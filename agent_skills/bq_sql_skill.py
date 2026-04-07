"""
bq_sql_skill.py

A Text-to-SQL tool (skill) for the Fraud Reasoning Engine.

Given a natural language question, this skill:
  1. Injects the BigQuery table schema into a prompt
  2. Calls Gemini via Vertex AI to generate a valid BigQuery SQL query
  3. Executes the query against the retail_banking dataset
  4. Returns the results as a formatted string for the agent to reason over

Safety: Only SELECT statements are permitted. Any attempt to run DML/DDL
        will be rejected before reaching BigQuery.
"""

import os
import re

from dotenv import load_dotenv
from google.cloud import bigquery
import vertexai
from vertexai.generative_models import GenerativeModel

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

GCP_PROJECT = os.environ["GCP_PROJECT"]
GCP_REGION = os.environ.get("GCP_REGION", "us-central1")
BQ_DATASET = "retail_banking"
BQ_TABLE = "credit_card_transactions"
FULL_TABLE_ID = f"{GCP_PROJECT}.{BQ_DATASET}.{BQ_TABLE}"
GEMINI_MODEL = "gemini-2.5-flash"
MAX_RESULT_ROWS = 100

# ---------------------------------------------------------------------------
# Schema context
# Injected into the prompt so Gemini understands the table structure
# without needing to make a live INFORMATION_SCHEMA call on every request.
# ---------------------------------------------------------------------------

SCHEMA_CONTEXT = f"""
You are a BigQuery SQL expert. Generate a single valid BigQuery SQL query
to answer the user's question about retail banking credit card transactions.

Table: `{FULL_TABLE_ID}`

Schema:
  - transaction_id       STRING      Unique transaction UUID
  - customer_id          STRING      Customer identifier (e.g. CUST_12345678)
  - transaction_timestamp TIMESTAMP  When the transaction occurred (UTC)
  - merchant_name        STRING      Name of the merchant
  - merchant_category_code STRING    MCC code (e.g. '5411' = Grocery, '5812' = Restaurant)
  - amount               FLOAT64     Transaction amount in the transaction currency
  - currency             STRING      Currency code (e.g. 'AUD', 'USD', 'EUR')
  - is_flagged_fraud     BOOL        True if the transaction was flagged as fraudulent
  - risk_score           FLOAT64     Fraud risk score between 0.0 (low) and 1.0 (high)
  - location_country     STRING      Country where the transaction occurred
  - terminal_id          STRING      Payment terminal identifier (e.g. TERM_1234)

Rules:
  - Only return the raw SQL query. No markdown, no explanation, no code fences.
  - Only generate SELECT statements. Never use INSERT, UPDATE, DELETE, DROP, or CREATE.
  - Use standard BigQuery SQL syntax.
  - For date arithmetic, use TIMESTAMP functions (e.g. TIMESTAMP_SUB, CURRENT_TIMESTAMP).
  - Limit results to {MAX_RESULT_ROWS} rows unless the user asks for aggregates.
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_safe_query(sql: str) -> bool:
    """
    Rejects any SQL that is not a plain SELECT statement.
    Guards against prompt injection attempts that try to run DML/DDL.
    """
    normalised = sql.strip().upper()
    forbidden = re.compile(
        r"\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE|MERGE|CALL)\b"
    )
    return normalised.startswith("SELECT") and not forbidden.search(normalised)


def _format_results(rows: list[dict]) -> str:
    """
    Formats BigQuery result rows into a readable string for the agent.
    """
    if not rows:
        return "The query returned no results."

    headers = list(rows[0].keys())
    lines = [" | ".join(headers)]
    lines.append("-" * len(lines[0]))
    for row in rows:
        lines.append(" | ".join(str(row[h]) for h in headers))

    result = "\n".join(lines)
    if len(rows) == MAX_RESULT_ROWS:
        result += f"\n\n[Note: Results truncated to {MAX_RESULT_ROWS} rows.]"
    return result


# ---------------------------------------------------------------------------
# Core skill function
# ---------------------------------------------------------------------------


def run_text_to_sql(question: str) -> str:
    """
    Answers a natural language question about credit card transactions
    by generating and executing a BigQuery SQL query via Gemini.

    This function is designed to be registered as a Tool in the
    Vertex AI Reasoning Engine agent.

    Args:
        question: A natural language question about the transaction data.
                  Example: "How many transactions were flagged as fraud last week?"

    Returns:
        A formatted string containing the query results, ready for the
        agent to interpret and summarise for the end user.
    """
    # 1. Initialise Vertex AI SDK
    vertexai.init(project=GCP_PROJECT, location=GCP_REGION)
    model = GenerativeModel(GEMINI_MODEL)

    # 2. Generate SQL from the natural language question
    prompt = f"{SCHEMA_CONTEXT}\n\nUser question: {question}"
    response = model.generate_content(prompt)
    generated_sql = response.text.strip()

    # Strip markdown fences if Gemini wraps in ```sql ... ``` despite instructions
    generated_sql = re.sub(r"^```(?:sql)?", "", generated_sql, flags=re.IGNORECASE).strip()
    generated_sql = re.sub(r"```$", "", generated_sql).strip()

    print(f"[bq_sql_skill] Generated SQL:\n{generated_sql}\n")

    # 3. Safety check — only permit SELECT statements
    if not _is_safe_query(generated_sql):
        return (
            "Safety check failed: the generated query was not a SELECT statement "
            "and was not executed. Please rephrase your question."
        )

    # 4. Execute against BigQuery
    bq_client = bigquery.Client(project=GCP_PROJECT)
    query_job = bq_client.query(generated_sql)
    results = query_job.result()

    rows = [dict(row) for row in results][:MAX_RESULT_ROWS]

    # 5. Return formatted results
    return _format_results(rows)


# ---------------------------------------------------------------------------
# Standalone test entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    test_questions = [
        "How many transactions were flagged as fraud?",
        "What is the average risk score for AUD transactions above $500?",
        "Which merchant category code has the highest fraud rate?",
    ]

    for q in test_questions:
        print(f"\n{'='*60}")
        print(f"Question: {q}")
        print(f"{'='*60}")
        answer = run_text_to_sql(q)
        print(answer)
