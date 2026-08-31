/**
 * types/index.ts
 * Shared TypeScript interfaces that mirror the backend Pydantic schemas.
 */

export type TransactionStatus = "open" | "pending" | "success" | "failed" | "refunded" | "recovered" | "unrecoverable";
export type AuditAction = "created" | "updated" | "flagged" | "reviewed" | "resolved" | "contact_attempted";

export interface Transaction {
  id: number;
  transaction_id: string;
  razorpay_payment_id?: string | null;
  customer_id: string;
  type: string;
  amount: number;
  currency: string;
  event_type: string;
  failure_reason_code: string;
  contact_attempts_so_far: number;
  customer_channel_pref: string;
  status: string;
  customer_email?: string | null;
  customer_phone?: string | null;
  description?: string | null;
  timestamp?: string | null;
  created_at: string; // ISO 8601
  updated_at: string;
}

export interface AuditLog {
  id: number;
  transaction_id: number;
  action: AuditAction;
  actor: string | null;
  notes: string | null;
  created_at: string;
}

export interface PolicyDocument {
  id: number;
  title: string;
  content: string;
  version: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface HealthResponse {
  status: string;
  app: string;
  version: string;
}
