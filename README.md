# Recoup: Autonomous AI Revenue Recovery Engine

> **AI-powered revenue recovery and cart abandonment dunning for Razorpay payment failures.**  
> Built for the **Razorpay Buildathon — Track 3**.

---

## Executive Overview

Payment failures cost merchants 5–15% of their Gross Merchandise Value (GMV) in avoidable churn, dropped checkouts, and missed renewals. **Recoup** is an intelligent, policy-governed autonomous agent system that ingests failed transactions, diagnoses their root causes, retrieves corporate dunning policies via RAG, and safely executes personalized multi-channel recovery workflows (WhatsApp, SMS, Email, and payment switches) — with strict, deterministic code guardrails protecting regulatory compliance and customer trust.

```
+--------------------------------------------------------------------------------------------------+
|                                    RECOUP ARCHITECTURE PIPELINE                                  |
|                                                                                                  |
|   [ 1. Data Ingestion ]           Failed payments & cart drop-offs (250 synthetic transactions)  |
|            |                                                                                     |
|            v                                                                                     |
|   [ 2. RAG Retrieval ]            Markdown policy chunking + subword TF-IDF cosine vector store  |
|            |                                                                                     |
|            v                                                                                     |
|   [ 3. Diagnosis Engine ]         Rule-Based (0-cost) for known codes + LLM for ambiguous carts  |
|            |                                                                                     |
|            v                                                                                     |
|   [ 4. Agent + Guardrails ]       Autonomous reasoning & tools + Deterministic Python safety net |
|            |                                                                                     |
|            v                                                                                     |
|   [ 5. Outcome Simulator ]        Empirical calibrated recovery probabilities (85% tech, 0% fatal) |
|            |                                                                                     |
|            v                                                                                     |
|   [ 6. FastAPI REST Engine ]      Async endpoints: /transactions, /report, /run-batch, /audit    |
|            |                                                                                     |
|            v                                                                                     |
|   [ 7. React 19 Frontend ]        Modern Vite dashboard, KPI cards, filters, and audit trail     |
+--------------------------------------------------------------------------------------------------+
```

---

## System Architecture

```mermaid
flowchart TD
    subgraph Data["1. Data Ingestion & Store"]
        D1[Razorpay Payment Webhooks] --> DB[(SQLite / PostgreSQL\nrecoup.db)]
        D2[Cart Abandonment Events] --> DB
        D3[Subscription Renewals] --> DB
    end

    subgraph Retrieval["2. Policy Retrieval / RAG"]
        P1[Markdown Policy Docs\npolicies/*.md] --> Chunker[Hierarchical Markdown Chunker]
        Chunker --> VecStore[In-Memory Semantic Vector Store\nTF-IDF + Subword n-grams]
        VecStore --> RAGQuery[Top-k Policy Chunks]
    end

    subgraph Diagnosis["3. Root-Cause Diagnosis"]
        DB --> Router{Failure Code\nRecognized?}
        Router -- "Known Code\n(insufficient_funds,\ncard_expired, etc.)" --> RulePath[Deterministic Rule Lookup\n0 Cost | Sub-millisecond]
        Router -- "customer_abandoned\nor ambiguous" --> LLMPath[OpenAI Structured Output\nCategory + Likely Reason + Confidence]
        RulePath --> DiagResult[Diagnosis Result\n4 Categories]
        LLMPath --> DiagResult
    end

    subgraph AgentSystem["4. Agent Reasoning & Guardrails"]
        DiagResult --> Agent[Autonomous AI Agent\nRecoupAgent]
        RAGQuery --> Agent
        HistCases[(Historical Case Base)] --> Agent
        Agent --> ToolSelector{Tool Selection}
        
        ToolSelector --> Retry[simulate_retry_payment]
        ToolSelector --> SendMsg[send_message]
        ToolSelector --> Escalate[escalate_to_human]
        ToolSelector --> LogAction[log_action]

        subgraph Guardrails["Deterministic Safety Guardrails (Python Code)"]
            SendMsg --> GCheck{Guardrail Check}
            Escalate --> GCheck
            GCheck -- "Quiet Hours (20:00-09:00 IST)\nMax Attempts Exceeded (>=3)\nCooldown < 24h\nOpted-Out / DNC Customer\nUnrecoverable Account" --> Block[BLOCKED\n[GUARDRAIL BLOCKED] Audit Log]
            GCheck -- "Compliant" --> Pass[PASSED\nExecute Action]
        end
    end

    subgraph Outcome["5. Outcome Simulation"]
        Pass --> Sim[Calibrated Outcome Simulator]
        Retry --> Sim
        Sim --> ProbCalc[Category Probabilities\nTech: ~85% | Wait: ~70%\nAction: ~40% | Fatal: 0%]
        ProbCalc --> UpdateDB[(Update Transaction Status\n& Immutable Audit Log)]
        Block --> UpdateDB
    end

    subgraph APILayer["6. FastAPI Backend Service"]
        UpdateDB --> FastAPIServer[FastAPI Async Service]
        FastAPIServer --> Ep1["GET /api/transactions"]
        FastAPIServer --> Ep2["GET /api/report (KPIs)"]
        FastAPIServer --> Ep3["POST /api/run-batch"]
        FastAPIServer --> Ep4["GET /api/transactions/{id}/audit-logs"]
    end

    subgraph Frontend["7. React 19 Frontend Dashboard"]
        Ep1 --> UI[Vite React + TypeScript App]
        Ep2 --> UI
        Ep3 --> UI
        Ep4 --> UI
        UI --> Views["KPI Cards | Recovery Charts | Transaction Table | Audit Drawer"]
    end
```

