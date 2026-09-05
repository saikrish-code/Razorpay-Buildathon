# Recoup — 5-Minute Product Demo Video Script & Technical Reference
**Project**: Recoup: Autonomous AI Revenue Recovery Engine  
**Hackathon**: Razorpay Buildathon — Track 3 (Autonomous AI Agents)  
**Live Application URL**: [https://compaq-tons-holes-placed.trycloudflare.com](https://compaq-tons-holes-placed.trycloudflare.com)  
**Interactive API Docs**: [https://compaq-tons-holes-placed.trycloudflare.com/api/docs](https://compaq-tons-holes-placed.trycloudflare.com/api/docs)  

---

## Section 1: Final Architecture as Actually Implemented

### 1.1 Plain-Text Pipeline Architecture
```
[ 1. Ingestion Engine ]
   Failed payments & abandoned checkouts (250 synthetic transactions across 3 types)
             │
             ▼
[ 2. RAG Policy Knowledge Store ]
   Hierarchical markdown chunker + In-memory subword TF-IDF cosine vector index
             │
             ▼
[ 3. Hybrid Diagnostic Classifier ]
   Deterministic Dictionary Lookup (0 token cost, <1ms) for 20+ standard codes
   + LLM Diagnostic Fallback (OpenAI Structured Output) for ambiguous abandoned carts
             │
             ▼
[ 4. Autonomous Agent + Deterministic Code Guardrails ]
   ReAct agent reasons with tools: retrieve_policy, retrieve_similar_cases,
   simulate_retry_payment, send_message, escalate_to_human, log_action.
   --> Pre-execution Python Guardrail filters: Quiet Hours (20:00-09:00 IST),
       Attempt Caps (>=3), Cooldown (<24h), DNC Registry, Account Freeze.
             │
             ▼
[ 5. Calibrated Outcome Simulator ]
   Empirical recovery probabilities (Tech: ~85%, Wait: ~70%, Action: ~40%, Fatal: 0%)
             │
             ▼
[ 6. Unified FastAPI REST & Static Serving Engine ]
   Serves compiled React 19 SPA from root `/` and async REST APIs under `/api/*`
             │
             ▼
[ 7. React 19 Frontend Dashboard ]
   Live metrics, breakdown meters, 1-click batch runner, 1-click dataset reset,
   and real-time slide-over audit trail drawer.
```

### 1.2 Evolution from Original Plan to Final Implementation
1. **Unified Single-Port Deployment (Vite + FastAPI)**:
   * *Original Plan*: Run backend on port 8000 and frontend on port 5173 separately, requiring complex CORS origin management or multi-host deployment (e.g. Render backend + Vercel frontend).
   * *Actual Implementation*: FastAPI was updated in [`main.py`](recoup/backend/app/main.py) to mount the compiled React 19 bundle (`recoup/frontend/dist`) directly at root `/` with SPA client-side route fallback. All API endpoints live at `/api/*`. Result: 0 CORS issues, instant zero-latency internal API routing, and single-port deployment.
2. **1-Click Live Dataset Reset (`POST /api/reset-data`)**:
   * *Original Plan*: Database resets required manual execution of `generate_data.py` from the command line.
   * *Actual Implementation*: Added a dedicated `POST /api/reset-data` route and a responsive `↺ Reset dataset` button in the UI top header right next to `▶ Run batch`. Presenters can reset the database to baseline with a single click during live video demos.
3. **Deterministic Guardrails in Pure Python (Not in System Prompts)**:
   * *Original Plan*: Rely primarily on LLM prompting to prevent quiet-hour messaging and contact flooding.
   * *Actual Implementation*: Strict deterministic Python interceptor (`DeterministicGuardrail.check_action()`) intercepts every outbound message or escalation before tool execution. If violated, it blocks the action with a structured `[GUARDRAIL BLOCKED]` audit record. Zero dependency on LLM prompt compliance.
4. **Instant Edge Tunneling**:
   * *Original Plan*: Localhost access only during development.
   * *Actual Implementation*: Cloudflare Tunnel daemon integrated, giving an instant live HTTPS link globally accessible from any phone or browser.

---

## Section 2: Exact Console Output from `run_batch.py`

Below is the **verbatim console output** produced by running `run_batch.py` on a freshly reset 250-record dataset:

```text
Loading transactions from database: C:\Users\Sai Krishna S\Documents\Razorpay Buildathon\recoup\backend\recoup.db...

============================================================================================
      RECOUP AI REVENUE RECOVERY ENGINE — FULL PIPELINE BATCH EXECUTION REPORT
============================================================================================
  Pipeline Flow: Ingest -> Diagnose -> Retrieve Policy -> Agent Acts -> Simulate -> Log & Update
============================================================================================

┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                              EXECUTIVE RECOVERY SUMMARY                                  │
├──────────────────────────────────────────────────────────────────────────────────────────┤
│  Total Transactions Processed : 250                                                  │
│  Total Revenue at Risk        : INR   1,314,635.00                                      │
│  Total Revenue Recovered      : INR     620,692.00  [SUCCESS]                             │
│  Amount Recovery Rate         :         47.21%                                       │
│  Transactions Recovered Count : 116             (46.4% volume recovery)                │
│  Permanently Unrecoverable    : 40              (Frozen & Escalate to Operations)        │
│  Pending / Active Follow-up   : 94                                                   │
│  Guardrail Interceptions      : 0               (Safety & Quiet Hours Protected)         │
└──────────────────────────────────────────────────────────────────────────────────────────┘

============================================================================================
  BREAKDOWN BY PAYMENT FAILURE REASON CODE
============================================================================================
Failure Reason Code      | Category               | Count  | At Risk (INR)  | Recovered      | Rate   
--------------------------------------------------------------------------------------------
customer_abandoned       | recoverable_action_needed | 45     |     297,724.00 |     100,120.00 |   33.6%
insufficient_funds       | recoverable_wait       | 50     |     227,778.00 |     148,046.00 |   65.0%
account_closed           | unrecoverable          | 40     |     196,727.00 |           0.00 |    0.0%
wrong_otp                | recoverable_action_needed | 28     |     157,941.00 |      56,872.00 |   36.0%
bank_timeout             | recoverable_wait       | 28     |     137,043.00 |     123,705.00 |   90.3%
card_expired             | recoverable_action_needed | 28     |     114,217.00 |      33,943.00 |   29.7%
daily_limit_exceeded     | recoverable_wait       | 13     |      95,988.00 |      72,639.00 |   75.7%
network_error            | recoverable_technical  | 18     |      87,217.00 |      85,367.00 |   97.9%
--------------------------------------------------------------------------------------------
TOTAL                    |                        | 250    |   1,314,635.00 |     620,692.00 |   47.2%
============================================================================================

============================================================================================
  BREAKDOWN BY RECOVERY CATEGORY
============================================================================================
Category                     | Count  | At Risk (INR)  | Recovered (INR) | Recovery Rate
--------------------------------------------------------------------------------------------
recoverable_action_needed    | 101    |     569,882.00 |      190,935.00 |         33.5%
recoverable_wait             | 91     |     460,809.00 |      344,390.00 |         74.7%
unrecoverable                | 40     |     196,727.00 |            0.00 |          0.0%
recoverable_technical        | 18     |      87,217.00 |       85,367.00 |         97.9%
============================================================================================

============================================================================================
  BREAKDOWN BY CUSTOMER CHANNEL PREFERENCE
============================================================================================
Channel              | Count  | At Risk (INR)  | Recovered (INR) | Conversion Rate
--------------------------------------------------------------------------------------------
Whatsapp             | 137    |     714,344.00 |      343,801.00 |           48.1%
Sms                  | 75     |     386,016.00 |      201,540.00 |           52.2%
Email                | 38     |     214,275.00 |       75,351.00 |           35.2%
============================================================================================
```

---

## Section 3: Three Concrete Example Cases with Full Audit Trails

### Case A: Recoverable Wait (`insufficient_funds` -> Success)
* **Transaction ID**: `txn_HyzMH8xvYKWAWHoP`
* **Customer ID**: `cust_xEOfY34NajjG`
* **Transaction Type**: `one_time_checkout`
* **Amount**: `INR 3,049.00`
* **Preferred Channel**: `WhatsApp`
* **Failure Code**: `insufficient_funds`
* **Final Status**: `recovered`

#### Full Audit Trail:
```text
[Event 1] 2026-09-03T09:03:23Z | Actor: system | Action: created
Notes: Ingested one_time_checkout event (payment.failed) with reason 'insufficient_funds'

[Event 2] 2026-09-02T14:30:00+05:30 | Actor: recoup_pipeline | Action: resolved
Notes: Pipeline Execution | Diagnosis: recoverable_wait (100% conf) | Action: send_message | Guardrail: PASSED | Outcome: RECOVERED (INR 3,049.00) | Method: Alternative Payment Link via WHATSAPP
```

---

### Case B: Deterministic Guardrail Block in Action (`MAX_CONTACT_ATTEMPTS_EXCEEDED`)
* **Transaction ID**: `txn_VEPRIcKmKaRKw3kn`
* **Customer ID**: `cust_H4UrIFjmLuuq`
* **Transaction Type**: `checkout_abandonment`
* **Amount**: `INR 2,299.00`
* **Preferred Channel**: `WhatsApp`
* **Failure Code**: `customer_abandoned`
* **Contact Attempts So Far**: `3`
* **Final Status**: `pending_compliance_review` (Suppressed by Safety Net)

#### Full Audit Trail:
```text
[Event 1] 2026-09-01T20:32:56Z | Actor: system | Action: created
Notes: Ingested checkout_abandonment event (checkout.abandoned) with reason 'customer_abandoned'

[Event 2] 2026-09-02T14:30:00+05:30 | Actor: recoup_pipeline | Action: contact_attempted
Notes: Pipeline Execution | Diagnosis: recoverable_action_needed (78% conf) | Action: send_message | Guardrail: PASSED | Outcome: UNRECOVERED | Method: Pending Follow-Up (send_message)

[Event 3] 2026-09-05T23:14:27+05:30 | Actor: guardrail_engine | Action: blocked
Notes: [GUARDRAIL BLOCKED] Action 'send_message' rejected. Rule: MAX_CONTACT_ATTEMPTS_EXCEEDED. Reason: Contact attempts (3) have reached or exceeded the maximum permitted limit (3). Outreach is blocked to prevent customer spam. Outbound communication suppressed to protect customer trust.
```

---

### Case C: Account Closed / Permanently Unrecoverable (Zero Customer Outreach)
* **Transaction ID**: `txn_2kAQFH2KTU51gJXY`
* **Customer ID**: `cust_liEFgJnmUYl8`
* **Transaction Type**: `subscription_renewal`
* **Amount**: `INR 12,500.00`
* **Preferred Channel**: `Email`
* **Failure Code**: `account_closed`
* **Final Status**: `unrecoverable` (Written off & escalated to operations)

#### Full Audit Trail:
```text
[Event 1] 2026-08-29T11:56:33Z | Actor: system | Action: created
Notes: Ingested subscription_renewal event (subscription.charged_failed) with reason 'account_closed'

[Event 2] 2026-09-02T14:30:00+05:30 | Actor: recoup_pipeline | Action: flagged
Notes: Pipeline Execution | Diagnosis: unrecoverable (100% conf) | Action: escalate_to_human | Guardrail: PASSED | Outcome: UNRECOVERED | Method: Human Operations Escalation / Write-Off
```

---

## Section 4: Technical Implementation Confirmations

| Question | Technical Confirmation & Details |
|---|---|
| **LLM Provider & Model** | **OpenAI `gpt-4o-mini`**<br>Configured via `OPENAI_MODEL="gpt-4o-mini"` in [`recoup/backend/.env`](recoup/backend/.env). Used with OpenAI Structured Outputs and Function Calling tool schemas (`retrieve_policy`, `retrieve_similar_cases`, `simulate_retry_payment`, `send_message`, `escalate_to_human`, `log_action`). If no API key is provided, an intelligent heuristic rule-based classifier handles the workflow gracefully. |
| **Vector Store Type** | **In-Memory Semantic Vector Store (Zero External DB)**<br>Implemented in [`app/retrieval/retriever.py`](recoup/backend/app/retrieval/retriever.py). Uses subword character n-grams (3–4 grams) + lexical TF-IDF with L2 cosine normalization. Reads structured policy markdown files from [`policies/*.md`](policies/). Requires no external vector database service (Pinecone, Chroma, Qdrant) or heavy native C-dependencies. Boots in under 50ms. |
| **Razorpay API Status** | **Fully Simulated (Zero-Cost Reproducibility)**<br>Payment webhook ingestion, retry token switching, and WhatsApp/SMS payment recovery links are modeled and calibrated using empirical payment failure statistics via [`simulate_outcome.py`](recoup/backend/simulate_outcome.py). Supported environment keys (`RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`) exist for production webhooks, but all transactions in the demo operate in sandbox simulation to guarantee 100% offline, zero-charge testing. |

---

## Section 5: Frontend Screen & Page Catalog

| Screen / Page | URL Route | Key Visual & Interactive Elements |
|---|---|---|
| **1. Executive Dashboard** | `/` | • **Header Controls**: Last updated timestamp, `↺ Reset dataset` (1-click baseline reset), and `▶ Run batch` execution button.<br>• **KPI Metric Cards**: Total at Risk (₹13,14,635), Total Recovered (₹6,20,692), Recovery Rate % (47.2%), Recovered Count (116 / 46.4%).<br>• **Failure Reason Breakdown**: Progress meters across insufficient funds, cart abandonment, wrong OTP, card expired, bank timeout, network error, and closed accounts.<br>• **Recovery Category Distribution**: Bar breakdown of wait, action needed, technical, and unrecoverable buckets.<br>• **Channel Efficiency**: WhatsApp vs SMS vs Email recovery rate comparison.<br>• **Recent Activity Stream**: Live feed of the latest transactions. |
| **2. Transactions Ledger** | `/transactions` | • **Filter Bar**: Free-text search (ID, customer, email, phone) + Status dropdown (All, Open, Pending, Recovered, Unrecoverable, Needs Review) + Reason code dropdown + Channel dropdown + Clear filters button.<br>• **Interactive Ledger Table**: Columns for Transaction ID, Customer ID, Failure Reason, Channel badge, Status badge, Timestamp, and amount formatted in INR.<br>• **Pagination**: 100 records per page with previous/next navigation. |
| **3. Audit-Trail Slide-Over Drawer** | Drawer Modal on click | • **Transaction Header**: ID, clipboard copy button, status pill, amount, currency.<br>• **Customer Profile**: Contact channels, email, phone.<br>• **AI Diagnosis**: Category badge, root-cause reasoning, diagnosis confidence score %.<br>• **Policy Citations (RAG)**: Policy document title and exact cited policy rules retrieved from markdown files.<br>• **Immutable Audit Log Timeline**: Chronological event history showing actor (`system`, `recoup_pipeline`, `guardrail_engine`), action type, timestamp, and detailed guardrail verification notes. |
| **4. Interactive API Playground** | `/api/docs` | • Embedded FastAPI Swagger UI allowing interactive live requests to all endpoints: `GET /api/transactions`, `GET /api/report`, `POST /api/run-batch`, `POST /api/reset-data`, `GET /api/health`, and policy endpoints. |

---

## Section 6: Video Demo Assets (Screenshots Saved in `/demo-assets`)

All four required video screenshots were captured directly from the live deployed application and are stored in [`demo-assets/`](demo-assets/):

1. **Dashboard View**:  
   File: [`demo-assets/01_dashboard.png`](demo-assets/01_dashboard.png)  
   *Demonstrates*: Clean brand header, KPI metric cards, progress bars by failure code, and channel conversion rates.

2. **Transactions Ledger Table**:  
   File: [`demo-assets/02_transactions_table.png`](demo-assets/02_transactions_table.png)  
   *Demonstrates*: Full transaction ledger of 250 records with multi-filter dropdowns and search inputs.

3. **Open Audit-Trail Detail Panel**:  
   File: [`demo-assets/03_audit_trail_panel.png`](demo-assets/03_audit_trail_panel.png)  
   *Demonstrates*: Slide-over drawer for `txn_VEPRIcKmKaRKw3kn` showing the AI root-cause diagnosis, policy citation from `04_abandoned_checkout_outreach.md`, and deterministic guardrail intervention.

4. **Account Closed / Unrecoverable Case**:  
   File: [`demo-assets/04_account_closed_case.png`](demo-assets/04_account_closed_case.png)  
   *Demonstrates*: Slide-over drawer for `txn_2kAQFH2KTU51gJXY` showing the `unrecoverable` write-off status, policy citation from `06_unrecoverable_account_write_off.md`, and escalation to human operations with zero customer outreach.

---

## Section 7: Recommended 5-Minute Demo Video Script Outline

* **0:00 – 0:45 | Problem & Value Proposition**:
  Show the dashboard (`01_dashboard.png`). Explain that payment failures cost merchants 5–15% of GMV. Introduce Recoup as an autonomous, policy-governed recovery engine built for Razorpay failures.
* **0:45 – 1:30 | Live Pipeline Execution & Metrics**:
  Highlight the live metrics: ₹13.14L at risk, ₹6.20L recovered (47.2% recovery rate). Click `▶ Run batch` or explain the 1-click batch execution and `↺ Reset dataset` capabilities.
* **1:30 – 2:30 | Technical Core: Hybrid Diagnosis & RAG**:
  Open the transactions ledger (`02_transactions_table.png`). Explain the hybrid split: 0-cost deterministic rules for standard codes, LLM structured outputs for ambiguous cart abandonment, and in-memory RAG policy retrieval.
* **2:30 – 3:45 | Deterministic Safety Guardrails in Action**:
  Open transaction drawer (`03_audit_trail_panel.png`). Point out that guardrails are hard-coded in Python (quiet hours, contact caps, cooldowns, DNC). Contrast this with prompt-only safety to demonstrate compliance rigor.
* **3:45 – 4:30 | Edge Cases & Unrecoverable Accounts**:
  Show the account closed case (`04_account_closed_case.png`). Highlight that confirmed closed accounts or fraud are immediately frozen with zero customer spam, and escalated for tax write-off.
* **4:30 – 5:00 | Production Readiness & Live Access**:
  Show the Swagger UI (`/api/docs`), mention the unified single-port FastAPI + React 19 architecture, and share the live public link.
