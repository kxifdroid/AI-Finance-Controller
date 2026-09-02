"use client";

import { useEffect, useState } from "react";
import { 
  X, 
  Building2, 
  CreditCard, 
  FileText,
  Sparkles,
  Receipt,
  Layers,
  ChevronDown,
  ChevronUp,
  AlertTriangle,
  CheckCircle2,
  ExternalLink
} from "lucide-react";
import { TransactionDetail } from "@/types";
import { fetchTransactionDetail } from "@/lib/api";
import { 
  StatusBadge, 
  RiskBadge, 
  MatchTypeTag, 
  DecisionBanner, 
  EvidenceSignal 
} from "@/components/ui-kit";
import { formatCurrency, formatDate, formatPercent, cleanId, cn } from "@/lib/utils";

interface MatchDetailModalProps {
  matchId: string | null;
  onClose: () => void;
}

export function MatchDetailModal({ matchId, onClose }: MatchDetailModalProps) {
  const [detail, setDetail] = useState<TransactionDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showAdvancedEvidence, setShowAdvancedEvidence] = useState(false);

  useEffect(() => {
    if (!matchId) return;
    setLoading(true);
    setError(null);
    fetchTransactionDetail(matchId)
      .then((data) => setDetail(data))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [matchId]);

  // Keyboard shortcut: ESC to close modal
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  if (!matchId) return null;

  // Dynamic modal title based on topology & reason
  const getModalTitle = () => {
    if (detail?.topology === "MANY_TO_ONE" || detail?.match_type === "MANY_TO_ONE") {
      return "Batch Settlement Reconciliation";
    }
    if (detail?.reason_code === "FEE_RECONCILED" || detail?.match_type === "FEE_RECONCILED") {
      return "Fee Settlement Reconciliation";
    }
    if (detail?.decision === "EXCEPTION") {
      return "Exception Investigation";
    }
    if (detail?.reason_code === "AMOUNT_MISMATCH") {
      return "Amount Discrepancy Investigation";
    }
    return "3-Way Transaction Reconciliation";
  };

  const orderReference = 
    detail?.gateway_record?.payment_reference || 
    detail?.invoice_record?.invoice_reference || 
    detail?.bank_record?.reference || 
    "";

  return (
    <div 
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 dark:bg-black/80 p-4 backdrop-blur-sm overflow-y-auto"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-title"
    >
      <div 
        className="relative w-full max-w-4xl rounded-2xl border border-border bg-surface-secondary shadow-2xl my-8 max-h-[90vh] flex flex-col overflow-hidden animate-modal-in"
        onClick={(e) => e.stopPropagation()}
      >
        
        {/* Modal Header */}
        <div className="flex items-start justify-between border-b border-border bg-surface px-6 py-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2.5 flex-wrap">
              <h2 id="modal-title" className="text-xl font-bold text-content tracking-tight">
                {getModalTitle()}
              </h2>
              {detail && <StatusBadge status={detail.decision} size="sm" />}
              {detail && <RiskBadge risk={detail.risk_level} />}
              {detail && <MatchTypeTag matchType={detail.reason_code || detail.match_type} />}
            </div>

            <div className="text-xs text-content-secondary font-mono flex items-center gap-2 flex-wrap pt-0.5">
              <span>Match ID: <span className="text-content font-bold">{cleanId(matchId)}</span></span>
              {orderReference && (
                <span className="px-2 py-0.5 rounded bg-surface-elevated text-primary font-semibold border border-border">
                  Ref / Order: {orderReference}
                </span>
              )}
            </div>
          </div>

          <button
            onClick={onClose}
            aria-label="Close dialog"
            className="rounded-lg p-1.5 text-content-secondary hover:bg-surface-elevated hover:text-content transition-colors focus-ring"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="flex-1 overflow-y-auto px-6 py-5">
          {loading ? (
            <div className="flex h-64 items-center justify-center">
              <div className="flex items-center gap-2.5 text-sm text-content-secondary">
                <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
                Loading financial ledger audit records...
              </div>
            </div>
          ) : error ? (
            <div className="p-8 text-center text-rose-500 text-sm">{error}</div>
          ) : detail ? (
            <div className="space-y-6">

              {/* 1. DECISION SUMMARY BANNER (Immediate Top Controller View) */}
              <DecisionBanner
                decision={detail.decision}
                reasonCode={detail.reason_code || detail.match_type}
                explanation={detail.explanation}
                recommendedAction={detail.recommended_action}
                amounts={detail.amounts}
              />

              {/* 2. TOPOLOGY-AWARE FINANCIAL RECONCILIATION COMPARISON */}
              {detail.topology === "MANY_TO_ONE" || (detail.gateway_transactions && detail.gateway_transactions.length > 1) ? (
                /* Many-to-One Batch Layout */
                <div className="rounded-xl border border-purple-500/30 bg-purple-500/5 p-4 space-y-4 shadow-xs">
                  <div className="flex items-center justify-between gap-2">
                    <h3 className="text-xs font-semibold uppercase tracking-wider text-purple-700 dark:text-purple-300 flex items-center gap-2">
                      <Layers className="h-4 w-4" />
                      Batch Settlement Breakdown (Aggregated Gateway Captures → Bank Settlement)
                    </h3>
                    <span className="text-[11px] font-mono text-purple-700 dark:text-purple-300 bg-purple-500/15 px-2 py-0.5 rounded border border-purple-500/30 font-semibold">
                      {detail.gateway_transactions?.length || 0} Captures Bundled
                    </span>
                  </div>

                  {/* Gateway Aggregation Table */}
                  <div className="rounded-lg border border-border bg-surface overflow-hidden shadow-xs">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-surface-secondary text-content-secondary uppercase text-[10px] border-b border-border">
                        <tr>
                          <th className="px-3 py-2">Gateway Txn ID</th>
                          <th className="px-3 py-2">Date</th>
                          <th className="px-3 py-2">Payment Ref</th>
                          <th className="px-3 py-2">Customer</th>
                          <th className="px-3 py-2 text-right">Gross Amount</th>
                          <th className="px-3 py-2 text-right">Net Settlement</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border/60">
                        {detail.gateway_transactions?.map((g) => (
                          <tr key={g.gateway_txn_id} className="hover:bg-surface-secondary/50">
                            <td className="px-3 py-2 font-mono text-primary font-semibold">{cleanId(g.gateway_txn_id)}</td>
                            <td className="px-3 py-2 text-content-secondary font-mono">{formatDate(g.transaction_date)}</td>
                            <td className="px-3 py-2 font-mono text-content">{g.payment_reference}</td>
                            <td className="px-3 py-2 text-content font-medium">{g.customer_name}</td>
                            <td className="px-3 py-2 text-right font-bold text-content tabular-nums">{formatCurrency(g.amount)}</td>
                            <td className="px-3 py-2 text-right font-bold text-teal-600 dark:text-teal-300 tabular-nums">{formatCurrency(g.net_settlement || g.amount)}</td>
                          </tr>
                        ))}
                      </tbody>
                      <tfoot className="bg-surface-secondary border-t border-border font-bold text-xs">
                        <tr>
                          <td colSpan={4} className="px-3 py-2 text-content">Gateway Aggregation Subtotal</td>
                          <td className="px-3 py-2 text-right text-content tabular-nums font-bold">
                            {formatCurrency(detail.gateway_transactions?.reduce((acc, g) => acc + g.amount, 0) || 0)}
                          </td>
                          <td className="px-3 py-2 text-right text-teal-600 dark:text-teal-300 tabular-nums font-bold">
                            {formatCurrency(detail.gateway_transactions?.reduce((acc, g) => acc + (g.net_settlement || g.amount), 0) || 0)}
                          </td>
                        </tr>
                      </tfoot>
                    </table>
                  </div>

                  {/* Bank Deposit vs Reconciled Invoice Grid */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <div className="rounded-lg bg-surface border border-sky-500/30 p-3 space-y-1 text-xs shadow-xs">
                      <span className="text-[11px] font-semibold uppercase text-sky-600 dark:text-sky-400 flex items-center gap-1.5">
                        <Building2 className="h-3.5 w-3.5" /> Settling Bank Deposit
                      </span>
                      <div className="text-base font-bold text-content tabular-nums">{formatCurrency(detail.bank_record?.amount)}</div>
                      <div className="text-content-secondary text-[11px] font-mono">
                        Bank Txn: {cleanId(detail.bank_record?.bank_txn_id)} · Ref: {detail.bank_record?.reference}
                      </div>
                    </div>

                    <div className="rounded-lg bg-surface border border-indigo-500/30 p-3 space-y-1 text-xs shadow-xs">
                      <span className="text-[11px] font-semibold uppercase text-indigo-600 dark:text-indigo-400 flex items-center gap-1.5">
                        <FileText className="h-3.5 w-3.5" /> Reconciled ERP Invoice
                      </span>
                      <div className="text-base font-bold text-content tabular-nums">
                        {detail.invoice_record ? formatCurrency(detail.invoice_record.amount) : "Linked at Group Level"}
                      </div>
                      <div className="text-content-secondary text-[11px] font-mono">
                        {detail.invoice_record ? `Invoice: ${cleanId(detail.invoice_record.invoice_id)} · Ref: ${detail.invoice_record.invoice_reference}` : "Aggregated across customer accounts"}
                      </div>
                    </div>
                  </div>
                </div>
              ) : detail.fee_breakdown_json ? (
                /* Fee Settlement Layout */
                (() => {
                  let fb: any = null;
                  try { fb = JSON.parse(detail.fee_breakdown_json); } catch {}
                  if (!fb) return null;
                  return (
                    <div className="rounded-xl border border-teal-500/30 bg-teal-500/5 p-4 space-y-3 shadow-xs">
                      <div className="flex items-center justify-between">
                        <h3 className="text-xs font-semibold uppercase tracking-wider text-teal-700 dark:text-teal-300 flex items-center gap-2">
                          <Receipt className="h-4 w-4" />
                          Fee Settlement Decomposition
                        </h3>
                        <span className="text-[10px] text-teal-700 dark:text-teal-400 font-mono bg-teal-500/15 border border-teal-500/30 px-2 py-0.5 rounded font-semibold">
                          Deterministic Arithmetic
                        </span>
                      </div>

                      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-xs">
                        <div className="rounded-lg bg-surface border border-border p-2.5 shadow-xs">
                          <span className="text-content-secondary block text-[10px] uppercase font-semibold">Gross Captured</span>
                          <span className="text-sm font-bold text-content tabular-nums">{formatCurrency(fb.gross_amount)}</span>
                        </div>
                        <div className="rounded-lg bg-surface border border-border p-2.5 shadow-xs">
                          <span className="text-content-secondary block text-[10px] uppercase font-semibold">Gateway MDR Fee</span>
                          <span className="text-sm font-bold text-rose-600 dark:text-rose-300 tabular-nums">− {formatCurrency(fb.gateway_fee)}</span>
                        </div>
                        <div className="rounded-lg bg-surface border border-border p-2.5 shadow-xs">
                          <span className="text-content-secondary block text-[10px] uppercase font-semibold">GST on Fee (18%)</span>
                          <span className="text-sm font-bold text-rose-600 dark:text-rose-300 tabular-nums">− {formatCurrency(fb.tax_on_fee)}</span>
                        </div>
                        <div className="rounded-lg bg-surface border border-teal-500/30 p-2.5 shadow-xs">
                          <span className="text-content-secondary block text-[10px] uppercase font-semibold">Expected Net Settlement</span>
                          <span className="text-sm font-bold text-teal-700 dark:text-teal-300 tabular-nums">{formatCurrency(fb.expected_net_settlement)}</span>
                        </div>
                        <div className="rounded-lg bg-surface border border-teal-500/30 p-2.5 shadow-xs">
                          <span className="text-content-secondary block text-[10px] uppercase font-semibold">Actual Bank Credit</span>
                          <span className="text-sm font-bold text-teal-700 dark:text-teal-300 tabular-nums">{formatCurrency(fb.actual_bank_credit)}</span>
                        </div>
                        <div className={cn("rounded-lg border p-2.5 shadow-xs", Math.abs(fb.variance) < 0.01 ? "bg-emerald-500/10 border-emerald-500/30" : "bg-amber-500/10 border-amber-500/30")}>
                          <span className="text-content-secondary block text-[10px] uppercase font-semibold">Net Variance</span>
                          <span className={cn("text-sm font-bold tabular-nums", Math.abs(fb.variance) < 0.01 ? "text-emerald-600 dark:text-emerald-400" : "text-amber-600 dark:text-amber-400")}>
                            {Math.abs(fb.variance) < 0.01 ? "₹0.00 ✓" : formatCurrency(Math.abs(fb.variance))}
                          </span>
                        </div>
                      </div>
                    </div>
                  );
                })()
              ) : (
                /* Standard 3-Way Source Comparison Cards */
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3.5">
                  
                  {/* ERP Invoice Card */}
                  <div className="rounded-xl border border-border bg-surface p-4 space-y-2.5 shadow-xs">
                    <div className="flex items-center gap-2 text-xs font-semibold text-indigo-600 dark:text-indigo-300 uppercase tracking-wider">
                      <FileText className="h-4 w-4" />
                      ERP Invoice
                    </div>
                    {detail.invoice_record ? (
                      <div className="space-y-2 text-xs">
                        <div>
                          <span className="text-content-muted block text-[11px]">Invoice ID</span>
                          <span className="font-mono text-content font-semibold">{cleanId(detail.invoice_record.invoice_id)}</span>
                        </div>
                        <div>
                          <span className="text-content-muted block text-[11px]">Invoice Amount</span>
                          <span className="text-base font-bold text-content tabular-nums">{formatCurrency(detail.invoice_record.amount)}</span>
                        </div>
                        <div>
                          <span className="text-content-muted block text-[11px]">Date</span>
                          <span className="text-content-secondary font-mono">{formatDate(detail.invoice_record.invoice_date)}</span>
                        </div>
                        <div>
                          <span className="text-content-muted block text-[11px]">Customer</span>
                          <span className="text-content font-medium">{detail.invoice_record.customer_name}</span>
                        </div>
                      </div>
                    ) : (
                      <div className="py-6 text-center text-xs text-content-muted italic">No ERP Invoice Linked</div>
                    )}
                  </div>

                  {/* Payment Gateway Card */}
                  <div className="rounded-xl border border-border bg-surface p-4 space-y-2.5 shadow-xs">
                    <div className="flex items-center gap-2 text-xs font-semibold text-emerald-600 dark:text-emerald-300 uppercase tracking-wider">
                      <CreditCard className="h-4 w-4" />
                      Payment Gateway
                    </div>
                    {detail.gateway_record ? (
                      <div className="space-y-2 text-xs">
                        <div>
                          <span className="text-content-muted block text-[11px]">Gateway Txn ID</span>
                          <span className="font-mono text-content font-semibold">{cleanId(detail.gateway_record.gateway_txn_id)}</span>
                        </div>
                        <div>
                          <span className="text-content-muted block text-[11px]">Captured Amount</span>
                          <span className="text-base font-bold text-content tabular-nums">{formatCurrency(detail.gateway_record.amount)}</span>
                        </div>
                        <div>
                          <span className="text-content-muted block text-[11px]">Capture Date</span>
                          <span className="text-content-secondary font-mono">{formatDate(detail.gateway_record.transaction_date)}</span>
                        </div>
                        <div>
                          <span className="text-content-muted block text-[11px]">Customer</span>
                          <span className="text-content font-medium">{detail.gateway_record.customer_name}</span>
                        </div>
                      </div>
                    ) : (
                      <div className="py-6 text-center text-xs text-content-muted italic">No Gateway Record Linked</div>
                    )}
                  </div>

                  {/* Bank Statement Card */}
                  <div className="rounded-xl border border-border bg-surface p-4 space-y-2.5 shadow-xs">
                    <div className="flex items-center gap-2 text-xs font-semibold text-sky-600 dark:text-sky-300 uppercase tracking-wider">
                      <Building2 className="h-4 w-4" />
                      Bank Statement
                    </div>
                    {detail.bank_record ? (
                      <div className="space-y-2 text-xs">
                        <div>
                          <span className="text-content-muted block text-[11px]">Bank Txn ID</span>
                          <span className="font-mono text-content font-semibold">{cleanId(detail.bank_record.bank_txn_id)}</span>
                        </div>
                        <div>
                          <span className="text-content-muted block text-[11px]">Credit Settled</span>
                          <span className="text-base font-bold text-content tabular-nums">{formatCurrency(detail.bank_record.amount)}</span>
                        </div>
                        <div>
                          <span className="text-content-muted block text-[11px]">Settlement Date</span>
                          <span className="text-content-secondary font-mono">{formatDate(detail.bank_record.transaction_date)}</span>
                        </div>
                        <div>
                          <span className="text-content-muted block text-[11px]">Statement Ref</span>
                          <span className="text-content font-mono text-[11px] truncate block">{detail.bank_record.reference}</span>
                        </div>
                      </div>
                    ) : (
                      <div className="py-6 text-center text-xs text-content-muted italic">No Bank Settlement Matched</div>
                    )}
                  </div>

                </div>
              )}

              {/* 3. COLLAPSIBLE EVIDENCE & MATCH SIGNALS */}
              <div className="rounded-xl border border-border bg-surface p-4 space-y-3 shadow-xs">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-content flex items-center gap-2">
                    Evidence & Match Signals
                  </h3>
                  <button
                    onClick={() => setShowAdvancedEvidence(!showAdvancedEvidence)}
                    className="flex items-center gap-1 text-xs text-primary-light hover:text-primary transition-colors focus-ring rounded px-1"
                  >
                    <span>{showAdvancedEvidence ? "Hide Raw Math" : "Advanced Math Trace"}</span>
                    {showAdvancedEvidence ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
                  </button>
                </div>

                {/* 4 Qualitative Evidence Signals */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
                  <EvidenceSignal
                    label="Amount Alignment"
                    score={typeof detail.features?.amount_similarity === "number" ? detail.features.amount_similarity : (detail.decision === "MATCH" ? 1.0 : 0.0)}
                    weight={0.40}
                  />
                  <EvidenceSignal
                    label="Reference Match"
                    score={typeof detail.features?.reference_similarity === "number" ? detail.features.reference_similarity : (detail.decision === "MATCH" ? 1.0 : 0.5)}
                    weight={0.25}
                  />
                  <EvidenceSignal
                    label="Settlement Date"
                    score={typeof detail.features?.date_similarity === "number" ? detail.features.date_similarity : (detail.decision === "MATCH" ? 1.0 : 0.5)}
                    weight={0.20}
                  />
                  <EvidenceSignal
                    label="Customer Entity"
                    score={typeof detail.features?.customer_similarity === "number" ? detail.features.customer_similarity : (detail.decision === "MATCH" ? 1.0 : 0.5)}
                    weight={0.15}
                  />
                </div>

                {/* Collapsible Advanced Technical Explanation */}
                {showAdvancedEvidence && (
                  <div className="pt-3 border-t border-border space-y-2 text-xs text-content-secondary animate-fade-in">
                    <div className="flex items-center justify-between font-mono text-[11px]">
                      <span className="text-content font-bold">Composite Score: {(detail.confidence_score * 100).toFixed(2)}%</span>
                      <span className="text-content-muted">Weighting: 0.40(Amt) + 0.25(Ref) + 0.20(Date) + 0.15(Cust)</span>
                    </div>
                    {detail.features && (
                      <div className="text-[11px] font-mono text-content-secondary bg-surface-elevated p-2 rounded border border-border flex items-center justify-between">
                        <span>Breakdown: 0.40({((detail.features.amount_similarity ?? 0) * 100).toFixed(0)}%) + 0.25({((detail.features.reference_similarity ?? 0) * 100).toFixed(0)}%) + 0.20({((detail.features.date_similarity ?? 0) * 100).toFixed(0)}%) + 0.15({((detail.features.customer_similarity ?? 0) * 100).toFixed(0)}%)</span>
                        <span className="font-bold text-primary">{(((detail.features.composite_score ?? detail.confidence_score)) * 100).toFixed(2)}%</span>
                      </div>
                    )}
                    <p className="text-[11px] text-content-muted font-mono leading-relaxed">
                      Deterministic scoring model evaluates 4 multi-source dimensions. Unexplained variances or missing counterpart records incur proportional mathematical score reductions.
                    </p>
                  </div>
                )}
              </div>

              {/* 4. AI ADVISORY SECTION (Secondary Insight) */}
              {detail.ai && (
                <div className="rounded-xl border border-ai/30 bg-ai/5 p-4 space-y-2 text-xs shadow-xs">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold uppercase tracking-wider text-ai-light flex items-center gap-1.5">
                      <Sparkles className="h-3.5 w-3.5" /> AI Advisory Assessment
                    </span>
                    {detail.ai.confidence && (
                      <span className="text-[11px] font-mono text-ai-light bg-ai/20 px-2 py-0.5 rounded border border-ai/30 font-semibold">
                        Advisory Confidence: {(detail.ai.confidence * 100).toFixed(0)}%
                      </span>
                    )}
                  </div>
                  {detail.ai.explanation && (
                    <p className="text-content-secondary leading-relaxed">{detail.ai.explanation}</p>
                  )}
                  {detail.ai.recommended_action && (
                    <div className="pt-1.5 text-content-secondary">
                      <strong className="text-content">AI Suggestion:</strong> {detail.ai.recommended_action}
                    </div>
                  )}
                </div>
              )}
            </div>
          ) : null}
        </div>

        {/* Modal Footer */}
        <div className="border-t border-border bg-surface px-6 py-3.5 flex items-center justify-between">
          <span className="text-[11px] text-content-muted">
            Press <kbd className="bg-surface-secondary px-1.5 py-0.5 rounded border border-border font-mono text-[10px] text-content">ESC</kbd> to exit
          </span>
          <button
            onClick={onClose}
            className="rounded-lg bg-surface-elevated border border-border px-4 py-1.5 text-xs font-semibold text-content hover:bg-surface transition-colors focus-ring shadow-xs"
          >
            Close Investigation
          </button>
        </div>
      </div>
    </div>
  );
}