---

## Architectural Deep Dive (Stage by Stage)

### 1. Data Ingestion
- **Dataset**: 250 realistic transaction records reflecting Indian payment scenarios across three core types:
  1. `one_time_checkout` (~48%, 120 records): E-commerce lifestyle goods, tech accessories, flight bookings.
  2. `subscription_renewal` (~32%, 80 records): SaaS plans, digital subscriptions, cloud memberships.
  3. `checkout_abandonment` (~20%, 50 records): High-intent shopping carts dropped before payment authorization.
- **Attributes**: Transaction ID, customer phone/email, amount (INR 199 to 15,000), preferred channel (WhatsApp ~58%, SMS ~27%, Email ~15%), contact attempts, and timestamp distribution.
- **Database**: SQLite with `aiosqlite` async connection pooling, indexed on key query attributes.

### 2. Retrieval / RAG (Retrieval-Augmented Generation)
- **Policy Documents**: Structured Markdown files stored in `policies/` specifying SLA rules, quiet hours, retry cooldowns, escalation pathways, and discount boundaries:
  - `01_insufficient_funds_recovery.md`
  - `02_card_update_reminder.md`
  - `03_do_not_contact_and_timing.md`
  - `04_abandoned_checkout_outreach.md`
  - `05_subscription_dunning_playbook.md`
  - `06_unrecoverable_account_write_off.md`
- **Hierarchical Markdown Chunker**: Splits documents cleanly along header boundaries (`# ` and `## `) with contextual section metadata.
- **Semantic Vector Store**: Zero-dependency subword n-gram (3-4 character n-grams) and lexical TF-IDF vectorizer with L2 cosine normalization and domain-synonym expansion (`nsf` → `insufficient`, `dunning` → `subscription renewal`).

### 3. Diagnosis Engine (Rule-Based + LLM Hybrid Split)
- **Standardized 4-Tier Categorization**:
  1. `recoverable_wait`: Temporary liquidity or timing constraint (e.g. `insufficient_funds`, `bank_timeout`, `daily_limit_exceeded`). Best handled by polite reminder and scheduled retry.
  2. `recoverable_action_needed`: Customer intervention required (e.g. `card_expired`, `wrong_otp`, price hesitation). Handled by tokenized 1-click update link or concierge incentive.
  3. `recoverable_technical`: Transient network or switch errors (e.g. `network_error`, `gateway_timeout`). Handled by automated secondary gateway retry.
  4. `unrecoverable`: Permanent failures (e.g. `account_closed`, `fraud_suspected`, sanctions). Outbound messaging frozen; escalated to human operations and queued for tax write-off.
