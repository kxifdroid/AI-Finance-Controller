export interface BankTransaction {
  bank_txn_id: string;
  transaction_date: string;
  amount: number;
  description: string;
  reference: string;
  transaction_type: string;
  normalized_amount: number;
  normalized_date: string;
  normalized_ref: string;
  normalized_desc: string;
  created_at: string;
}

export interface GatewayTransaction {
  gateway_txn_id: string;
  transaction_date: string;
  amount: number;
  customer_name: string;
  payment_reference: string;
  status: string;
  gateway_fee?: number;
  tax_on_fee?: number;
  net_settlement?: number;
  normalized_amount: number;
  normalized_date: string;
  normalized_ref: string;
  normalized_customer: string;
  created_at: string;
}

export interface Invoice {
  invoice_id: string;
  invoice_date: string;
  customer_name: string;
  amount: number;
  invoice_reference: string;
  status: string;
  normalized_amount: number;
  normalized_date: string;
  normalized_ref: string;
  normalized_customer: string;
  created_at: string;
}

export interface AIInvestigation {
  investigation_id: string;
  exception_id: string;
  run_id: string;
  classification: string;
  confidence: number;
  explanation: string;
  evidence: string[] | Record<string, any>;
  recommendation: "MARK_RECONCILED" | "MANUAL_REVIEW" | "ESCALATE";
  requires_human_review: boolean;
  deterministic_override: boolean;
  override_reason?: string;
  policy_references?: string[];
  created_at: string;
}

export interface MatchRecord {
  match_id: string;
  run_id: string;
  topology?: "ONE_TO_ONE" | "MANY_TO_ONE" | "ONE_TO_MANY" | "ORPHAN";
  reason_code?: string | null;
  bank_txn_id: string | null;
  gateway_txn_id: string | null;
  invoice_id: string | null;
  primary_amount?: number;
  expected_amount?: number;
  settled_amount?: number;
  variance_amount?: number;
  amounts_json?: string | null;
  decision: "MATCH" | "REVIEW" | "EXCEPTION" | "DUPLICATE" | "MISSING";
  confidence_score: number;
  deterministic_confidence?: number;
  risk_level: "LOW" | "MEDIUM" | "HIGH";
  explanation: string;
  recommended_action: string;
  match_type?: string;
  evidence_json?: string;
  amount_similarity: number;
  date_similarity: number;
  reference_similarity: number;
  customer_similarity: number;
  composite_score: number;
  verified_by_ai: boolean;
  ai_verification_status?: string | null;
  ai_confidence?: number | null;
  ai_explanation?: string | null;
  ai_raw_response?: string | null;
  created_at: string;
  bank_transaction?: BankTransaction | null;
  gateway_transaction?: GatewayTransaction | null;
  invoice?: Invoice | null;
}

export interface TransactionDetail {
  match_id: string;
  decision: string;
  topology?: string;
  match_type?: string | null;
  reason_code?: string | null;
  confidence_score: number;
  deterministic_confidence?: number;
  risk_level: string;
  explanation: string;
  recommended_action: string;
  verified_by_ai: boolean;
  ai_verification_status?: string | null;
  ai_raw_response?: string | null;
  amounts?: {
    invoice_total?: number;
    gateway_gross_total?: number;
    gateway_fee_total?: number;
    gateway_tax_total?: number;
    gateway_net_total?: number;
    bank_credit_total?: number;
    variance?: number;
  } | null;
  fee_classification?: string | null;
  fee_breakdown_json?: string | null;
  features: {
    amount_similarity: number;
    date_similarity: number;
    reference_similarity: number;
    customer_similarity: number;
    composite_score: number;
  };
  bank_record?: BankTransaction | null;
  gateway_record?: GatewayTransaction | null;
  invoice_record?: Invoice | null;
  bank_transactions?: BankTransaction[];
  gateway_transactions?: GatewayTransaction[];
  invoice_transactions?: Invoice[];
  exception_record?: {
    exception_id: string;
    type: string;
    severity: string;
    amount_involved: number;
    amount_discrepancy: number;
    explanation: string;
    status: string;
  } | null;
  ai?: {
    status?: string | null;
    confidence?: number | null;
    explanation?: string | null;
    recommended_action?: string | null;
  } | null;
}

export interface ExceptionRecord {
  exception_id: string;
  run_id: string;
  bank_txn_id: string | null;
  gateway_txn_id: string | null;
  invoice_id: string | null;
  exception_type: string;
  severity: "HIGH" | "MEDIUM" | "LOW";
  amount_involved: number;
  amount_discrepancy: number;
  explanation: string;
  recommended_action: string;
  status: "OPEN" | "IN_REVIEW" | "RESOLVED" | "IGNORED";
  notes?: string | null;
  resolved_by?: string | null;
  evidence_json?: string;
  related_records_json?: string;
  investigation?: AIInvestigation;
  created_at: string;
  updated_at: string;
  bank_transaction?: BankTransaction | null;
  gateway_transaction?: GatewayTransaction | null;
  invoice?: Invoice | null;
}

export interface EvaluationBenchmark {
  has_evaluation: boolean;
  accuracy: number;
  precision: number;
  recall: number;
  f1_score: number;
  false_positive_rate: number;
  false_negative_rate: number;
  exception_detection_accuracy: number;
  true_positives: number;
  false_positives: number;
  false_negatives: number;
  true_negatives: number;
}

export interface MetricsSummary {
  has_run: boolean;
  run_id?: string;
  started_at?: string;
  completed_at?: string;
  total_records: number;
  total_source_records?: number;
  matched_count: number;
  review_count: number;
  exception_count: number;
  duplicate_count: number;
  missing_count: number;
  match_rate_pct: number;
  value_match_rate_pct?: number;
  exception_rate_pct: number;
  review_rate_pct: number;
  ai_escalation_rate_pct: number;
  ai_verified_count?: number;
  ai_failed_count?: number;
  processing_time_ms: number;
  throughput_rps: number;
  total_matched_volume: number;
  total_exception_volume: number;
  total_review_volume: number;
  settlement_variance_exposure?: number;
  batch_settlement_count?: number;
  duplicate_detection_count?: number;
  status_distribution: Array<{ name: string; value: number; color: string }>;
  exceptions_by_type: Array<{ type: string; count: number; amount: number }>;
  severity_distribution: Array<{ severity: string; count: number }>;
  evaluation?: EvaluationBenchmark | null;
}

export interface ForecastPoint {
  forecast_date: string;
  day_offset: number;
  cleared_cash: number;
  expected_settlements: number;
  expected_receivables: number;
  upcoming_payouts: number;
  recurring_expenses: number;
  projected_balance: number;
  confidence_level: string;
  assumptions_notes: string;
}

export interface CashForecastData {
  generated_at: string;
  current_cleared_cash: number;
  forecast_points: ForecastPoint[];
  methodology: string;
  limitations: string;
}

export interface ToolCall {
  tool_name: string;
  arguments: Record<string, any>;
  result_summary: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  isThinking?: boolean; // Optional: true when the AI is actively processing, false/undefined otherwise
  thought_process?: string[]; // Optional: array of strings for step-by-step reasoning
  tools_used?: ToolCall[];
  timestamp: string;
}

// ---------------------------------------------------------------------------
// Authentication Types
// ---------------------------------------------------------------------------

export interface AuthUser {
  id: string;
  email: string;
  name: string;
  role: string;
  auth_provider: string;
  avatar_url?: string | null;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: AuthUser;
}

