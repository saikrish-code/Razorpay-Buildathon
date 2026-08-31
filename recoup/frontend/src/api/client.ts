/**
 * api/client.ts
 * Axios instance pre-configured to hit the backend.
 * In development, Vite proxies /api → http://localhost:8000.
 * In production, set VITE_API_BASE_URL to the deployed backend URL.
 */

import axios from "axios";

const baseURL = import.meta.env.VITE_API_BASE_URL ?? "";

const apiClient = axios.create({
  baseURL,
  headers: {
    "Content-Type": "application/json",
  },
  timeout: 15_000,
});

export default apiClient;

// ── Typed helper functions ────────────────────────────────────────────────────

import type { AuditLog, HealthResponse, Transaction } from "../types";

export const api = {
  health: {
    get: () => apiClient.get<HealthResponse>("/api/health").then((r) => r.data),
  },

  transactions: {
    list: (skip = 0, limit = 100) =>
      apiClient
        .get<Transaction[]>("/api/transactions", { params: { skip, limit } })
        .then((r) => r.data),

    getById: (id: number) =>
      apiClient.get<Transaction>(`/api/transactions/${id}`).then((r) => r.data),

    auditLogs: (id: number) =>
      apiClient
        .get<AuditLog[]>(`/api/transactions/${id}/audit-logs`)
        .then((r) => r.data),
  },
};
