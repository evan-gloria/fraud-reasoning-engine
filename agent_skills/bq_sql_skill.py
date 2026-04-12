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
  - merchant_category_code STRING    A standard four-digit number used by credit card processors to classify a business by the type of goods or services it provides.
  - transaction_amount   FLOAT64     Transaction amount in the transaction currency
  - currency             STRING      Currency code (e.g. 'AUD', 'USD', 'EUR')
  - is_flagged           BOOL        True if the transaction was flagged as fraudulent
  - risk_score           FLOAT64     Fraud risk score between 0.0 (low) and 1.0 (high)
  - location_country     STRING      Country where the transaction occurred
  - terminal_id          STRING      Payment terminal identifier (e.g. TERM_1234)

Rules:
  - Only return the raw SQL query. No markdown, no explanation, no code fences.
  - Only generate SELECT statements. Never use INSERT, UPDATE, DELETE, DROP, or CREATE.
  - Use standard BigQuery SQL syntax.
  - CRITICAL BIGQUERY RULE: `TIMESTAMP_SUB` and `TIMESTAMP_ADD` do NOT support `MONTH` or `YEAR` intervals.
  - To filter by months/years, you MUST use `DATE()` first. Example for last month: `WHERE DATE(transaction_timestamp) >= DATE_SUB(CURRENT_DATE(), INTERVAL 1 MONTH)`
  - Limit results to {MAX_RESULT_ROWS} rows unless the user asks for aggregates.

WINDOW FUNCTION RULES (MANDATORY):
  When you need both an aggregate (e.g. COUNT) AND a window function (e.g. cumulative SUM)
  in the same query, you MUST use a subquery pattern:
    1. Inner subquery: perform the GROUP BY and aggregation
    2. Outer query: apply the window function on the pre-aggregated columns
  NEVER mix GROUP BY with window functions in the same SELECT level.

Gold Standard Examples:

- Question: "Show fraudulent transactions in the last month"
  SQL: SELECT * FROM `{FULL_TABLE_ID}` WHERE is_flagged = true AND DATE(transaction_timestamp) >= DATE_SUB(CURRENT_DATE(), INTERVAL 1 MONTH)

- Question: "Daily fraud count and cumulative count for the last 10 days"
  SQL: SELECT day, daily_fraud_count, SUM(daily_fraud_count) OVER (ORDER BY day ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS cumulative_fraud_count FROM (SELECT DATE(transaction_timestamp) AS day, COUNT(*) AS daily_fraud_count FROM `{FULL_TABLE_ID}` WHERE is_flagged = true AND DATE(transaction_timestamp) >= DATE_SUB(CURRENT_DATE(), INTERVAL 10 DAY) GROUP BY day) ORDER BY day

- Question: "Top 5 merchants by total transaction amount in AUD"
  SQL: SELECT merchant_name, SUM(transaction_amount) as total_amount FROM `{FULL_TABLE_ID}` WHERE currency = 'AUD' GROUP BY merchant_name ORDER BY total_amount DESC LIMIT 5
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


MAX_RETRIES = 2  # Number of auto-fix attempts before giving up


def _clean_sql(raw: str) -> str:
    """Strip markdown fences and whitespace from generated SQL."""
    sql = raw.strip()
    sql = re.sub(r"^```(?:sql)?", "", sql, flags=re.IGNORECASE).strip()
    sql = re.sub(r"```$", "", sql).strip()
    return sql


def run_text_to_sql(question: str) -> str:
    """
    Answers a natural language question about credit card transactions
    by generating and executing a BigQuery SQL query via Gemini.

    Includes automatic retry: if BigQuery rejects the SQL, the error
    is fed back to Gemini so it can self-correct (up to MAX_RETRIES).

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
    bq_client = bigquery.Client(project=GCP_PROJECT)

    # 2. Generate SQL from the natural language question
    prompt = f"{SCHEMA_CONTEXT}\n\nUser question: {question}"
    response = model.generate_content(prompt)
    generated_sql = _clean_sql(response.text)

    print(f"[bq_sql_skill] Generated SQL:\n{generated_sql}\n")

    # 3. Safety check — only permit SELECT statements
    if not _is_safe_query(generated_sql):
        return (
            "Safety check failed: the generated query was not a SELECT statement "
            "and was not executed. Please rephrase your question."
        )

    # 4. Execute against BigQuery — with automatic retry on SQL errors
    for attempt in range(1 + MAX_RETRIES):
        try:
            query_job = bq_client.query(generated_sql)
            results = query_job.result()
            rows = [dict(row) for row in results][:MAX_RESULT_ROWS]
            return _format_results(rows)

        except Exception as e:
            error_msg = str(e)
            print(f"[bq_sql_skill] Attempt {attempt + 1} failed: {error_msg}")

            if attempt < MAX_RETRIES:
                # Feed the error back to Gemini and ask it to fix the SQL
                retry_prompt = (
                    f"{SCHEMA_CONTEXT}\n\n"
                    f"User question: {question}\n\n"
                    f"Your previous SQL was:\n{generated_sql}\n\n"
                    f"BigQuery rejected it with this error:\n{error_msg}\n\n"
                    f"COMMON FIX: If the error mentions 'neither grouped nor aggregated', "
                    f"you MUST use a subquery: do the GROUP BY in a subquery first, "
                    f"then apply window functions in the outer query on the pre-aggregated columns.\n\n"
                    f"Please fix the SQL and return ONLY the corrected query."
                )
                response = model.generate_content(retry_prompt)
                generated_sql = _clean_sql(response.text)
                print(f"[bq_sql_skill] Retry SQL:\n{generated_sql}\n")

                if not _is_safe_query(generated_sql):
                    return "Safety check failed on retry. Please rephrase your question."
            else:
                return f"Query failed after {1 + MAX_RETRIES} attempts. Last error: {error_msg}"


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
