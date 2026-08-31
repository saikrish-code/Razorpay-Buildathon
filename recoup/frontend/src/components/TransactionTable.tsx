/**
 * components/TransactionTable.tsx
 * Responsive table listing transactions. Clicking a row opens the detail modal.
 */

import type { Transaction } from "../types";
import "./TransactionTable.css";

interface Props {
  transactions: Transaction[];
  onSelect: (t: Transaction) => void;
  loading: boolean;
}

const STATUS_COLORS: Record<string, string> = {
  pending: "#c8b560",
  success: "#34d399",
  failed: "#f87171",
  refunded: "#818cf8",
};

export default function TransactionTable({ transactions, onSelect, loading }: Props) {
  if (loading) {
    return (
      <div className="table-placeholder">
        <div className="skeleton-row" />
        <div className="skeleton-row" />
        <div className="skeleton-row" />
      </div>
    );
  }

  if (transactions.length === 0) {
    return (
      <div className="table-empty">
        <span className="empty-icon">🧾</span>
        <p>No transactions found.</p>
        <p className="muted-text">Transactions will appear here once ingested from Razorpay.</p>
      </div>
    );
  }

  return (
    <div className="table-wrapper">
      <table className="tx-table" id="transactions-table">
        <thead>
          <tr>
            <th>Payment ID</th>
            <th>Amount</th>
            <th>Status</th>
            <th>Customer</th>
            <th>Created</th>
          </tr>
        </thead>
        <tbody>
          {transactions.map((tx) => (
            <tr
              key={tx.id}
              className="tx-row"
              onClick={() => onSelect(tx)}
              tabIndex={0}
              onKeyDown={(e) => e.key === "Enter" && onSelect(tx)}
              aria-label={`View details for ${tx.razorpay_payment_id}`}
            >
              <td>
                <code className="payment-id">{tx.razorpay_payment_id}</code>
              </td>
              <td className="amount-cell">
                {new Intl.NumberFormat("en-IN", {
                  style: "currency",
                  currency: tx.currency,
                }).format(tx.amount)}
              </td>
              <td>
                <span
                  className="status-pill"
                  style={{ background: STATUS_COLORS[tx.status] ?? "#6b7280" }}
                >
                  {tx.status}
                </span>
              </td>
              <td>{tx.customer_email ?? tx.customer_phone ?? "—"}</td>
              <td className="date-cell">{new Date(tx.created_at).toLocaleDateString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
