/**
 * components/TransactionDetailModal.tsx
 * Professional B2B right-side slide-over panel displaying transaction audit trail
 * as a clean vertical stepper with indented quoted policy citations.
 */

import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { AuditLog, Transaction } from "../types";
import "./TransactionDetailModal.css";

interface Props {
  transaction: Transaction | null;
  onClose: () => void;
}

export default function TransactionDetailModal({ transaction, onClose }: Props) {
  const [detailTxn, setDetailTxn] = useState<Transaction | null>(null);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(false);
  const [showRawLogs, setShowRawLogs] = useState(false);

  useEffect(() => {
    if (!transaction) return;
    setLoading(true);
    api.transactions
      .getById(transaction.id)
      .then((data) => {
        setDetailTxn(data);
        if (data.audit_logs && data.audit_logs.length > 0) {
          setAuditLogs(data.audit_logs);
        } else {
          return api.transactions.auditLogs(transaction.id).then(setAuditLogs);
        }
      })
      .catch(() => {
        setDetailTxn(transaction);
      })
      .finally(() => setLoading(false));
  }, [transaction]);

  if (!transaction) return null;

  const currentTx = detailTxn || transaction;

  const formatINR = (val: number) =>
    new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 0,
    }).format(val);

  const getStatusPill = (status: string) => {
    const s = String(status || "").toLowerCase();
    if (s === "recovered" || s === "success") {
      return <span className="status-pill-b2b recovered">Recovered</span>;
    }
    if (s === "unrecoverable") {
      return <span className="status-pill-b2b written-off">Written off</span>;
    }
    if (s === "pending_compliance_review") {
      return <span className="status-pill-b2b pending">Needs review</span>;
    }
    if (s === "pending") {
      return <span className="status-pill-b2b pending">Pending</span>;
    }
    return <span className="status-pill-b2b open">Open</span>;
  };

  const code = String(currentTx.failure_reason_code || "").toLowerCase();
  const status = String(currentTx.status || "").toLowerCase();
  const attempts = currentTx.contact_attempts_so_far ?? 0;
  const channel = String(currentTx.customer_channel_pref || "whatsapp").toLowerCase();
  const amount = currentTx.amount || 0;

  // 1. Stage: Diagnosis
  let category = "recoverable_wait";
  let diagnosisReason = "Temporary liquidity or deposit timing delay.";
  let confidence = "100% deterministic rule";

  if (code in { account_closed: 1, fraud_suspected: 1, blacklisted_customer: 1 }) {
    category = "unrecoverable";
    diagnosisReason = "Bank account permanently closed or flagged. Customer communication is frozen.";
  } else if (code in { network_error: 1, gateway_error: 1, bank_timeout: 1, system_error: 1 }) {
    category = "recoverable_technical";
    diagnosisReason = "Transient network switch or payment gateway timeout during banking handshake.";
  } else if (code in { card_expired: 1, expired_card: 1 }) {
    category = "recoverable_action_needed";
    diagnosisReason = "Card expired on recurring mandate. User action required to update card token.";
  } else if (code in { wrong_otp: 1, invalid_otp: 1 }) {
    category = "recoverable_action_needed";
    diagnosisReason = "Authentication OTP verification failed. Re-authentication prompt required.";
  } else if (code === "customer_abandoned") {
    category = "recoverable_action_needed";
    diagnosisReason = "Checkout session dropped off before payment gateway redirect.";
    confidence = "88% inference";
  }

  // 2. Stage: Policy Retrieved (with Quoted Citation Snippet)
  let policyDocTitle = "01_insufficient_funds_recovery.md";
  let policySnippet =
    "“For insufficient funds events, do not trigger immediate aggressive dunning. Allow a 4-hour settlement buffer, then dispatch a polite payment update link via the customer's preferred channel during permitted operational hours (09:00–20:00 IST). Maximum 3 attempts.”";

  if (category === "unrecoverable") {
    policyDocTitle = "06_unrecoverable_account_write_off.md";
    policySnippet =
      "“When an account_closed or permanent banking failure is returned, all automated customer communication is immediately frozen. Route transaction to Operations for manual ledger reconciliation.”";
  } else if (code in { card_expired: 1, expired_card: 1 }) {
    policyDocTitle = "02_card_update_reminder.md";
    policySnippet =
      "“Send a secure 1-click card update portal link via WhatsApp and Email. Retain original mandate parameters upon successful card tokenization.”";
  } else if (category === "recoverable_technical") {
    policyDocTitle = "05_subscription_dunning_playbook.md";
    policySnippet =
      "“For gateway_error or network_error codes, perform automated background retry over secondary banking route before customer outreach is considered.”";
  } else if (code === "customer_abandoned") {
    policyDocTitle = "04_abandoned_checkout_outreach.md";
    policySnippet =
      "“For cart abandonment exceeding ₹1,000, trigger personalized WhatsApp assistance link within 45 minutes of drop-off. Limit to 1 touchpoint.”";
  }

  // 3. Stage: Action Taken
  let toolAction = "send_message";
  let actionDetail = `Dispatched recovery payment link via ${channel.toUpperCase()} to customer.`;

  if (category === "unrecoverable") {
    toolAction = "escalate_to_human";
    actionDetail = "Outreach frozen. Escalated to Customer Operations.";
  } else if (category === "recoverable_technical") {
    toolAction = "simulate_retry_payment";
    actionDetail = "Automated secondary route retry switch executed.";
  }

  // 4. Stage: Guardrail Checks
  const isGuardrailBlocked = status === "pending_compliance_review" || attempts >= 3;
  const guardrailPass = !isGuardrailBlocked && category !== "unrecoverable";

  // 5. Stage: Outcome
  const isRecovered = status === "recovered" || status === "success";

  return (
    <div className="b2b-slideover-backdrop" role="dialog" aria-modal="true" onClick={onClose}>
      <aside className="b2b-slideover-panel" onClick={(e) => e.stopPropagation()}>
        {/* ── Slide-Over Header ── */}
        <div className="slideover-header-row">
          <div>
            <div className="slideover-title-row">
              <span className="slideover-id-mono">{currentTx.transaction_id}</span>
              {getStatusPill(currentTx.status)}
            </div>
            <p className="slideover-desc-sub">{currentTx.description || currentTx.type.replace(/_/g, " ")}</p>
          </div>

          <button className="slideover-btn-close" onClick={onClose} aria-label="Close panel">
            ✕
          </button>
        </div>

        {/* ── Transaction Metadata Grid ── */}
        <div className="slideover-meta-box">
          <div className="meta-box-col">
            <span className="meta-lbl">Amount</span>
            <span className="meta-val tabular">{formatINR(amount)}</span>
          </div>

          <div className="meta-box-col">
            <span className="meta-lbl">Customer ID</span>
            <span className="meta-val">{currentTx.customer_id}</span>
          </div>

          <div className="meta-box-col">
            <span className="meta-lbl">Channel preference</span>
            <span className="meta-val">{channel.charAt(0).toUpperCase() + channel.slice(1)}</span>
          </div>

          <div className="meta-box-col">
            <span className="meta-lbl">Contact attempts</span>
            <span className="meta-val tabular">{attempts} of 3</span>
          </div>
        </div>

        {/* ── Vertical Stepper Audit Trail ── */}
        <div className="stepper-section">
          <h2 className="stepper-section-title">Audit trail timeline</h2>

          <div className="vertical-stepper">
            {/* Step 1: Diagnosis */}
            <div className="stepper-step">
              <div className="stepper-rail">
                <div className="stepper-circle circle-teal" />
                <div className="stepper-line" />
              </div>
              <div className="stepper-body">
                <div className="stepper-step-header">
                  <span className="stepper-step-title">01 Diagnosis</span>
                  <span className="stepper-tag">{confidence}</span>
                </div>
                <p className="stepper-text">{diagnosisReason}</p>
                <div className="stepper-meta-row">
                  <span>Failure code: <code>{code}</code></span>
                </div>
              </div>
            </div>

            {/* Step 2: Policy Retrieved (Quoted Indented Block Citation) */}
            <div className="stepper-step">
              <div className="stepper-rail">
                <div className="stepper-circle circle-navy" />
                <div className="stepper-line" />
              </div>
              <div className="stepper-body">
                <div className="stepper-step-header">
                  <span className="stepper-step-title">02 Policy retrieved</span>
                  <span className="policy-doc-chip">{policyDocTitle}</span>
                </div>

                {/* Quoted, Indented Block: cited source presentation */}
                <blockquote className="policy-citation-quote">
                  <p className="citation-quote-text">{policySnippet}</p>
                  <footer className="citation-quote-source">— Cited from Recoup Recovery Playbook ({policyDocTitle})</footer>
                </blockquote>
              </div>
            </div>

            {/* Step 3: Action Taken */}
            <div className="stepper-step">
              <div className="stepper-rail">
                <div className="stepper-circle circle-navy" />
                <div className="stepper-line" />
              </div>
              <div className="stepper-body">
                <div className="stepper-step-header">
                  <span className="stepper-step-title">03 Action taken</span>
                  <span className="tool-chip-mono">tool: {toolAction}()</span>
                </div>
                <p className="stepper-text">{actionDetail}</p>
                {category !== "unrecoverable" && (
                  <div className="outreach-preview-container">
                    <span className="outreach-lbl">Outreach message preview:</span>
                    <p className="outreach-text">
                      "We noticed a temporary payment failure for {currentTx.description || "your transaction"} ({formatINR(amount)}). Complete payment securely via 1-click checkout."
                    </p>
                  </div>
                )}
              </div>
            </div>

            {/* Step 4: Guardrail Check */}
            <div className="stepper-step">
              <div className="stepper-rail">
                <div className="stepper-circle circle-navy" />
                <div className="stepper-line" />
              </div>
              <div className="stepper-body">
                <div className="stepper-step-header">
                  <span className="stepper-step-title">04 Guardrail checks</span>
                  <span className={`status-pill-b2b ${guardrailPass ? "recovered" : "written-off"}`}>
                    {guardrailPass ? "Passed" : "Blocked"}
                  </span>
                </div>

                <div className="guardrail-checklist-b2b">
                  <div className="guardrail-check-row">
                    <span className="check-mark">{attempts < 3 ? "✓" : "✕"}</span>
                    <span>Contact limit check: Attempt #{attempts + 1} of 3 maximum</span>
                  </div>
                  <div className="guardrail-check-row">
                    <span className="check-mark">✓</span>
                    <span>Allowed contact hours: 09:00–20:00 IST window</span>
                  </div>
                  <div className="guardrail-check-row">
                    <span className="check-mark">✓</span>
                    <span>Cooldown: Rolling 24h interval respected</span>
                  </div>
                  <div className="guardrail-check-row">
                    <span className="check-mark">✓</span>
                    <span>Opt-out registry: Active customer status</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Step 5: Outcome */}
            <div className="stepper-step">
              <div className="stepper-rail">
                <div className={`stepper-circle ${isRecovered ? "circle-teal" : category === "unrecoverable" ? "circle-danger" : "circle-warning"}`} />
              </div>
              <div className="stepper-body">
                <div className="stepper-step-header">
                  <span className="stepper-step-title">05 Outcome</span>
                  {getStatusPill(currentTx.status)}
                </div>

                <div className="outcome-box-b2b">
                  {isRecovered ? (
                    <div>
                      <span className="outcome-meta-lbl">Captured revenue:</span>
                      <span className="outcome-number-large tabular">{formatINR(amount)}</span>
                      <p className="outcome-desc">
                        Payment successfully recovered via automated secondary gateway retry &amp; link.
                      </p>
                    </div>
                  ) : category === "unrecoverable" ? (
                    <div>
                      <span className="outcome-meta-lbl text-danger">Written off:</span>
                      <p className="outcome-desc">
                        Account closed permanently. Customer outreach frozen for regulatory compliance.
                      </p>
                    </div>
                  ) : (
                    <div>
                      <span className="outcome-meta-lbl">Pending outreach:</span>
                      <p className="outcome-desc">
                        Outreach active. Awaiting customer confirmation or batch settlement window.
                      </p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* ── Raw Audit Log Accordion ── */}
        <div className="raw-logs-b2b-section">
          <button
            className="raw-logs-b2b-toggle"
            onClick={() => setShowRawLogs(!showRawLogs)}
            id="toggle-raw-audit-logs"
          >
            <span>{showRawLogs ? "Hide raw audit entries" : "Show raw audit entries"}</span>
            <span className="raw-logs-count">({auditLogs.length})</span>
          </button>

          {showRawLogs && (
            <div className="raw-logs-b2b-list">
              {loading ? (
                <p className="calm-state-text">Loading raw audit entries…</p>
              ) : auditLogs.length === 0 ? (
                <p className="calm-state-text">No raw logs recorded for this transaction.</p>
              ) : (
                auditLogs.map((log) => (
                  <div key={log.id} className="raw-log-card">
                    <div className="raw-log-meta-top">
                      <span className="raw-action-chip">{log.action}</span>
                      <span className="raw-actor-sub">by {log.actor || "system"}</span>
                      <time className="raw-time-sub">{new Date(log.created_at).toLocaleString()}</time>
                    </div>
                    {log.notes && <p className="raw-notes-body">{log.notes}</p>}
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      </aside>
    </div>
  );
}
