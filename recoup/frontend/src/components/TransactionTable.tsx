/**
 * components/TransactionTable.tsx
 * Dense B2B transactions table with sortable column headers, right-aligned tabular amounts,
 * soft-tinted status pills, hover actions, and pagination summary.
 */

import { useState } from "react";
import type { Transaction } from "../types";
import "./TransactionTable.css";

interface Props {
  transactions: Transaction[];
  onSelect: (t: Transaction) => void;
  loading: boolean;
  onClearFilters?: () => void;
}

type SortField = "transaction_id" | "amount" | "status" | "contact_attempts_so_far" | "created_at";

export default function TransactionTable({ transactions, onSelect, loading, onClearFilters }: Props) {
  const [sortField, setSortField] = useState<SortField>("transaction_id");
  const [sortAsc, setSortAsc] = useState(true);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      setSortAsc(true);
    }
  };

  const sortedTransactions = [...transactions].sort((a, b) => {
    let valA = a[sortField] ?? "";
    let valB = b[sortField] ?? "";
    if (typeof valA === "number" && typeof valB === "number") {
      return sortAsc ? valA - valB : valB - valA;
    }
    return sortAsc
      ? String(valA).localeCompare(String(valB))
      : String(valB).localeCompare(String(valA));
  });

  if (loading) {
    return (
      <div className="b2b-card table-wrapper-card">
        <div className="table-calm-state">
          <p className="state-headline">Loading transactions</p>
          <p className="state-sub">Fetching latest payment records from ledger…</p>
        </div>
      </div>
    );
  }

  if (transactions.length === 0) {
    return (
      <div className="b2b-card table-wrapper-card" id="empty-transactions-view">
        <div className="table-calm-state">
          <p className="state-headline">No transactions match these filters</p>
          <p className="state-sub">Try broadening your search query or resetting active filter chips.</p>
          {onClearFilters && (
            <button className="btn-secondary-white" onClick={onClearFilters} style={{ marginTop: "12px" }}>
              Clear filters
            </button>
          )}
        </div>
      </div>
    );
  }

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

  const formatReason = (code: string) => {
    const map: Record<string, string> = {
      insufficient_funds: "Insufficient funds",
      customer_abandoned: "Checkout abandoned",
      account_closed: "Account closed",
      card_expired: "Card expired",
      wrong_otp: "Wrong OTP",
      bank_timeout: "Bank timeout",
      network_error: "Network error",
      daily_limit_exceeded: "Daily limit exceeded",
    };
    return map[code] || code.replace(/_/g, " ");
  };

  const formatChannel = (ch: string) => {
    const c = String(ch || "").toLowerCase();
    if (c === "whatsapp") return "WhatsApp";
    if (c === "sms") return "SMS";
    if (c === "email") return "Email";
    return ch;
  };

  return (
    <div className="b2b-card table-wrapper-card" id="transactions-ledger-table">
      <div className="table-responsive-box">
        <table className="b2b-dense-table">
          <thead>
            <tr>
              <th className="th-tx sortable" onClick={() => handleSort("transaction_id")}>
                <div className="th-content">
                  <span>Transaction</span>
                  <span className="sort-icon">{sortField === "transaction_id" ? (sortAsc ? "▲" : "▼") : "↕"}</span>
                </div>
              </th>
              <th className="th-customer">Customer</th>
              <th className="th-reason">Failure reason</th>
              <th className="th-channel">Channel</th>
              <th className="th-attempts sortable" onClick={() => handleSort("contact_attempts_so_far")}>
                <div className="th-content">
                  <span>Attempts</span>
                  <span className="sort-icon">{sortField === "contact_attempts_so_far" ? (sortAsc ? "▲" : "▼") : "↕"}</span>
                </div>
              </th>
              <th className="th-status sortable" onClick={() => handleSort("status")}>
                <div className="th-content">
                  <span>Status</span>
                  <span className="sort-icon">{sortField === "status" ? (sortAsc ? "▲" : "▼") : "↕"}</span>
                </div>
              </th>
              <th className="th-amount text-right sortable" onClick={() => handleSort("amount")}>
                <div className="th-content justify-end">
                  <span>Amount</span>
                  <span className="sort-icon">{sortField === "amount" ? (sortAsc ? "▲" : "▼") : "↕"}</span>
                </div>
              </th>
              <th className="th-action text-right">Action</th>
            </tr>
          </thead>
          <tbody>
            {sortedTransactions.map((tx) => (
              <tr
                key={tx.id}
                className="b2b-table-row"
                onClick={() => onSelect(tx)}
                tabIndex={0}
                onKeyDown={(e) => e.key === "Enter" && onSelect(tx)}
                id={`transaction-row-${tx.id}`}
                aria-label={`View audit trail for transaction ${tx.transaction_id}`}
              >
                {/* Transaction ID */}
                <td className="td-tx">
                  <div className="tx-cell-b2b">
                    <span className="tx-code-mono">{tx.transaction_id}</span>
                    <span className="tx-sub-label">{tx.description || tx.type.replace(/_/g, " ")}</span>
                  </div>
                </td>

                {/* Customer */}
                <td className="td-customer">
                  <div className="customer-cell-b2b">
                    <span className="cust-id-bold">{tx.customer_id}</span>
                    <span className="cust-contact-muted">{tx.customer_email || tx.customer_phone || "—"}</span>
                  </div>
                </td>

                {/* Failure Reason */}
                <td className="td-reason">
                  <span className="reason-label-text">{formatReason(tx.failure_reason_code)}</span>
                </td>

                {/* Channel */}
                <td className="td-channel">
                  <span className="channel-label-text">{formatChannel(tx.customer_channel_pref)}</span>
                </td>

                {/* Attempts */}
                <td className="td-attempts">
                  <span className="attempts-count-text tabular">{tx.contact_attempts_so_far} / 3</span>
                </td>

                {/* Status Pill */}
                <td className="td-status">{getStatusPill(tx.status)}</td>

                {/* Amount (Right-aligned, Tabular) */}
                <td className="td-amount text-right">
                  <span className="amount-val-tabular tabular">{formatINR(tx.amount)}</span>
                </td>

                {/* Action View */}
                <td className="td-action text-right">
                  <button
                    className="row-view-action"
                    onClick={(e) => {
                      e.stopPropagation();
                      onSelect(tx);
                    }}
                    tabIndex={-1}
                  >
                    View
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* ── Pagination Footer Summary ── */}
      <div className="table-pagination-footer">
        <span className="pagination-count-text">
          Showing 1 to {sortedTransactions.length} of {sortedTransactions.length} transactions
        </span>

        <div className="pagination-controls">
          <button className="btn-page disabled" disabled>Previous</button>
          <span className="page-current-num">1</span>
          <button className="btn-page disabled" disabled>Next</button>
        </div>
      </div>
    </div>
  );
}
