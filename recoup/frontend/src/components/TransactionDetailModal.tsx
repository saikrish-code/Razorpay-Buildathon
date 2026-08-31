/**
 * components/TransactionDetailModal.tsx
 * Slide-over modal showing transaction details and its audit trail.
 */

import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { AuditLog, Transaction } from "../types";
import "./TransactionDetailModal.css";

interface Props {
  transaction: Transaction | null;
  onClose: () => void;
}

const ACTION_LABELS: Record<string, string> = {
  created: "Created",
  updated: "Updated",
  flagged: "Flagged",
  reviewed: "Reviewed",
  resolved: "Resolved",
};

const STATUS_COLORS: Record<string, string> = {
  pending: "#c8b560",
  success: "#34d399",
  failed: "#f87171",
  refunded: "#818cf8",
};

export default function TransactionDetailModal({ transaction, onClose }: Props) {
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!transaction) return;
    setLoading(true);
    api.transactions
      .auditLogs(transaction.id)
      .then(setAuditLogs)
      .catch(() => setAuditLogs([]))
      .finally(() => setLoading(false));
  }, [transaction]);

  if (!transaction) return null;

  const amountFormatted = new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: transaction.currency,
  }).format(transaction.amount / 100);

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true" onClick={onClose}>
      <aside className="modal-panel" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="modal-header">
          <div>
            <h2 className="modal-title">Transaction Details</h2>
            <code className="modal-payment-id">{transaction.razorpay_payment_id}</code>
          </div>
          <button className="modal-close-btn" onClick={onClose} aria-label="Close modal">
            ✕
          </button>
        </div>

        {/* Details grid */}
        <section className="modal-section">
          <div className="detail-grid">
            <DetailRow label="Amount" value={amountFormatted} />
            <DetailRow
              label="Status"
              value={
                <span
                  className="status-badge"
                  style={{ background: STATUS_COLORS[transaction.status] ?? "#6b7280" }}
                >
                  {transaction.status}
                </span>
              }
            />
            <DetailRow label="Email" value={transaction.customer_email ?? "—"} />
            <DetailRow label="Phone" value={transaction.customer_phone ?? "—"} />
            <DetailRow label="Description" value={transaction.description ?? "—"} />
            <DetailRow
              label="Created"
              value={new Date(transaction.created_at).toLocaleString()}
            />
          </div>
        </section>

        {/* Audit Trail */}
        <section className="modal-section">
          <h3 className="section-title">Audit Trail</h3>
          {loading ? (
            <p className="muted-text">Loading audit trail…</p>
          ) : auditLogs.length === 0 ? (
            <p className="muted-text">No audit entries yet.</p>
          ) : (
            <ol className="audit-timeline">
              {auditLogs.map((log) => (
                <li key={log.id} className="audit-entry">
                  <div className="audit-dot" />
                  <div className="audit-body">
                    <span className="audit-action">{ACTION_LABELS[log.action] ?? log.action}</span>
                    {log.actor && <span className="audit-actor"> by {log.actor}</span>}
                    {log.notes && <p className="audit-notes">{log.notes}</p>}
                    <time className="audit-time">
                      {new Date(log.created_at).toLocaleString()}
                    </time>
                  </div>
                </li>
              ))}
            </ol>
          )}
        </section>
      </aside>
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <>
      <dt className="detail-label">{label}</dt>
      <dd className="detail-value">{value}</dd>
    </>
  );
}
