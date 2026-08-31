/**
 * pages/Dashboard.tsx
 * Landing page showing system health and high-level stats.
 */

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { HealthResponse } from "../types";
import "./Dashboard.css";

export default function Dashboard() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.health
      .get()
      .then(setHealth)
      .catch(() => setError("Backend unreachable. Is the FastAPI server running?"));
  }, []);

  return (
    <div className="dashboard-page">
      {/* Hero */}
      <header className="dashboard-hero">
        <div className="hero-badge">Razorpay Buildathon</div>
        <h1 className="hero-title">
          <span className="gradient-text">recoup</span>
        </h1>
        <p className="hero-subtitle">
          AI-powered revenue recovery — flag failed payments, recover revenue, stay compliant.
        </p>
        <Link to="/transactions" className="hero-cta" id="go-to-transactions">
          View Transactions →
        </Link>
      </header>

      {/* API health card */}
      <section className="dashboard-cards">
        <div className="stat-card" id="api-health-card">
          <div className="stat-icon">🟢</div>
          <div>
            <p className="stat-label">API Status</p>
            {health ? (
              <p className="stat-value">
                {health.status} · v{health.version}
              </p>
            ) : error ? (
              <p className="stat-value error-text">{error}</p>
            ) : (
              <p className="stat-value muted-text">Checking…</p>
            )}
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon">🔍</div>
          <div>
            <p className="stat-label">RAG Retrieval</p>
            <p className="stat-value muted-text">Not implemented yet</p>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon">🤖</div>
          <div>
            <p className="stat-label">AI Agent</p>
            <p className="stat-value muted-text">Not implemented yet</p>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon">🛡️</div>
          <div>
            <p className="stat-label">Guardrails</p>
            <p className="stat-value muted-text">Not implemented yet</p>
          </div>
        </div>
      </section>
    </div>
  );
}
