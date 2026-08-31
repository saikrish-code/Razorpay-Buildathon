/**
 * types/index.ts
 * Shared TypeScript interfaces that mirror the backend Pydantic schemas.
 */

export type TransactionStatus = "pending" | "success" | "failed" | "refunded";
export type AuditAction = "created" | "updated" | "flagged" | "reviewed" | "resolved";

export interface Transaction {
  id: number;
  razorpay_payment_id: string;
  amount: number;
  currency: string;
  status: TransactionStatus;
  customer_email: string | null;
  customer_phone: string | null;
  description: string | null;
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