- **Dual-Path Routing**:
  - Deterministic Rule Engine classifies 20+ known codes instantly with 0 API cost and sub-millisecond execution.
  - LLM Diagnostic Engine (OpenAI Structured Outputs / Tool Calling) processes `customer_abandoned` carts and ambiguous failures, returning structured root causes, confidence scores, and action plans.

### 4. Agent Reasoning & Deterministic Guardrails
- **LLM Tool Ecosystem**:
  - `retrieve_policy(query)`: RAG vector search over policy documents.
  - `retrieve_similar_cases(transaction)`: Historical recovery tactic lookup.
  - `simulate_retry_payment(transaction_id)`: Gateway payment switch retry.
  - `send_message(customer_id, channel, content)`: Dispatches personalized WhatsApp/SMS/Email outreach.
  - `escalate_to_human(transaction_id, reason)`: Operations routing for unrecoverable/fraud transactions.
  - `log_action(transaction_id, action, reasoning)`: Creates immutable audit entries.
- **Code-Enforced Deterministic Guardrails**:
  - Outbound actions (`send_message`, `escalate_to_human`) pass through a Python verification filter *before* execution.
  - Violations immediately block action execution and log a structured `[GUARDRAIL BLOCKED]` audit record.

### 5. Outcome Simulator
- Uses empirical recovery probability models calibrated against actual payment failure categories and customer response channels:
  - `recoverable_technical`: ~85% base recovery rate.
  - `recoverable_wait`: ~70% base recovery rate.
  - `recoverable_action_needed`: ~40% base recovery rate.
  - `unrecoverable`: 0.0% recovery rate.
  - Guardrail-blocked actions: Strictly 0.0% recovery (customer never received message).
- Includes channel engagement multipliers (+8% for interactive WhatsApp checkout links) and contact attempt decay factors.

### 6. API Layer (FastAPI)
- Exposes async REST endpoints:
  - `GET /api/transactions`: Multi-field filtered pagination (status, reason code, type, channel, amount range, search).
  - `GET /api/transactions/{id}`: Detailed transaction inspection with complete ordered audit trail.
  - `POST /api/run-batch`: Triggers full 6-step recovery pipeline across transactions and updates database records.
  - `GET /api/report`: Live recovery KPI analytics (Total At Risk, Total Recovered, Recovery Rate, breakdowns).
  - `GET /api/health`: Health status, version, and database connectivity.
  - `GET /api/policy-documents`: CRUD management for dunning policy documents.

### 7. Modern Frontend Dashboard (React 19 + TypeScript + Vite)
- Built with a modern dark theme and interactive analytics:
  - **KPI Cards**: Revenue at Risk, Total Recovered, Amount Recovery Rate %, Volume Recovery Rate %.
  - **Breakdown Tables & Progress Meters**: By failure reason code, recovery category, and channel.
  - **Interactive Pipeline Runner**: One-click batch pipeline trigger with live status indicators.
  - **Filterable Transaction Table**: Status, failure reason, channel, search, and amount sorting.
  - **Slide-Over Audit Trail Drawer**: Complete timestamped event history, diagnosis confidence, and guardrail notes for every transaction.

---

## Key Engineering Decisions & Rationale

### 1. Why Guardrails are Enforced in Code (Not Just in the Prompt)
* **The Problem with Prompt-Only Safety**: Modern LLMs are probabilistic engines. Under edge cases, subtle prompt injections, novel phrasing, or temperature fluctuations, an LLM can ignore system prompt directives (e.g. sending messages at 2 AM or messaging an opted-out customer).
* **Regulatory & Financial Liability**: In India, TRAI regulations impose severe financial penalties for commercial communications sent during quiet hours (20:00 to 09:00 IST) or to customers on the National Do-Not-Call (DND) Registry.
* **Our Solution**: All outbound actions are intercepted by deterministic Python preconditions (`check_action`) before execution:
  - **Quiet Hours Check**: Evaluates current timestamp in `Asia/Kolkata` (IST) against operational bounds (09:00–20:00 IST).
  - **Contact Cap**: Rejects if contact attempts $\ge 3$.
  - **Cooldown Period**: Rejects if $< 24$ hours have elapsed since previous outreach.
  - **DNC / Opt-Out Registry**: Instant rejection if customer ID, phone, or email exists in the opt-out registry.
  - **Fatal Error Freeze**: Prohibits customer messaging on closed accounts or confirmed fraud.
