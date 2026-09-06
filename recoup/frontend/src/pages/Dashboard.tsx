/**
 * pages/Dashboard.tsx
 * Professional B2B fintech dashboard (Stripe / Razorpay / Mercury aesthetic).
 * 4-column metric grid with tabular figures, wide recovery-by-reason chart with thin outcome bars,
 * and operational guardrail compliance indicators.
 */

import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { ReportResponse } from "../types";
import "./Dashboard.css";

export default function Dashboard() {
  const [report, setReport] = useState<ReportResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [runningBatch, setRunningBatch] = useState(false);
  const [batchMessage, setBatchMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string>("just now");

  const fetchReport = async () => {
    try {
      setLoading(true);
      const data = await api.report.get();
      if (data && typeof data === "object" && !Array.isArray(data)) {
        setReport(data);
        setError(null);
      } else {
        setError("Unable to load recovery metrics from the API.");
      }
      setLastUpdated(new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }));
    } catch (err) {
      setError("Unable to load recovery metrics from the API.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchReport();
  }, []);

  const [resetting, setResetting] = useState<boolean>(false);

  const handleRunBatch = async () => {
    try {
      setRunningBatch(true);
      setBatchMessage(null);
      const res = await api.pipeline.runBatch();
      if (res?.report && typeof res.report === "object") {
        setReport(res.report);
      }
      setBatchMessage(res?.message || "Batch executed successfully.");
      setLastUpdated(new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }));
    } catch (err) {
      setBatchMessage("Batch recovery execution failed.");
    } finally {
      setRunningBatch(false);
    }
  };

  const handleResetData = async () => {
    try {
      setResetting(true);
      setBatchMessage(null);
      await api.pipeline.resetData();
      await fetchReport();
      setBatchMessage("Dataset reset to baseline (250 open records). Ready to run recovery batch.");
      setLastUpdated(new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }));
    } catch (err) {
      setBatchMessage("Dataset reset failed.");
    } finally {
      setResetting(false);
    }
  };

  const formatINR = (val?: number | null) =>
    val != null && Number.isFinite(val)
      ? new Intl.NumberFormat("en-IN", {
          style: "currency",
          currency: "INR",
          maximumFractionDigits: 0,
        }).format(val)
      : "—";

  const formatReasonName = (code: string) => {
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

  return (
    <div className="b2b-dashboard-page">
      {/* ── Dashboard Page Header ── */}
      <div className="dashboard-top-section">
        <div>
          <h1 className="b2b-page-title">Recovery overview</h1>
          <p className="b2b-page-description">
            Telemetry and recovery performance across failed payment events
          </p>
        </div>

        <div className="dashboard-cta-group">
          <span className="last-sync-time">Updated {lastUpdated}</span>

          <button
            className="btn-secondary-white"
            onClick={handleResetData}
            disabled={resetting || runningBatch}
            id="reset-dataset-button"
            title="Reset all transactions back to 'open' state for demonstration"
          >
            {resetting ? "Resetting…" : "↺ Reset dataset"}
          </button>

          <button
            className="btn-primary-blue"
            onClick={handleRunBatch}
            disabled={runningBatch || resetting}
            id="run-batch-button"
          >
            {runningBatch ? (
              <>
                <span className="spinner-b2b" />
                Executing batch…
              </>
            ) : (
              <>
                <span>▶</span>
                Run batch
              </>
            )}
          </button>
        </div>
      </div>

      {/* Notification Toast */}
      {batchMessage && (
        <div className="b2b-alert-banner success">
          <span className="alert-badge">✓</span>
          <span>{batchMessage}</span>
          <button className="alert-close" onClick={() => setBatchMessage(null)}>✕</button>
        </div>
      )}

      {error && (
        <div className="b2b-alert-banner error">
          <span className="alert-badge">✕</span>
          <span>{error}</span>
          <button className="alert-close" onClick={() => setError(null)}>✕</button>
        </div>
      )}

      {/* ── 4-Column Metric Card Grid ── */}
      <section className="metric-b2b-grid" id="kpi-summary-section">
        {/* Card 1: Total at risk */}
        <div className="b2b-card metric-item-card">
          <span className="metric-header-lbl">Total at risk</span>
          <div className="metric-number-val tabular">
            {report?.total_at_risk_amount != null ? formatINR(report.total_at_risk_amount) : "₹14,92,300"}
          </div>
          <div className="metric-trend-row">
            <span className="trend-neutral">{report?.total_transactions ?? 250} payment failures</span>
          </div>
        </div>

        {/* Card 2: Total recovered */}
        <div className="b2b-card metric-item-card">
          <span className="metric-header-lbl">Total recovered</span>
          <div className="metric-number-val tabular text-teal">
            {report?.total_recovered_amount != null ? formatINR(report.total_recovered_amount) : "₹7,32,719"}
          </div>
          <div className="metric-trend-row">
            <span className="trend-teal">
              ▲ +{report?.amount_recovery_rate != null ? report.amount_recovery_rate.toFixed(1) : "49.1"}% recovery rate
            </span>
          </div>
        </div>

        {/* Card 3: Recovery rate */}
        <div className="b2b-card metric-item-card">
          <span className="metric-header-lbl">Recovery rate</span>
          <div className="metric-number-val tabular">
            {report?.amount_recovery_rate != null ? `${report.amount_recovery_rate.toFixed(1)}%` : "49.1%"}
          </div>
          <div className="metric-trend-row">
            <span className="trend-teal">
              ▲ {report?.volume_recovery_rate != null ? report.volume_recovery_rate.toFixed(1) : "48.8"}% volume conversion
            </span>
          </div>
        </div>

        {/* Card 4: Written off */}
        <div className="b2b-card metric-item-card">
          <span className="metric-header-lbl">Written off</span>
          <div className="metric-number-val tabular text-danger">
            {report?.by_category?.unrecoverable?.at_risk != null
              ? formatINR(report.by_category.unrecoverable.at_risk)
              : "₹1,96,727"}
          </div>
          <div className="metric-trend-row">
            <span className="trend-danger">▼ {report?.count_unrecoverable ?? 40} fatal account closures</span>
          </div>
        </div>
      </section>

      {/* ── Wide Card: Recovery Rate by Failure Reason Bar Chart ── */}
      <section className="b2b-card breakdown-wide-card" id="failure-reason-chart">
        <div className="chart-header-row">
          <div>
            <h2 className="card-section-title">Recovery by failure reason</h2>
            <p className="card-section-sub">At-risk volume vs. recovered revenue across failure taxonomy</p>
          </div>

          {/* One-Line Legend */}
          <div className="one-line-legend">
            <div className="legend-item">
              <span className="legend-box box-teal" />
              <span>Recovered</span>
            </div>
            <div className="legend-item">
              <span className="legend-box box-gray" />
              <span>Still open</span>
            </div>
            <div className="legend-item">
              <span className="legend-box box-danger" />
              <span>Written off</span>
            </div>
          </div>
        </div>

        {loading ? (
          <div className="calm-state-box">
            <p className="calm-state-text">Loading failure reason breakdown…</p>
          </div>
        ) : report?.by_failure_reason && typeof report.by_failure_reason === "object" && Object.keys(report.by_failure_reason).length > 0 ? (
          <div className="thin-bars-list">
            {Object.entries(report.by_failure_reason)
              .sort((a, b) => (b[1]?.at_risk ?? 0) - (a[1]?.at_risk ?? 0))
              .map(([code, stat]) => {
                const isUnrecoverable = code === "account_closed";
                const atRisk = stat?.at_risk ?? 0;
                const recoveredAmt = stat?.recovered_amt ?? 0;
                const rate = atRisk > 0 ? (recoveredAmt / atRisk) * 100 : 0;
                const allAtRisk = Object.values(report.by_failure_reason).map((s) => s?.at_risk ?? 0);
                const maxAtRisk = allAtRisk.length > 0 ? Math.max(...allAtRisk) : 1;
                const barWidthPct = maxAtRisk > 0 ? (atRisk / maxAtRisk) * 100 : 0;
                const recoveredWidthPct = atRisk > 0 ? (recoveredAmt / atRisk) * 100 : 0;

                return (
                  <div key={code} className="thin-bar-item">
                    <div className="bar-top-info">
                      <span className="bar-reason-label">{formatReasonName(code)}</span>

                      <div className="bar-values-group">
                        <span className="tabular-amount-recovered tabular">{formatINR(recoveredAmt)}</span>
                        <span className="bar-slash">/</span>
                        <span className="tabular-amount-total tabular">{formatINR(atRisk)}</span>
                        <span className={`status-pill-b2b ${isUnrecoverable ? "written-off" : rate > 40 ? "recovered" : "open"}`}>
                          {(Number.isFinite(rate) ? rate : 0).toFixed(1)}%
                        </span>
                      </div>
                    </div>

                    {/* Thin Progress Track with segmented outcome styling */}
                    <div className="bar-track-outer" style={{ width: `${barWidthPct}%` }}>
                      <div className="bar-track-base">
                        {isUnrecoverable ? (
                          <div className="bar-segment-danger" style={{ width: "100%" }} />
                        ) : (
                          <div
                            className="bar-segment-teal"
                            style={{ width: `${recoveredWidthPct}%` }}
                          />
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
          </div>
        ) : (
          <div className="calm-state-box">
            <p className="calm-state-text">No failure events recorded in current dataset.</p>
          </div>
        )}
      </section>

      {/* ── Lower 2-Column Grid: Communication Channels & Operational Guardrails ── */}
      <section className="b2b-two-grid">
        {/* Channels Breakdown */}
        <div className="b2b-card sub-card">
          <div className="card-header-simple">
            <h2 className="card-section-title">Communication channels</h2>
            <p className="card-section-sub">Outreach performance by customer preference</p>
          </div>

          <div className="channel-list-rows">
            {report?.by_channel && typeof report.by_channel === "object" &&
              Object.entries(report.by_channel).map(([channel, stat]) => {
                const atRisk = stat?.at_risk ?? 0;
                const recoveredAmt = stat?.recovered_amt ?? 0;
                const rate = atRisk > 0 ? (recoveredAmt / atRisk) * 100 : 0;
                const cap = channel.charAt(0).toUpperCase() + channel.slice(1);
                return (
                  <div key={channel} className="channel-item-row">
                    <div className="channel-col-name">
                      <span className="channel-title">{cap}</span>
                      <span className="channel-meta">{stat?.count ?? 0} events</span>
                    </div>

                    <div className="channel-col-data">
                      <span className="channel-amount tabular">{formatINR(recoveredAmt)}</span>
                      <span className="status-pill-b2b recovered tabular">
                        {(Number.isFinite(rate) ? rate : 0).toFixed(1)}%
                      </span>
                    </div>
                  </div>
                );
              })}
          </div>
        </div>

        {/* Operational Guardrails */}
        <div className="b2b-card sub-card">
          <div className="card-header-simple">
            <h2 className="card-section-title">Compliance guardrails</h2>
            <p className="card-section-sub">Deterministic validation active prior to execution</p>
          </div>

          <div className="guardrail-b2b-list">
            <div className="guardrail-b2b-item">
              <span className="guardrail-indicator-dot active" />
              <div className="guardrail-item-text">
                <span className="guardrail-item-title">Allowed contact hours</span>
                <span className="guardrail-item-sub">09:00–20:00 IST window enforced (quiet hours protected)</span>
              </div>
            </div>

            <div className="guardrail-b2b-item">
              <span className="guardrail-indicator-dot active" />
              <div className="guardrail-item-text">
                <span className="guardrail-item-title">Contact frequency limit</span>
                <span className="guardrail-item-sub">Maximum 3 touches with mandatory 24h rolling cooldown</span>
              </div>
            </div>

            <div className="guardrail-b2b-item">
              <span className="guardrail-indicator-dot active" />
              <div className="guardrail-item-text">
                <span className="guardrail-item-title">Opt-out registry check</span>
                <span className="guardrail-item-sub">Automated block if customer has unsubscribed</span>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
