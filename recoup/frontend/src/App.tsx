/**
 * App.tsx
 * Root component — sets up routing and the persistent navigation bar.
 */

import { NavLink, Route, BrowserRouter as Router, Routes } from "react-router-dom";
import "./App.css";
import Dashboard from "./pages/Dashboard";
import Transactions from "./pages/Transactions";

export default function App() {
  return (
    <Router>
      <div className="app-shell">
        {/* Top navigation bar */}
        <nav className="navbar" id="main-nav">
          <div className="nav-brand">
            <span className="brand-logo">⚡</span>
            <span className="brand-name">recoup</span>
          </div>
          <div className="nav-links">
            <NavLink
              to="/"
              end
              className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}
              id="nav-dashboard"
            >
              Dashboard
            </NavLink>
            <NavLink
              to="/transactions"
              className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}
              id="nav-transactions"
            >
              Transactions
            </NavLink>
          </div>
        </nav>

        {/* Page content */}
        <main className="main-content">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/transactions" element={<Transactions />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}
