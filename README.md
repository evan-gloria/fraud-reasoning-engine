# 🛡️ Fraud Reasoning Engine

An **Agentic AI system** built on Google Cloud that autonomously investigates credit card fraud using natural language. Ask questions in plain English — the AI agent reasons about your intent, queries BigQuery via auto-generated SQL, and produces professional executive visualizations and reports.

> **Built with:** Google Cloud Vertex AI (Gemini 2.5 Flash) · BigQuery · Cloud Run · Cloud Storage · Firestore · Streamlit

---

## 🏗️ Architecture

The engine is built on a modular, decoupled architecture designed for executive-grade auditability and resilience.

| Component | Technology | Purpose |
|:--- |:--- |:--- |
| **`reasoning_engine/`** | Vertex AI (Gemini) | The "Brain." Orchestrates the 20-turn agentic loop and tool coordination. |
| **`agent_skills/`** | Python SDKs | Specialized tools for SQL generation, charting, and executive reporting. |
| **`api/`** | FastAPI + Firestore | The "Control Plane." Manages case history, registry synchronization, and security. |
| **`ui/`** | Streamlit | The "Command Center." A reactive, authenticated interface for investigators. |
| **`scripts/`** | Python + Faker | Synthetic data factory for generating realistic fraud scenarios. |

---

## 🌟 Modernized Features

### 1. Executive Reporting Engine (.pptx)
Move beyond simple charts. The engine now generates boardroom-ready PowerPoint presentations including:
- **Thematic Branding**: Automatically adopts company colors and fonts from a `theme.pptx` template.
- **Narrative Sectioning**: High-level transition slides to guide management through investigative phases.
- **Audit-Blue Tables**: Precision data grids for descriptive statistics (Mean, Median, Quartiles, etc.).

### 2. High-Capacity Reasoning Loop
Hardened for high-stakes investigations:
- **20-Turn Runway**: Expanded reasoning capacity allows the agent to solve multi-component queries (e.g., 3 charts + a structured deck) without stalling.
- **Universal Sync Guard**: Charting tools automatically align data and labels, preventing technical failures during complex visualisations.
- **Silent Tool Protocol**: Zero-noise interaction between the AI and its tools to prevent hallucinations.

### 3. UX Performance & Scalability
Designed for professional audit workflows where case history can span hundreds of investigations:
- **On-Demand Archive Retrieval**: The app completely bypasses startup latency by eliminating auto-fetching. The Case Registry is now stored behind a dedicated "View Case Archives" UI state, moving heavy database reads off the critical startup path.
- **Real-Time Archive Search**: Instantly filter historical investigations by Case ID or Title without dragging down the performance of the active investigation stream.

### 4. Production Governance & Security
- **Reactive Registry**: Automatic synchronization between the UI and Backend using Firestore persistence.
- **Identity Token Auth**: Backend endpoints are secured using Google Identity Tokens for institutional-grade access control.
- **Immutable Metadata**: Every report produced is tagged with GCS custom metadata (`user_prompt`, `sql_query`, `case_id`) for permanent audit trails.
- **Triad Defense (Prompt Injection)**: Employs a three-layer adversarial shield: Frontend Payload Limits (`max_chars`), Backend API Keyword Filtration, and a Hardened AI System Prompt Directive to refuse jailbreak attempts.

---

## 🚀 Getting Started

### 📦 Local Development (Docker-First)
The fastest way to launch the full stack (Backend + UI) is using Docker Compose:

```bash
# 1. Configure your environment
cp .env.example .env
# Edit .env with your GCP_PROJECT, GCP_REGION, and GCP_ARTIFACT_BUCKET

# 2. Authenticate locally
gcloud auth application-default login

# 3. Launch the stack
docker-compose up --build
```
*UI: http://localhost:8501 | API: http://localhost:8080*

### ☁️ Cloud Deployment (GCP)

#### 1. Security & IAM Roles
First, create the dedicated Service Account:
```bash
gcloud iam service-accounts create fraud-engine-sa \
    --display-name "Fraud Engine Service Account"
```

Then, bind the following "Least-Privilege" roles:
```bash
# Assign Vertex AI, BigQuery, Firestore, and GCS permissions
for ROLE in aiplatform.user bigquery.dataViewer bigquery.jobUser datastore.user storage.objectAdmin; do
    gcloud projects add-iam-policy-binding $GCP_PROJECT \
        --member="serviceAccount:fraud-engine-sa@$GCP_PROJECT.iam.gserviceaccount.com" \
        --role="roles/$ROLE"
done
```

#### 2. Deploy to Cloud Run
Deploy the backend logic to **Google Cloud Run** for production-grade scaling:

```bash
# Option A: SECURE (Production) - Requires SA Key for local access
gcloud run deploy fraud-reasoning-engine \
  --source . \
  --project $GCP_PROJECT \
  --region $GCP_REGION \
  --service-account "fraud-engine-sa@$GCP_PROJECT.iam.gserviceaccount.com" \
  --set-env-vars="GCP_PROJECT=$GCP_PROJECT,GCP_REGION=$GCP_REGION,GCP_ARTIFACT_BUCKET=$GCP_ARTIFACT_BUCKET,GCP_FIRESTORE_DATABASE=$GCP_FIRESTORE_DATABASE" \
  --no-allow-unauthenticated

# Option B: PUBLIC POC (Fastest) - No auth required for local access
gcloud run deploy fraud-reasoning-engine \
  --source . \
  --project $GCP_PROJECT \
  --region $GCP_REGION \
  --service-account "fraud-engine-sa@$GCP_PROJECT.iam.gserviceaccount.com" \
  --set-env-vars="GCP_PROJECT=$GCP_PROJECT,GCP_REGION=$GCP_REGION,GCP_ARTIFACT_BUCKET=$GCP_ARTIFACT_BUCKET,GCP_FIRESTORE_DATABASE=$GCP_FIRESTORE_DATABASE" \
  --allow-unauthenticated
```

---

## 💬 Investigative Test Suite

Try these "Executive Prompts" to experience the engine's full capacity:

| Prompt | What it Tests |
|:--- |:--- |
| *"Show the weekly fraud count for the last 14 days and create a professional presentation with a pie chart and a statistics table."* | **Multi-Tool Orchestration** |
| *"Visualize fraud per currency in a horizontal bar chart and add it to my investigation deck."* | **Professional Orientation (`barh`)** |
| *"Identify terminals with >5 fraud events and generate a section-based slide deck explaining the risk."* | **Narrative Sectioning** |
| *"Provide descriptive statistics for transaction amounts in the last 10 days using a tabular format."* | **Statistical Grids** |

---

## 🛡️ Data Governance
Every artifact generated by this system follows a strict **Chain of Custody** protocol. Raw evidence (.png) is transitioned to **Archive Storage** via Object Lifecycle Management (OLM), while final Management Reports (.pptx) are retained for permanent record-keeping with immutable metadata links back to the original SQL derivation.

---

## ⚠️ Disclaimer

*This project is a technical proof-of-concept for LLM-powered agentic workflows and microservice architecture. All data used within this engine—including transaction amounts, cardholders, and merchant names—is entirely synthetic. Any resemblance to real individuals, financial institutions, or actual fraud cases is purely coincidental. This solution is intended for demonstration purposes and should not be used in live financial environments without rigorous security and compliance auditing.*

**License**: This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