* **Result**: 100% deterministic safety guarantee with zero reliance on LLM compliance, paired with an immutable `[GUARDRAIL BLOCKED]` audit trail.

### 2. Why RAG Was Used Instead of Hardcoding Policies
* **Decoupling Business Policy from Code**: Dunning policies, retry grace windows, and channel escalation paths are business rules that change frequently. Hardcoding these in Python scripts or giant LLM prompts requires engineering deployments for every minor SLA adjustment.
* **Non-Developer Governance**: By structuring policies as plain Markdown files in `policies/`, finance, risk, and legal teams can update policies directly via git or the `/api/policy-documents` endpoint without modifying application source code.
* **Token Efficiency & Context Hygiene**: Ingesting the entire dunning manual into every LLM invocation inflates token costs and dilutes reasoning focus. RAG queries retrieve only the top 2 relevant chunks, keeping latency low and hallucination risk minimal.

### 3. Why the Rule-Based / LLM Split Exists in Diagnosis
* **Volume and Economics**: In production payment switches handling millions of payments daily, 70–80% of failures have clear, unambiguous gateway response codes (`insufficient_funds`, `bank_timeout`, `card_expired`, `wrong_otp`).
* **Latency & Cost Waste**: Routing standard errors through an LLM incurs 1–2 seconds of latency and substantial API costs with zero incremental accuracy over a deterministic dictionary lookup.
* **Hybrid Routing Architecture**:
  - **Rule-Based Path**: Instant lookup mapping 20+ standard gateway error codes to recovery categories and action templates in $<1$ millisecond at $0 token cost.
  - **LLM Diagnostic Path**: Reserved exclusively for ambiguous events, cart drop-offs (`customer_abandoned`), and multi-factor scenarios where contextual inference (cart value, customer history, items) is required.
* **Result**: 80% reduction in LLM inference costs and immediate throughput for high-volume transactions.

### 4. Why an In-Memory Vector Store & SQLite Were Chosen
* **Zero Infrastructure Overhead**: Requiring external vector databases (Pinecone, Qdrant) or heavy services adds deployment complexity, API key management, and failure points.
* **Fast Boot & Portability**: The custom subword TF-IDF vectorizer runs in pure Python with zero external C-extensions, initializing the entire policy index in $<50$ milliseconds.
* **Full Offline Reproducibility**: The entire test suite (91 unit tests) runs in under 1 second without internet connectivity, mock servers, or external credentials.

---

## Known Limitations

1. **Simulated Outcomes**: Recovery outcomes are generated via calibrated empirical probability distributions rather than live card charges or UPI debit intents.
2. **In-Memory Vector Store at Small Scale**: The lexical/subword TF-IDF cosine vectorizer operates in-memory. While ideal for dozens of markdown policy documents, scaling to hundreds of thousands of dynamic documents would require a persistent, distributed vector database (e.g. `pgvector`, Qdrant).
3. **No Real Channel Integrations**: Outbound messages (WhatsApp, SMS, Email) are simulated and logged to the database audit trail rather than integrated with live Twilio, Gupshup, SendGrid, or WhatsApp Business API webhooks.
4. **Static Guardrail Rules**: Policy thresholds (09:00–20:00 IST quiet hours, max 3 attempts, 24h cooldown) are configured via constants and environment variables rather than a multi-tenant dynamic UI rule builder.
5. **No Human-Review Queue for Low-Confidence Cases**: When an action is blocked or escalated (`escalate_to_human`), its status transitions to `pending_compliance_review` or `unrecoverable`, but there is currently no dedicated human agent review portal for manual triage and override.

