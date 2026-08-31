/**
 * pages/Transactions.tsx
 * Full transaction list with modal detail/audit-trail overlay.
 */

import { useEffect, useState } from "react";
import { api } from "../api/client";
import TransactionDetailModal from "../components/TransactionDetailModal";
import TransactionTable from "../components/TransactionTable";
import type { Transaction } from "../types";
import "./Transactions.css";

export default function Transactions() {
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [selected, setSelected] = useState<Transaction | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.transactions
      .list()
      .then(setTransactions)
      .catch(() => setError("Failed to load transactions. Is the backend running?"))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="transactions-page">
      <div className="page-header">
        <h1 className="page-title">Transactions</h1>
        <p className="page-subtitle">
          Click any row to view details and the audit trail.
        </p>
      </div>

      {error && <div className="error-banner">{error}</div>}

      <TransactionTable
        transactions={transactions}
        onSelect={setSelected}
        loading={loading}
      />

      <TransactionDetailModal
        transaction={selected}
        onClose={() => setSelected(null)}
      />
    </div>
  );
}
