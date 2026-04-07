# Fraud Reasoning Engine

A Proof of Concept (PoC) demonstrating a Google Cloud Vertex AI Reasoning Engine querying a BigQuery dataset using natural language to SQL.

## Architecture
- **Data Generator:** Synthesizes realistic 5,000 credit card transactions with fraud flags and pushes them to BigQuery.
- **Skill (bq_sql_skill.py):** A tool that uses Gemini to translate natural language into BigQuery SQL.
- **Agent (fraud_investigator.py):** A Native Vertex AI Agent acting as a Senior Corporate Fraud Investigator that uses the Skill to answer user queries.
- **UI (streamlit_app.py):** An interactive Chat Web App.

## Setup
1. Define your `.env` with `GCP_PROJECT` and `GCP_REGION`.
2. Authenticate: `gcloud auth application-default login`
3. Install dependencies: `poetry install`
4. Generate Data: `poetry run python mock_data/generate_transactions.py`

## Running the Web App
```bash
poetry run streamlit run app/streamlit_app.py
```

## Example Test Questions

Once the app is running, try asking the Agent the following questions to test its reasoning and Text-to-SQL logic:

1. *"Hi, I'm doing an audit. What is the total amount (in AUD) of transactions that we currently have flagged as fraudulent across all our mock data?"*
2. *"Can you break that down and tell me which Top 3 Merchant Category Codes had the highest number of fraud occurrences?"*
3. *"If I am looking for the single largest flagged transaction, who is the merchant and what was the amount?"*
4. *"Write me a poem about credit cards."* (To test that the persona rules reject off-topic questions!)