---

## Cloud Deployment Guide

### Architecture Topology

```
+---------------------------+             +---------------------------+
|    Frontend on Vercel     |  HTTPS API  |  Backend on Render/Railway|
|  (React 19 + TypeScript)  | ----------> |      (FastAPI + Python)   |
|   VITE_API_BASE_URL       |             |  CORS_ORIGINS, SQLite/PG  |
+---------------------------+             +---------------------------+
```

---

### Deploy Backend on Render

1. **Create Web Service**:
   - Log into [Render Dashboard](https://dashboard.render.com).
   - Click **New +** → **Web Service** and connect your repository.
2. **Configure Service Details**:
   - **Root Directory**: `recoup/backend` (or leave empty if using root Blueprint).
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
3. **Set Environment Variables**:
   | Variable | Example Value | Description |
   |---|---|---|
   | `OPENAI_API_KEY` | `sk-proj-...` | OpenAI API Key (optional; structured fallback active if omitted) |
   | `OPENAI_MODEL` | `gpt-4o-mini` | Model for LLM diagnosis & agent reasoning |
   | `CORS_ORIGINS` | `*` or `https://your-app.vercel.app` | Allowed frontend domains (comma-separated or `*`) |
   | `DATABASE_URL` | `sqlite+aiosqlite:///./recoup.db` | Async SQLAlchemy database URL |
   | `PYTHON_VERSION` | `3.11.9` | Python runtime version |
4. **Deploy**:
   - Click **Create Web Service**. Once live, note your backend URL (e.g. `https://recoup-api.onrender.com`).
   - Interactive docs will be available at `https://recoup-api.onrender.com/api/docs`.

> [!TIP]
> A ready-to-use Render Blueprint is included in [`render.yaml`](file:///c:/Users/Sai%20Krishna%20S/Documents/Razorpay%20Buildathon/render.yaml) for 1-click infrastructure-as-code deployment.

---

### Deploy Backend on Railway

1. Log into [Railway](https://railway.app) and click **New Project** → **Deploy from GitHub repo**.
2. Railway will automatically detect [`railway.json`](file:///c:/Users/Sai%20Krishna%20S/Documents/Razorpay%20Buildathon/railway.json) and [`Procfile`](file:///c:/Users/Sai%20Krishna%20S/Documents/Razorpay%20Buildathon/Procfile).
3. In **Variables**, add:
   - `CORS_ORIGINS` = `*`
   - `OPENAI_API_KEY` = `sk-proj-...`
   - `OPENAI_MODEL` = `gpt-4o-mini`
4. Railway will build and generate a public domain (e.g. `https://recoup-production.up.railway.app`).

---

### Deploy Frontend on Vercel

1. Log into [Vercel Dashboard](https://vercel.com) and click **Add New...** → **Project**.
2. Select your repository.
3. In the project settings:
   - **Framework Preset**: `Vite`
   - **Root Directory**: Click **Edit** and choose `recoup/frontend`
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`
4. **Configure Environment Variables**:
   | Variable | Value | Description |
   |---|---|---|
   | `VITE_API_BASE_URL` | `https://recoup-api.onrender.com` | Deployed backend URL (without trailing slash) |
5. **Deploy**: Click **Deploy**. Vercel will automatically apply client-side route rewrites defined in [`recoup/frontend/vercel.json`](file:///c:/Users/Sai%20Krishna%20S/Documents/Razorpay%20Buildathon/recoup/frontend/vercel.json).

---

## Environment Variables Reference

All credentials are loaded from environment variables (or local `.env` files). **No API keys are committed to git.**

### Backend (`recoup/backend/.env`)

| Variable | Required | Default | Purpose |
|---|:---:|---|---|
| `DATABASE_URL` | No | `sqlite+aiosqlite:///./recoup.db` | Async SQLAlchemy database connection string |
| `OPENAI_API_KEY` | Optional | `""` | OpenAI API key for LLM diagnosis and agent reasoning (intelligent heuristic fallback used if omitted) |
| `OPENAI_MODEL` | No | `gpt-4o-mini` | OpenAI model identifier |
| `CORS_ORIGINS` | No | `["http://localhost:5173"]` | Allowed CORS origins. Accepts wildcard `*`, JSON array, or comma-separated URLs |
| `DEBUG` | No | `false` | Enable SQL query debug logging |
| `PORT` | No | `8000` | Port for Uvicorn server |
| `RAZORPAY_KEY_ID` | Optional | `""` | Razorpay API key ID for live webhooks |
| `RAZORPAY_KEY_SECRET` | Optional | `""` | Razorpay API key secret |

### Frontend (`recoup/frontend/.env`)

| Variable | Required | Default | Purpose |
|---|:---:|---|---|
| `VITE_API_BASE_URL` | In Prod | `""` (proxies to `localhost:8000` in dev) | Base URL of the deployed FastAPI backend |

---

## Local Development Quickstart

### Prerequisites
- Python 3.11+
- Node.js 18+ and npm 9+

### 1. Backend Setup
```bash
# Enter backend directory
cd recoup/backend

# Create and activate virtual environment
python -m venv .venv

# Windows:
.venv\Scripts\activate
# macOS/Linux:
# source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env

# Generate/verify 250 synthetic transactions
python generate_data.py

# Start FastAPI dev server
uvicorn app.main:app --reload --port 8000
```
API docs: **http://localhost:8000/api/docs**  
Health check: **http://localhost:8000/api/health**

### 2. Frontend Setup
```bash
# In a new terminal:
cd recoup/frontend

# Install dependencies
npm install

# Start Vite dev server (auto-proxies /api -> localhost:8000)
npm run dev
```
Dashboard UI: **http://localhost:5173**

### 3. Running Unit Tests & Batch Pipeline
```bash
# Run all 91 pytest unit tests
cd recoup/backend
.venv\Scripts\pytest -v

# Run the end-to-end recovery batch pipeline via CLI
python run_batch.py
```

---

## Project Structure

```
recoup/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI application factory, CORS, lifespan
│   │   ├── config.py               # Pydantic settings with CORS & env validators
│   │   ├── database.py             # Async SQLAlchemy engine & auto-seeder
│   │   ├── agent/
│   │   │   ├── agent.py            # Autonomous LLM tool-calling agent
│   │   │   └── diagnose.py         # 4-tier rule-based + LLM diagnosis engine
│   │   ├── guardrails/
│   │   │   └── guardrail.py        # Deterministic Python code safety guardrails
│   │   ├── retrieval/
│   │   │   └── retriever.py        # Pure-Python TF-IDF subword vector store
│   │   ├── db/                     # ORM models (Transaction, AuditLog, Policy)
│   │   └── routes/                 # REST APIRouters (transactions, report, batch)
│   ├── policies/                   # Version-controlled markdown dunning policies
│   ├── tests/                      # 91 unit tests across all engine modules
│   ├── generate_data.py            # 250-record realistic dataset generator
│   ├── simulate_outcome.py         # Calibrated empirical recovery simulator
│   ├── run_batch.py                # End-to-end batch pipeline runner
│   ├── Procfile                    # Web process specification
│   ├── render.yaml                 # Render Blueprint configuration
│   └── requirements.txt            # Python dependencies
│
├── frontend/
│   ├── src/
│   │   ├── App.tsx                 # Navigation & router
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx       # KPI metrics, recovery rate charts, batch trigger
│   │   │   └── Transactions.tsx    # Filterable transactions table & detail drawer
│   │   ├── components/             # Reusable UI components & modals
│   │   └── api/client.ts           # Axios client configured for VITE_API_BASE_URL
│   ├── vercel.json                 # Vercel SPA routing rewrites
│   ├── package.json
│   └── vite.config.ts
│
├── policies/                       # Root policy markdown copies
├── render.yaml                     # Root Render Blueprint
├── Procfile                        # Root web process file
├── railway.json                    # Railway deployment specification
├── .gitignore                      # Root ignore protecting secrets & build files
└── README.md                       # ← You are here
```

---

## License

MIT License. Developed for the Razorpay Buildathon 2026.
