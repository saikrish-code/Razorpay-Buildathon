/**
 * App.tsx
 * Recoup B2B fintech dashboard shell (Stripe / Razorpay / Mercury aesthetic).
 * Fixed ~220px white left sidebar, active 2px accent-blue left border,
 * top bar with breadcrumb title, "Test mode" amber badge, search, and user avatar.
 */

import { NavLink, Route, BrowserRouter as Router, Routes, useLocation } from "react-router-dom";
import "./App.css";
import { RecoupLogo } from "./components/Logo";
import Dashboard from "./pages/Dashboard";
import Transactions from "./pages/Transactions";

function TopBar() {
  const location = useLocation();
  const pageTitle = location.pathname.startsWith("/transactions") ? "Transactions" : "Dashboard";

  return (
    <header className="b2b-topbar">
      {/* Breadcrumb Title */}
      <div className="topbar-breadcrumb">
        <span className="breadcrumb-root">Recoup</span>
        <span className="breadcrumb-sep">/</span>
        <span className="breadcrumb-current">{pageTitle}</span>
      </div>

      {/* Right Controls: Test Mode Badge, Search, User Avatar */}
      <div className="topbar-right-controls">
        {/* Razorpay-style Test Mode Amber Badge */}
        <div className="test-mode-badge" title="Simulated recovery batch data active">
          <span className="test-mode-dot" />
          <span>Test mode</span>
        </div>

        {/* Global Compact Search */}
        <div className="topbar-search-box">
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <circle cx="7" cy="7" r="5" />
            <line x1="11" y1="11" x2="15" y2="15" />
          </svg>
          <input
            type="text"
            className="topbar-search-input"
            placeholder="Search transactions, customers…"
          />
        </div>

        {/* User Profile Avatar */}
        <div className="user-avatar-pill" title="Merchant Account (Test)">
          <span className="avatar-initials">SK</span>
        </div>
      </div>
    </header>
  );
}

export default function App() {
  return (
    <Router>
      <div className="b2b-layout-shell">
        {/* ── Left Sidebar Navigation (~220px) ── */}
        <aside className="b2b-sidebar" id="main-sidebar">
          {/* Logo Header */}
          <div className="sidebar-logo-header">
            <RecoupLogo size={24} />
          </div>

          {/* Navigation Links (Active item has 2px accent-blue left border) */}
          <nav className="sidebar-nav-group">
            <NavLink
              to="/"
              end
              className={({ isActive }) => (isActive ? "b2b-nav-item active" : "b2b-nav-item")}
              id="nav-dashboard"
            >
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <rect x="2" y="2" width="5" height="5" rx="1" />
                <rect x="9" y="2" width="5" height="5" rx="1" />
                <rect x="2" y="9" width="5" height="5" rx="1" />
                <rect x="9" y="9" width="5" height="5" rx="1" />
              </svg>
              <span>Dashboard</span>
            </NavLink>

            <NavLink
              to="/transactions"
              className={({ isActive }) => (isActive ? "b2b-nav-item active" : "b2b-nav-item")}
              id="nav-transactions"
            >
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M2.5 4h11M2.5 8h11M2.5 12h7" />
              </svg>
              <span>Transactions</span>
            </NavLink>

            <a
              href="http://localhost:8000/api/docs"
              target="_blank"
              rel="noreferrer"
              className="b2b-nav-item"
              id="nav-api-settings"
            >
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <circle cx="8" cy="8" r="2.5" />
                <path d="M13.2 10.4a1 1 0 0 0 .15 1.15l.15.15a1.2 1.2 0 1 1-1.7 1.7l-.15-.15a1 1 0 0 0-1.15-.15 1 1 0 0 0-.6.9V14.5a1.2 1.2 0 1 1-2.4 0v-.35a1 1 0 0 0-.6-.9 1 1 0 0 0-1.15.15l-.15.15a1.2 1.2 0 1 1-1.7-1.7l.15-.15a1 1 0 0 0 .15-1.15 1 1 0 0 0-.9-.6H2.5a1.2 1.2 0 1 1 0-2.4h.35a1 1 0 0 0 .9-.6 1 1 0 0 0-.15-1.15l-.15-.15a1.2 1.2 0 1 1 1.7-1.7l.15.15a1 1 0 0 0 1.15.15 1 1 0 0 0 .6-.9V1.5a1.2 1.2 0 1 1 2.4 0v.35a1 1 0 0 0 .6.9 1 1 0 0 0 1.15-.15l.15-.15a1.2 1.2 0 1 1 1.7 1.7l-.15.15a1 1 0 0 0-.15 1.15 1 1 0 0 0 .9.6h.35a1.2 1.2 0 1 1 0 2.4h-.35a1 1 0 0 0-.9.6z" />
              </svg>
              <span>API settings</span>
            </a>
          </nav>

          {/* Sidebar Footer */}
          <div className="sidebar-footer-b2b">
            <div className="merchant-info-pill">
              <span className="merchant-name">Razorpay Sandbox</span>
              <span className="merchant-id">MID: rzp_test_01</span>
            </div>
          </div>
        </aside>

        {/* ── Main Viewport Canvas ── */}
        <div className="b2b-main-wrapper">
          <TopBar />

          <main className="b2b-content-canvas">
            <div className="content-inner-container">
              <Routes>
                <Route
                  path="/"
                  element={
                    <div className="page-wrapper">
                      <Dashboard />
                    </div>
                  }
                />
                <Route
                  path="/transactions"
                  element={
                    <div className="page-wrapper">
                      <Transactions />
                    </div>
                  }
                />
              </Routes>
            </div>
          </main>
        </div>
      </div>
    </Router>
  );
}
