/**
 * api/client.ts
 * Axios instance and typed helpers for Recoup AI endpoints.
 */

import axios from "axios";
import type {
  AuditLog,
  HealthResponse,
  ReportResponse,
  RunBatchResponse,
  Transaction,
  TransactionFilterParams,
} from "../types";

const baseURL = import.meta.env.VITE_API_BASE_URL ?? "";

const apiClient = axios.create({
  baseURL,
  headers: {
    "Content-Type": "application/json",
  },
  timeout: 30_000,
});

export default apiClient;

// ── Typed API Helpers ─────────────────────────────────────────────────────────

export const api = {
  health: {
    get: () => apiClient.get<HealthResponse>("/api/health").then((r) => r.data),
  },

  report: {
    get: () => apiClient.get<ReportResponse>("/api/report").then((r) => r.data),
  },

  pipeline: {
    runBatch: (limit?: number, random_seed: number = 42) =>
      apiClient
        .post<RunBatchResponse>("/api/run-batch", { limit, random_seed })
        .then((r) => r.data),
  },

  transactions: {
    list: (params?: TransactionFilterParams) =>
      apiClient
        .get<Transaction[]>("/api/transactions", { params: { limit: 100, ...params } })
        .then((r) => r.data),

    getById: (identifier: string | number) =>
      apiClient
        .get<Transaction>(`/api/transactions/${identifier}`)
        .then((r) => r.data),

    auditLogs: (identifier: string | number) =>
      apiClient
        .get<AuditLog[]>(`/api/transactions/${identifier}/audit-logs`)
        .then((r) => r.data),
  },
};
