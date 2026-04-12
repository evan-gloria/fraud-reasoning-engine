# 🛡️ Fraud Reasoning Engine

An **Agentic AI system** built on Google Cloud that autonomously investigates credit card fraud using natural language. Ask questions in plain English — the AI agent reasons about your intent, queries BigQuery via auto-generated SQL, and produces professional visualizations, all without writing a single line of SQL yourself.

> **Built with:** Google Cloud Vertex AI (Gemini 2.5 Flash) · BigQuery · Cloud Run · Streamlit · Python

---

## 🧠 AI Agent vs Agentic AI — What's the Difference?

These terms are often confused. Here's how they apply to this project:

| | AI Agent | Agentic AI |
|---|---|---|
| **What is it?** | A specific entity with a role, tools, and a goal | The architecture/design pattern that enables autonomous behaviour |
| **Analogy** | An employee you hired | The way that employee independently works without hand-holding |
| **In this project** | The "Senior Corporate Fraud Investigator" | The reasoning loop: observe → decide → act → evaluate → repeat |

### This project has:
- **1 AI Agent** — The Fraud Investigator (powered by Gemini 2.5 Flash)
- **2 Skills** — Text-to-SQL (BigQuery) and Chart Generation (Matplotlib/Seaborn)
- **1 Agentic AI System** — The full architecture that lets the agent reason, call tools, self-correct errors, and loop autonomously

```
┌──────────────────────────────────────────────────────────┐
│              Agentic AI System (Architecture)            │
│                                                          │
│   ┌──────────────────────────────────────────────────┐   │
│   │    AI Agent: "Senior Fraud Investigator"         │   │
│   │    ├── Skill: Text-to-SQL (BigQuery)             │   │
│   │    ├── Skill: Chart Generation (Matplotlib)      │   │
│   │    └── Brain: Gemini 2.5 Flash (Vertex AI)       │   │
│   └──────────────────────────────────────────────────┘   │
│                                                          │
│   Infrastructure:                                        │
│   ├── Cloud Run (Backend API)                            │
│   ├── BigQuery (Data Warehouse)                          │
│   └── Streamlit (Frontend UI)                            │
└──────────────────────────────────────────────────────────┘
```

---

## ⚙️ How the Agentic Loop Works

When a user asks a question like *"Show daily fraud as a bar chart with cumulative totals as a line"*, the system:

1. **Reasons** — The agent determines it needs data first, then a chart
2. **Acts** — Calls the Text-to-SQL skill, which generates and executes BigQuery SQL
3. **Self-Corrects** — If BigQuery rejects the SQL, the error is fed back to Gemini to auto-fix (up to 3 attempts)
4. **Acts Again** — Calls the Chart skill to produce a combo visualisation (bar + line with dual Y-axes)
5. **Responds** — Summarises findings in plain English alongside the chart

This autonomous loop is what makes it **agentic** — the AI decides *what* to do and *when*, without human intervention between steps.

---

## 🏗️ Architecture

| Component | Technology | Purpose |
|---|---|---|
| `reasoning_engine/` | Vertex AI + Gemini 2.5 Flash | Orchestrates the agent, manages tool calling and the agentic loop |
| `agent_skills/bq_sql_skill.py` | BigQuery + Gemini | Translates natural language → SQL, executes queries, auto-retries on errors |
| `agent_skills/graph_skill.py` | Matplotlib + Seaborn | Generates multi-series charts (bar, line, combo) with dual Y-axes |
| `api/` | FastAPI + Cloud Run | Production REST API backend, deployed as a container |
| `ui/` | Streamlit | Decoupled chat-based frontend (can be hosted anywhere) |
| `scripts/` | Faker + NumPy + Pandas | Synthetic data generator (5,000 realistic credit card transactions) |

---

## 🔐 Key Design Decisions

- **Schema Standardisation** — Column names follow the [Open Data Dictionary](https://www.opendatadictionary.com/) standard (e.g., `transaction_amount`, `is_flagged`, `merchant_category_code`)
- **SQL Safety** — Only `SELECT` statements are permitted. All DML/DDL is rejected before reaching BigQuery
- **Self-Healing SQL** — If the generated SQL fails, the error is automatically fed back to Gemini for correction (up to 3 retries)
- **Decoupled Frontend** — The Streamlit UI communicates via REST API only. No GCP credentials or secrets are exposed to the client
- **Parallel Tool Calling** — The agent can execute multiple tools simultaneously (e.g., two charts at once) following the Vertex AI multi-part protocol

---

## 🚀 Getting Started

### Prerequisites
- Python 3.11+
- [Poetry](https://python-poetry.org/)
- A Google Cloud project with BigQuery and Vertex AI enabled
- `gcloud` CLI authenticated

### Setup

```bash
# 1. Clone the repository
git clone https://github.com/evan-gloria/fraud-reasoning-engine.git
cd fraud-reasoning-engine

# 2. Install dependencies
poetry install

# 3. Configure environment
cp .env.example .env
# Edit .env with your GCP_PROJECT and GCP_REGION

# 4. Authenticate with Google Cloud
gcloud auth application-default login

# 5. Generate and load synthetic data into BigQuery
poetry run python scripts/generate_transactions.py --load-bq
```

### Running Locally

```bash
# Start the FastAPI backend
poetry run uvicorn api.main:app --host 0.0.0.0 --port 8080

# In a separate terminal, start the Streamlit frontend
poetry run streamlit run ui/streamlit_app.py
```

### Deploying to Google Cloud

```bash
# Deploy the backend to Cloud Run
gcloud run deploy fraud-reasoning-engine \
  --source . \
  --project $GCP_PROJECT \
  --region $GCP_REGION \
  --service-account "fraud-engine-sa@$GCP_PROJECT.iam.gserviceaccount.com" \
  --set-env-vars="GCP_PROJECT=$GCP_PROJECT,GCP_REGION=$GCP_REGION"
```

### Appending Fresh Data

```bash
# Append 5-20 random new transactions (safe — does NOT overwrite)
poetry run python scripts/generate_transactions.py --load-bq

# Reset the table with 5,000 fresh records
poetry run python scripts/generate_transactions.py --load-bq --truncate
```

---

## 💬 Example Questions to Try

Once the app is running, test the agent's reasoning with these prompts:

| Prompt | What it tests |
|---|---|
| *"How many transactions were flagged as fraud?"* | Basic aggregation |
| *"Which top 3 merchant category codes had the highest fraud rate?"* | GROUP BY + ranking |
| *"Show a breakdown of fraud per day for the last 10 days with cumulative totals"* | Subquery + window functions |
| *"Show the daily fraud count as a bar chart and cumulative as a line chart"* | Combo chart with dual Y-axes |
| *"What is the average risk score for international transactions above $500 AUD?"* | Multi-condition filtering |
| *"Write me a poem about credit cards"* | Persona guardrails (should decline) |

---

## 📄 License

This project is a Proof of Concept for portfolio and demonstration purposes.
