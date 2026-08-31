/**
 * pages/Dashboard.tsx
 * Fintech-style landing page with balance overview, stats, and module status.
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

  const isOnline = health?.status === "ok";

  return (
    <div className="dashboard-page">
      {/* Welcome */}
      <header className="dashboard-welcome">
        <div className="welcome-left">
          <p className="welcome-label">Welcome back</p>
          <h1 className="welcome-title">
            <span className="gradient-text">recoup</span>
          </h1>
          <p className="welcome-subtitle">
            AI-powered revenue recovery — flag failed payments, recover revenue, stay compliant.
          </p>
        </div>
        <Link to="/transactions" className="hero-cta" id="go-to-transactions">
          <span className="cta-icon">→</span>
          View Transactions
        </Link>
      </header>

      {/* Balance / Recovery Overview Card */}
      <section className="overview-row">
        <div className="balance-card card-accent">
          <div className="balance-card-inner">
            <p className="balance-label">Recovery Available</p>
            <h2 className="balance-amount">₹ 0.00</h2>
            <p className="balance-note">No failed transactions yet</p>
          </div>
        </div>

        <div className="stats-column">
          <div className="stat-row-item">
            <span className="stat-row-label">Failed Payments</span>
            <span className="stat-row-value">₹ 0.00</span>
          </div>
          <div className="stat-row-divider" />
          <div className="stat-row-item">
            <span className="stat-row-label">Recovered</span>
            <span className="stat-row-value success-text">₹ 0.00</span>
          </div>
          <div className="stat-row-divider" />
          <div className="stat-row-item">
            <span className="stat-row-label">Pending Review</span>
            <span className="stat-row-value warning-text">0</span>
          </div>
        </div>
      </section>

      {/* Quick Action Buttons */}
      <section className="actions-row">
        <Link to="/transactions" className="action-btn">
          <div className="action-icon">📋</div>
          <span className="action-label">View</span>
          <span className="action-sublabel">Transactions</span>
        </Link>
        <div className="action-btn disabled">
          <div className="action-icon">🔄</div>
          <span className="action-label">Retry</span>
          <span className="action-sublabel">Payment</span>
        </div>
        <div className="action-btn disabled">
          <div className="action-icon">📊</div>
          <span className="action-label">View</span>
          <span className="action-sublabel">Reports</span>
        </div>
      </section>

      {/* Module status cards */}
      <section className="module-section">
        <h3 className="section-heading">System Status</h3>
        <div className="module-grid">
          <div className="module-card" id="api-health-card">
            <div className="module-header">
              <div className={`module-dot ${isOnline ? "online" : error ? "offline" : "loading"}`} />
              <span className="module-name">API Server</span>
            </div>
            {health ? (
              <p className="module-status-text">
                {health.status} · v{health.version}
              </p>
            ) : error ? (
              <p className="module-status-text error-text">{error}</p>
            ) : (
              <p className="module-status-text muted-text">Checking…</p>
            )}
            <div className="module-progress-bar">
              <div
                className="module-progress-fill"
                style={{ width: isOnline ? "100%" : error ? "0%" : "50%" }}
              />
            </div>
          </div>

          <div className="module-card">
            <div className="module-header">
              <div className="module-dot pending" />
              <span className="module-name">RAG Retrieval</span>
            </div>
            <p className="module-status-text muted-text">Not configured</p>
            <div className="module-progress-bar">
              <div className="module-progress-fill" style={{ width: "0%" }} />
            </div>
          </div>

          <div className="module-card">
            <div className="module-header">
              <div className="module-dot pending" />
              <span className="module-name">AI Agent</span>
            </div>
            <p className="module-status-text muted-text">Not configured</p>
            <div className="module-progress-bar">
              <div className="module-progress-fill" style={{ width: "0%" }} />
            </div>
          </div>

          <div className="module-card">
            <div className="module-header">
              <div className="module-dot pending" />
              <span className="module-name">Guardrails</span>
            </div>
            <p className="module-status-text muted-text">Not configured</p>
            <div className="module-progress-bar">
              <div className="module-progress-fill" style={{ width: "0%" }} />
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
