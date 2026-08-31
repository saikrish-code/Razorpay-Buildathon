# recoup

> AI-powered revenue recovery for failed Razorpay payments.  
> **Razorpay Buildathon — Track 3**

---

## Project Structure

```
recoup/
├── backend/                        Python FastAPI service
│   ├── app/
│   │   ├── main.py                 FastAPI app factory (CORS, lifespan, routers)
│   │   ├── config.py               pydantic-settings — all env vars live here
│   │   ├── database.py             SQLAlchemy async engine + get_db dependency
│   │   ├── models/                 Pydantic v2 request/response schemas
│   │   │   ├── transaction.py
│   │   │   ├── audit_log.py
│   │   │   └── policy_document.py
│   │   ├── db/                     Database access layer (CRUD / repository pattern)
│   │   │   ├── base.py             SQLAlchemy ORM table definitions
│   │   │   ├── transactions.py
│   │   │   ├── audit_logs.py
│   │   │   └── policy_documents.py
│   │   ├── retrieval/              RAG / vector-search logic (stub)
│   │   │   └── retriever.py
│   │   ├── agent/                  LLM orchestration / agentic reasoning (stub)
│   │   │   └── agent.py
│   │   ├── guardrails/             Policy enforcement / safety checks (stub)
│   │   │   └── guardrail.py
│   │   └── routes/                 FastAPI APIRouter modules
│   │       ├── health.py           GET /api/health
│   │       ├── transactions.py     CRUD + audit trail
│   │       ├── audit_logs.py       POST /api/audit-logs
│   │       └── policy_documents.py CRUD
│   ├── .env.example                Template — copy to .env and fill in secrets
│   ├── .gitignore
│   └── requirements.txt
│
├── frontend/                       React + TypeScript (Vite)
│   ├── src/
│   │   ├── main.tsx                Entry point
│   │   ├── App.tsx                 Router + navbar
│   │   ├── api/
│   │   │   └── client.ts           Typed Axios helpers (proxied to /api)
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx       Health status + module overview cards
│   │   │   └── Transactions.tsx    Transaction list page
│   │   ├── components/
│   │   │   ├── TransactionTable.tsx
│   │   │   └── TransactionDetailModal.tsx  Slide-over with audit trail
│   │   └── types/
│   │       └── index.ts            Shared TypeScript interfaces
│   ├── index.html
│   ├── vite.config.ts              Proxies /api → http://localhost:8000
│   ├── .env.example
│   └── package.json
│
└── README.md                       ← you are here
```

---

## Prerequisites

| Tool | Minimum version |
|------|----------------|
| Python | 3.11+ |
| Node.js | 18+ |
| npm | 9+ |

---

## Running Locally

### 1 · Clone and enter the project

```bash
git clone <your-repo-url>
cd recoup
```

### 2 · Backend

```bash
cd backend

# Create and activate a virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Open .env and fill in your OPENAI_API_KEY, RAZORPAY_* keys, etc.

# Start the dev server (auto-reloads on file changes)
uvicorn app.main:app --reload --port 8000
```

The API will be live at **http://localhost:8000**

- Interactive docs: http://localhost:8000/api/docs  
- Health check:    http://localhost:8000/api/health

### 3 · Frontend

Open a **new terminal**:

```bash
cd frontend

# Install dependencies (first time only)
npm install

# Copy env template (optional — only needed for production overrides)
cp .env.example .env

# Start the Vite dev server
npm run dev
```

The frontend will be live at **http://localhost:5173**

> Vite automatically proxies all `/api/*` requests to `http://localhost:8000`,
> so no CORS configuration is needed during development.

---

## API Routes

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/transactions` | List transactions (paginated) |
| POST | `/api/transactions` | Create a transaction |
| GET | `/api/transactions/{id}` | Get a single transaction |
| PATCH | `/api/transactions/{id}` | Update a transaction |
| GET | `/api/transactions/{id}/audit-logs` | Get audit trail |
| POST | `/api/audit-logs` | Create an audit log entry |
| GET | `/api/policy-documents` | List policy documents |
| POST | `/api/policy-documents` | Create a policy document |
| GET | `/api/policy-documents/{id}` | Get a policy document |
| PATCH | `/api/policy-documents/{id}` | Update a policy document |

Full interactive API documentation: **http://localhost:8000/api/docs**

---

## Environment Variables

All secrets are stored in `backend/.env` (never committed to git).  
Copy `backend/.env.example` → `backend/.env` and fill in:

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | SQLAlchemy connection string (default: SQLite) |
| `OPENAI_API_KEY` | OpenAI API key for LLM agent |
| `OPENAI_MODEL` | Model name (default: `gpt-4o-mini`) |
| `RAZORPAY_KEY_ID` | Razorpay API key ID |
| `RAZORPAY_KEY_SECRET` | Razorpay API key secret |
| `DEBUG` | Set `true` to enable SQLAlchemy query logging |
| `CORS_ORIGINS` | JSON array of allowed frontend origins |

---

## Next Steps (business logic stubs to implement)

| Module | File | TODO |
|--------|------|------|
| RAG Retrieval | `app/retrieval/retriever.py` | Embed policy docs + vector search |
| AI Agent | `app/agent/agent.py` | LLM tool-calling for recovery decisions |
| Guardrails | `app/guardrails/guardrail.py` | Policy enforcement before agent actions |
| Razorpay Webhook | `app/routes/` | Ingest failed payment events |

---

## License

MIT
