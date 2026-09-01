/**
 * types/index.ts
 * Shared TypeScript interfaces mirroring backend Pydantic schemas.
 */

export type TransactionStatus =
  | "open"
  | "pending"
  | "success"
  | "failed"
  | "refunded"
  | "recovered"
  | "unrecoverable"
  | "pending_compliance_review";

export type AuditAction =
  | "created"
  | "updated"
  | "flagged"
  | "reviewed"
  | "resolved"
  | "contact_attempted";

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
  created_at: string;
  updated_at: string;
  audit_logs?: AuditLog[];
}

export interface AuditLog {
  id: number;
  transaction_id: number;
  action: AuditAction;
  actor: string | null;
  notes: string | null;
  created_at: string;
}

export interface FailureReasonStat {
  count: number;
  at_risk: number;
  recovered_count: number;
  recovered_amt: number;
  category: string;
}

export interface CategoryStat {
  count: number;
  at_risk: number;
  recovered_count: number;
  recovered_amt: number;
}

export interface ChannelStat {
  count: number;
  at_risk: number;
  recovered_count: number;
  recovered_amt: number;
}

export interface ReportResponse {
  total_transactions: number;
  total_at_risk_amount: number;
  total_recovered_amount: number;
  amount_recovery_rate: number;
  count_recovered: number;
  count_unrecoverable: number;
  count_pending: number;
  count_blocked_by_guardrail: number;
  volume_recovery_rate: number;
  by_failure_reason: Record<string, FailureReasonStat>;
  by_category: Record<string, CategoryStat>;
  by_channel: Record<string, ChannelStat>;
  generated_at: string;
}

export interface RunBatchResponse {
  status: string;
  message: string;
  processed_count: number;
  report: ReportResponse;
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

export interface TransactionFilterParams {
  status?: string;
  failure_reason_code?: string;
  type?: string;
  channel?: string;
  min_amount?: number;
  max_amount?: number;
  search?: string;
  skip?: number;
  limit?: number;
}
