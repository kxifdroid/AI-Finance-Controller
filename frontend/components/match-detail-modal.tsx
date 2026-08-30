"use client";

import { useEffect, useState } from "react";
import { 
  X, 
  CheckCircle2, 
  AlertCircle, 
  HelpCircle, 
  Copy, 
  Building2, 
  CreditCard, 
  FileText,
  Sparkles,
  ShieldCheck,
  Scale,
  Receipt
} from "lucide-react";
import { TransactionDetail } from "@/types";
import { fetchTransactionDetail } from "@/lib/api";
import { formatCurrency, formatDate, formatPercent, cleanId, cn } from "@/lib/utils";

interface MatchDetailModalProps {
  matchId: string | null;
  onClose: () => void;
}

export function MatchDetailModal({ matchId, onClose }: MatchDetailModalProps) {
  const [detail, setDetail] = useState<TransactionDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!matchId) return;
    setLoading(true);
    setError(null);
    fetchTransactionDetail(matchId)
      .then((data) => setDetail(data))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [matchId]);

  if (!matchId) return null;

  const getStatusBadge = (decision: string) => {
    switch (decision) {
      case "MATCH":
        return <span className="bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 px-2.5 py-1 rounded-full text-xs font-semibold">AUTO MATCH</span>;
      case "REVIEW":
        return <span className="bg-amber-500/10 text-amber-400 border border-amber-500/30 px-2.5 py-1 rounded-full text-xs font-semibold">HUMAN REVIEW</span>;
      case "EXCEPTION":
        return <span className="bg-rose-500/10 text-rose-400 border border-rose-500/30 px-2.5 py-1 rounded-full text-xs font-semibold">EXCEPTION</span>;
      case "DUPLICATE":
        return <span className="bg-purple-500/10 text-purple-400 border border-purple-500/30 px-2.5 py-1 rounded-full text-xs font-semibold">DUPLICATE</span>;
      case "MISSING":
        return <span className="bg-gray-500/10 text-gray-400 border border-gray-500/30 px-2.5 py-1 rounded-full text-xs font-semibold">MISSING RECORD</span>;
      default:
        return <span className="bg-gray-500/10 text-gray-400 border border-gray-500/30 px-2.5 py-1 rounded-full text-xs font-semibold">{decision}</span>;
    }
  };

  const getFeeClassificationBadge = (cls: string) => {
    switch (cls) {
      case "FEE_RECONCILED":
        return <span className="bg-teal-500/10 text-teal-300 border border-teal-500/30 px-2.5 py-1 rounded-full text-xs font-semibold flex items-center gap-1"><Receipt className="h-3 w-3" /> FEE RECONCILED</span>;
      case "FEE_VARIANCE":
        return <span className="bg-amber-500/10 text-amber-300 border border-amber-500/30 px-2.5 py-1 rounded-full text-xs font-semibold">FEE VARIANCE</span>;
      case "FEE_MISMATCH":
        return <span className="bg-rose-500/10 text-rose-300 border border-rose-500/30 px-2.5 py-1 rounded-full text-xs font-semibold">FEE MISMATCH</span>;
      default:
        return null;
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm overflow-y-auto">
      <div className="relative w-full max-w-4xl rounded-2xl border border-border bg-card p-6 shadow-2xl my-8 max-h-[90vh] overflow-y-auto">
        
        {/* Header */}
        <div className="flex items-start justify-between border-b border-border pb-4">
          <div>
            <div className="flex items-center gap-3 flex-wrap">
              <h2 className="text-xl font-bold text-white tracking-tight">3-Way Transaction Reconciliation Detail</h2>
              {detail && getStatusBadge(detail.decision)}
              {detail?.fee_classification && getFeeClassificationBadge(detail.fee_classification)}
            </div>
            <p className="mt-1 text-xs text-gray-400 font-mono">
              Match Reference ID: <span className="text-gray-200">{cleanId(matchId)}</span>
            </p>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-gray-400 hover:bg-gray-800 hover:text-white transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {loading ? (
          <div className="flex h-64 items-center justify-center">
            <div className="flex items-center gap-2 text-sm text-gray-400">
              <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
              Loading 3-way financial ledger details...
            </div>
          </div>
        ) : error ? (
          <div className="p-8 text-center text-rose-400 text-sm">{error}</div>
        ) : detail ? (
          <div className="mt-6 space-y-6">

            {/* 3-Way Side-by-Side Comparison */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              
              {/* Bank Statement Card */}
              <div className="rounded-xl border border-border bg-background/50 p-4 space-y-3">
                <div className="flex items-center gap-2 text-xs font-semibold text-sky-400 uppercase tracking-wider">
                  <Building2 className="h-4 w-4" />
                  Bank Statement
                </div>
                {detail.bank_record ? (
                  <div className="space-y-2 text-xs">
                    <div>
                      <span className="text-gray-500 block">Bank Txn ID</span>
                      <span className="font-mono text-white font-medium">{cleanId(detail.bank_record.bank_txn_id)}</span>
                    </div>
                    <div>
                      <span className="text-gray-500 block">Amount</span>
                      <span className="text-base font-bold text-white">{formatCurrency(detail.bank_record.amount)}</span>
                    </div>
                    <div>
                      <span className="text-gray-500 block">Date</span>
                      <span className="text-gray-300">{formatDate(detail.bank_record.transaction_date)}</span>
                    </div>
                    <div>
                      <span className="text-gray-500 block">Reference</span>
                      <span className="font-mono text-gray-300">{detail.bank_record.reference}</span>
                    </div>
                    <div>
                      <span className="text-gray-500 block">Statement Description</span>
                      <span className="text-gray-300 text-[11px] line-clamp-2">{detail.bank_record.description}</span>
                    </div>
                  </div>
                ) : (
                  <div className="py-8 text-center text-xs text-gray-500 italic">No Bank Record Matched</div>
                )}
              </div>

              {/* Payment Gateway Card */}
              <div className="rounded-xl border border-border bg-background/50 p-4 space-y-3">
                <div className="flex items-center gap-2 text-xs font-semibold text-emerald-400 uppercase tracking-wider">
                  <CreditCard className="h-4 w-4" />
                  Payment Gateway
                </div>
                {detail.gateway_record ? (
                  <div className="space-y-2 text-xs">
                    <div>
                      <span className="text-gray-500 block">Gateway Txn ID</span>
                      <span className="font-mono text-white font-medium">{cleanId(detail.gateway_record.gateway_txn_id)}</span>
                    </div>
                    <div>
                      <span className="text-gray-500 block">Amount</span>
                      <span className="text-base font-bold text-white">{formatCurrency(detail.gateway_record.amount)}</span>
                    </div>
                    <div>
                      <span className="text-gray-500 block">Date</span>
                      <span className="text-gray-300">{formatDate(detail.gateway_record.transaction_date)}</span>
                    </div>
                    <div>
                      <span className="text-gray-500 block">Payment Reference</span>
                      <span className="font-mono text-gray-300">{detail.gateway_record.payment_reference}</span>
                    </div>
                    <div>
                      <span className="text-gray-500 block">Customer</span>
                      <span className="text-gray-300 font-medium">{detail.gateway_record.customer_name}</span>
                    </div>
                  </div>
                ) : (
                  <div className="py-8 text-center text-xs text-gray-500 italic">No Gateway Record Matched</div>
                )}
              </div>

              {/* ERP Invoice Card */}
              <div className="rounded-xl border border-border bg-background/50 p-4 space-y-3">
                <div className="flex items-center gap-2 text-xs font-semibold text-indigo-400 uppercase tracking-wider">
                  <FileText className="h-4 w-4" />
                  ERP Invoice
                </div>
                {detail.invoice_record ? (
                  <div className="space-y-2 text-xs">
                    <div>
                      <span className="text-gray-500 block">Invoice ID</span>
                      <span className="font-mono text-white font-medium">{cleanId(detail.invoice_record.invoice_id)}</span>
                    </div>
                    <div>
                      <span className="text-gray-500 block">Amount</span>
                      <span className="text-base font-bold text-white">{formatCurrency(detail.invoice_record.amount)}</span>
                    </div>
                    <div>
                      <span className="text-gray-500 block">Invoice Date</span>
                      <span className="text-gray-300">{formatDate(detail.invoice_record.invoice_date)}</span>
                    </div>
                    <div>
                      <span className="text-gray-500 block">Invoice Reference</span>
                      <span className="font-mono text-gray-300">{detail.invoice_record.invoice_reference}</span>
                    </div>
                    <div>
                      <span className="text-gray-500 block">Customer / Entity</span>
                      <span className="text-gray-300 font-medium">{detail.invoice_record.customer_name}</span>
                    </div>
                  </div>
                ) : (
                  <div className="py-8 text-center text-xs text-gray-500 italic">No ERP Invoice Record Matched</div>
                )}
              </div>

            </div>

            {/* Fee Settlement Breakdown — shown when gateway fee was deducted */}
            {detail.fee_breakdown_json && (() => {
              let fb: any = null;
              try { fb = JSON.parse(detail.fee_breakdown_json); } catch {}
              if (!fb) return null;
              return (
                <div className="rounded-xl border border-teal-500/30 bg-teal-500/5 p-4">
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-teal-400 flex items-center gap-2 mb-3">
                    <Receipt className="h-4 w-4" />
                    Deterministic Fee Settlement Calculation
                    <span className="ml-auto text-[10px] text-teal-600 font-mono">LLM-Free · Python Arithmetic</span>
                  </h3>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-xs">
                    <div className="rounded-lg bg-card/60 border border-border/50 p-2.5">
                      <span className="text-gray-400 block">Invoice / Gross Amount</span>
                      <span className="text-base font-bold text-white">{formatCurrency(fb.gross_amount)}</span>
                    </div>
                    <div className="rounded-lg bg-card/60 border border-border/50 p-2.5">
                      <span className="text-gray-400 block">Gateway Fee (MDR)</span>
                      <span className="text-base font-bold text-rose-400">− {formatCurrency(fb.gateway_fee)}</span>
                    </div>
                    <div className="rounded-lg bg-card/60 border border-border/50 p-2.5">
                      <span className="text-gray-400 block">Tax on Fee (GST 18%)</span>
                      <span className="text-base font-bold text-rose-400">− {formatCurrency(fb.tax_on_fee)}</span>
                    </div>
                    <div className="rounded-lg bg-teal-900/30 border border-teal-500/30 p-2.5">
                      <span className="text-gray-400 block">Expected Net Settlement</span>
                      <span className="text-base font-bold text-teal-300">{formatCurrency(fb.expected_net_settlement)}</span>
                    </div>
                    <div className="rounded-lg bg-teal-900/30 border border-teal-500/30 p-2.5">
                      <span className="text-gray-400 block">Actual Bank Credit</span>
                      <span className="text-base font-bold text-teal-300">{formatCurrency(fb.actual_bank_credit)}</span>
                    </div>
                    <div className={`rounded-lg border p-2.5 ${Math.abs(fb.variance) < 0.01 ? "bg-emerald-900/20 border-emerald-500/30" : "bg-amber-900/20 border-amber-500/30"}`}>
                      <span className="text-gray-400 block">Variance</span>
                      <span className={`text-base font-bold ${Math.abs(fb.variance) < 0.01 ? "text-emerald-400" : "text-amber-400"}`}>
                        {fb.variance === 0 ? "₹0.00 ✓" : formatCurrency(Math.abs(fb.variance))}
                      </span>
                    </div>
                  </div>
                  <p className="mt-2 text-[11px] text-teal-700">
                    Formula: {formatCurrency(fb.gross_amount)} − {formatCurrency(fb.gateway_fee)} (fee) − {formatCurrency(fb.tax_on_fee)} (GST) = {formatCurrency(fb.expected_net_settlement)} expected · Bank credited {formatCurrency(fb.actual_bank_credit)} · Classification: {fb.classification}
                  </p>
                </div>
              );
            })()}

            {/* Deterministic Scoring Features Breakdown */}
            <div className="rounded-xl border border-border bg-background/30 p-4">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-400 flex items-center gap-2 mb-3">
                <Scale className="h-4 w-4 text-primary-light" />
                Multi-Factor Deterministic Scoring Breakdown
              </h3>
              
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="rounded-lg bg-card/60 p-2.5 border border-border/50">
                  <div className="text-[11px] text-gray-400">Amount Similarity (0.40)</div>
                  <div className="text-base font-bold text-white mt-0.5 flex items-baseline gap-1.5">
                    <span>{(detail.features?.amount_similarity ?? 1).toFixed(4)}</span>
                    <span className="text-xs font-normal text-gray-400">({formatPercent(detail.features?.amount_similarity ?? 1)})</span>
                  </div>
                  <div className="w-full bg-gray-800 h-1.5 rounded-full mt-1.5 overflow-hidden">
                    <div
                      className={cn(
                        "h-full rounded-full",
                        (detail.features?.amount_similarity ?? 1) >= 0.90
                          ? "bg-emerald-500"
                          : (detail.features?.amount_similarity ?? 1) >= 0.50
                          ? "bg-amber-500"
                          : "bg-rose-500"
                      )}
                      style={{ width: `${Math.min(100, (detail.features?.amount_similarity ?? 1) * 100)}%` }}
                    />
                  </div>
                </div>

                <div className="rounded-lg bg-card/60 p-2.5 border border-border/50">
                  <div className="text-[11px] text-gray-400">Reference Similarity (0.25)</div>
                  <div className="text-base font-bold text-white mt-0.5 flex items-baseline gap-1.5">
                    <span>{(detail.features?.reference_similarity ?? 1).toFixed(4)}</span>
                    <span className="text-xs font-normal text-gray-400">({formatPercent(detail.features?.reference_similarity ?? 1)})</span>
                  </div>
                  <div className="w-full bg-gray-800 h-1.5 rounded-full mt-1.5 overflow-hidden">
                    <div
                      className={cn(
                        "h-full rounded-full",
                        (detail.features?.reference_similarity ?? 1) >= 0.90
                          ? "bg-emerald-500"
                          : (detail.features?.reference_similarity ?? 1) >= 0.50
                          ? "bg-amber-500"
                          : "bg-rose-500"
                      )}
                      style={{ width: `${Math.min(100, (detail.features?.reference_similarity ?? 1) * 100)}%` }}
                    />
                  </div>
                </div>

                <div className="rounded-lg bg-card/60 p-2.5 border border-border/50">
                  <div className="text-[11px] text-gray-400">Date Settlement (0.20)</div>
                  <div className="text-base font-bold text-white mt-0.5 flex items-baseline gap-1.5">
                    <span>{(detail.features?.date_similarity ?? 1).toFixed(4)}</span>
                    <span className="text-xs font-normal text-gray-400">({formatPercent(detail.features?.date_similarity ?? 1)})</span>
                  </div>
                  <div className="w-full bg-gray-800 h-1.5 rounded-full mt-1.5 overflow-hidden">
                    <div
                      className={cn(
                        "h-full rounded-full",
                        (detail.features?.date_similarity ?? 1) >= 0.90
                          ? "bg-emerald-500"
                          : (detail.features?.date_similarity ?? 1) >= 0.50
                          ? "bg-amber-500"
                          : "bg-rose-500"
                      )}
                      style={{ width: `${Math.min(100, (detail.features?.date_similarity ?? 1) * 100)}%` }}
                    />
                  </div>
                </div>

                <div className="rounded-lg bg-card/60 p-2.5 border border-border/50">
                  <div className="text-[11px] text-gray-400">Customer Entity (0.15)</div>
                  <div className="text-base font-bold text-white mt-0.5 flex items-baseline gap-1.5">
                    <span>{(detail.features?.customer_similarity ?? 1).toFixed(4)}</span>
                    <span className="text-xs font-normal text-gray-400">({formatPercent(detail.features?.customer_similarity ?? 1)})</span>
                  </div>
                  <div className="w-full bg-gray-800 h-1.5 rounded-full mt-1.5 overflow-hidden">
                    <div
                      className={cn(
                        "h-full rounded-full",
                        (detail.features?.customer_similarity ?? 1) >= 0.90
                          ? "bg-emerald-500"
                          : (detail.features?.customer_similarity ?? 1) >= 0.50
                          ? "bg-amber-500"
                          : "bg-rose-500"
                      )}
                      style={{ width: `${Math.min(100, (detail.features?.customer_similarity ?? 1) * 100)}%` }}
                    />
                  </div>
                </div>
              </div>
            </div>

            {/* Explanation & Recommended Action */}
            <div className="rounded-xl border border-primary/20 bg-primary/5 p-4 space-y-3">
              <div className="flex items-center gap-2 text-xs font-semibold text-primary-light uppercase tracking-wider">
                <Sparkles className="h-4 w-4" />
                Auditor Explanation & Actionable Guidance
                {detail.verified_by_ai && (
                  <span className="ml-auto text-[10px] bg-primary/20 text-primary-light px-2 py-0.5 rounded-full border border-primary/40 font-mono">
                    AI Verified
                  </span>
                )}
              </div>
              <p className="text-sm text-gray-200 leading-relaxed">{detail.explanation}</p>
              
              <div className="pt-2 border-t border-primary/10 flex items-center justify-between text-xs">
                <span className="text-gray-400">Recommended Action:</span>
                <span className="font-semibold text-white">{detail.recommended_action}</span>
              </div>
            </div>

          </div>
        ) : null}

        {/* Footer */}
        <div className="mt-6 flex justify-end border-t border-border pt-4">
          <button
            onClick={onClose}
            className="rounded-lg bg-gray-800 px-4 py-2 text-xs font-semibold text-white hover:bg-gray-700 transition-colors"
          >
            Close Detail View
          </button>
        </div>

      </div>
    </div>
  );
}
