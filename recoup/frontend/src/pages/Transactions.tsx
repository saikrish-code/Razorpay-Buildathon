/**
 * pages/Transactions.tsx
 * Professional B2B fintech transactions ledger with compact dropdown filter chips,
 * dense tabular data rows, pagination bar, and slide-over audit stepper.
 */

import { useEffect, useState } from "react";
import { api } from "../api/client";
import TransactionDetailModal from "../components/TransactionDetailModal";
import TransactionTable from "../components/TransactionTable";
import type { Transaction, TransactionFilterParams } from "../types";
import "./Transactions.css";

const STATUS_OPTIONS = [
  { label: "All statuses", value: "" },
  { label: "Recovered", value: "recovered" },
  { label: "Open", value: "open" },
  { label: "Written off", value: "unrecoverable" },
  { label: "Needs review", value: "pending_compliance_review" },
];

const FAILURE_REASON_OPTIONS = [
  { label: "All failure reasons", value: "" },
  { label: "Insufficient funds", value: "insufficient_funds" },
  { label: "Checkout abandoned", value: "customer_abandoned" },
  { label: "Account closed", value: "account_closed" },
  { label: "Card expired", value: "card_expired" },
  { label: "Wrong OTP", value: "wrong_otp" },
  { label: "Bank timeout", value: "bank_timeout" },
  { label: "Network error", value: "network_error" },
  { label: "Daily limit exceeded", value: "daily_limit_exceeded" },
];

const CHANNEL_OPTIONS = [
  { label: "All channels", value: "" },
  { label: "WhatsApp", value: "whatsapp" },
  { label: "SMS", value: "sms" },
  { label: "Email", value: "email" },
];

export default function Transactions() {
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [selected, setSelected] = useState<Transaction | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters State
  const [statusFilter, setStatusFilter] = useState("");
  const [reasonFilter, setReasonFilter] = useState("");
  const [channelFilter, setChannelFilter] = useState("");
  const [searchQuery, setSearchQuery] = useState("");

  const fetchTransactions = async () => {
    try {
      setLoading(true);
      setError(null);

      const params: TransactionFilterParams = {
        limit: 250,
      };

      if (statusFilter) params.status = statusFilter;
      if (reasonFilter) params.failure_reason_code = reasonFilter;
      if (channelFilter) params.channel = channelFilter;
      if (searchQuery.trim()) params.search = searchQuery.trim();

      const data = await api.transactions.list(params);
      if (Array.isArray(data)) {
        setTransactions(data);
      } else {
        setTransactions([]);
        setError("Unable to load transactions from backend server.");
      }
    } catch (err) {
      setError("Unable to load transactions from backend server.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTransactions();
  }, [statusFilter, reasonFilter, channelFilter]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    fetchTransactions();
  };

  const handleResetFilters = () => {
    setStatusFilter("");
    setReasonFilter("");
    setChannelFilter("");
    setSearchQuery("");
  };

  const hasActiveFilters = Boolean(statusFilter || reasonFilter || channelFilter || searchQuery);

  const totalFilteredAmount = transactions.reduce((acc, t) => acc + (t.amount || 0), 0);

  const formatINR = (val: number) =>
    new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 0,
    }).format(val);

  return (
    <div className="b2b-transactions-page">
      {/* ── Page Header ── */}
      <div className="transactions-header-row">
        <div>
          <h1 className="b2b-page-title">Transactions</h1>
          <p className="b2b-page-description">
            Audit ledger of failed payments, autonomous recovery workflows, and compliance checks
          </p>
        </div>

        <div className="b2b-ledger-summary">
          <span className="summary-count-lbl">{transactions.length} records</span>
          <span className="summary-dot-sep">·</span>
          <span className="summary-amount-lbl tabular">{formatINR(totalFilteredAmount)} total</span>
        </div>
      </div>

      {/* ── Compact Dropdown Chips Filter Bar ── */}
      <section className="b2b-card compact-filter-bar" id="transactions-filter-panel">
        <div className="filter-chips-row">
          {/* Status Dropdown Chip */}
          <div className="chip-dropdown-wrapper">
            <span className="chip-prefix">Status:</span>
            <select
              className="chip-select"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              id="status-filter-select"
            >
              {STATUS_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          {/* Failure Reason Dropdown Chip */}
          <div className="chip-dropdown-wrapper">
            <span className="chip-prefix">Reason:</span>
            <select
              className="chip-select"
              value={reasonFilter}
              onChange={(e) => setReasonFilter(e.target.value)}
              id="failure-reason-select"
            >
              {FAILURE_REASON_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          {/* Channel Dropdown Chip */}
          <div className="chip-dropdown-wrapper">
            <span className="chip-prefix">Channel:</span>
            <select
              className="chip-select"
              value={channelFilter}
              onChange={(e) => setChannelFilter(e.target.value)}
              id="channel-select"
            >
              {CHANNEL_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          {/* Search Box */}
          <form className="chip-search-form" onSubmit={handleSearchSubmit}>
            <input
              type="text"
              className="chip-search-input"
              placeholder="Search ID, customer, description…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              id="transaction-search-input"
            />
            {searchQuery && (
              <button
                type="button"
                className="chip-search-clear"
                onClick={() => {
                  setSearchQuery("");
                  setTimeout(fetchTransactions, 0);
                }}
              >
                ✕
              </button>
            )}
          </form>

          {/* Clear Filters Link */}
          {hasActiveFilters && (
            <button className="clear-filters-link" onClick={handleResetFilters} id="reset-filters-button">
              Clear filters
            </button>
          )}
        </div>
      </section>

      {error && <div className="b2b-alert-banner error">{error}</div>}

      {/* ── Dense Table & Pagination ── */}
      <TransactionTable
        transactions={transactions}
        onSelect={setSelected}
        loading={loading}
        onClearFilters={handleResetFilters}
      />

      {/* ── Slide-Over Detail Stepper ── */}
      <TransactionDetailModal
        transaction={selected}
        onClose={() => setSelected(null)}
      />
    </div>
  );
}
