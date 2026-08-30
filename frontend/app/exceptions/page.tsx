"use client";

import { useEffect, useState } from "react";
import { 
  AlertTriangle, 
  Clock, 
  CheckCircle2, 
  EyeOff, 
  ShieldAlert, 
  ArrowUpRight, 
  Filter, 
  Edit3, 
  Layers,
  Sparkles,
  ShieldCheck,
  Ban,
  Check,
  FileSearch,
  Tag,
  Info,
  RefreshCw,
  Search,
  RotateCcw
} from "lucide-react";
import { ExceptionRecord, AIInvestigation } from "@/types";
import { fetchExceptions, investigateException, approveException, rejectException, resetReconciliation } from "@/lib/api";
import { ExceptionTriageModal } from "@/components/exception-triage-modal";
import { formatCurrency, formatDate, formatPercent, cn } from "@/lib/utils";

// Quick filter types as requested
const EXCEPTION_TYPE_FILTERS = [
  { key: "", label: "All Types" },
  { key: "MDR_FEE_VARIANCE", label: "MDR Fee Variance" },
  { key: "MANY_TO_ONE_SETTLEMENT", label: "Many-to-One Settlement" },
  { key: "MISSING_BANK_LEG", label: "Missing Bank Leg" },
  { key: "DUPLICATE_TRANSACTION", label: "Duplicate Transaction" },
  { key: "AMOUNT_MISMATCH", label: "Amount Mismatch" },
  { key: "TIMING_DIFFERENCE", label: "Timing Difference" },
  { key: "NO_MATCH_FOUND", label: "Missing Counterpart" },
];

export default function ExceptionsPage() {
  const [exceptions, setExceptions] = useState<ExceptionRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<string>("OPEN");
  const [severityFilter, setSeverityFilter] = useState<string>("");
  const [typeFilter, setTypeFilter] = useState<string>("");
  const [searchTerm, setSearchTerm] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [isResetting, setIsResetting] = useState(false);
  const [selectedException, setSelectedException] = useState<ExceptionRecord | null>(null);

  const handleResetAll = async () => {
    if (!window.confirm("Reset and clear all exceptions and reconciliation records to start 100% fresh?")) return;
    setIsResetting(true);
    try {
      await resetReconciliation(undefined, true);
      if (typeof window !== "undefined") {
        localStorage.removeItem("latest_dataset_id");
      }
      await loadExceptions();
    } catch (err: any) {
      alert(`Failed to reset: ${err.message}`);
    } finally {
      setIsResetting(false);
    }
  };

  // Per-item action loading states
  const [investigatingIds, setInvestigatingIds] = useState<Record<string, boolean>>({});
  const [actionLoadingIds, setActionLoadingIds] = useState<Record<string, boolean>>({});
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  // Quick reject inline prompt
  const [rejectingId, setRejectingId] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState<string>("");

  const loadExceptions = async () => {
    setLoading(true);
    try {
      const res = await fetchExceptions({
        status: statusFilter || undefined,
        severity: severityFilter || undefined,
        page,
        pageSize: 50,
      });
      setExceptions(res.items);
      setTotal(res.total);
    } catch (err) {
      console.error("Failed to load exceptions:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadExceptions();
  }, [page, statusFilter, severityFilter]);

  const handleUpdated = (updated: ExceptionRecord) => {
    setExceptions((prev) =>
      prev.map((e) => (e.exception_id === updated.exception_id ? updated : e))
    );
  };

  // AI Investigate on a single card
  const handleInvestigateCard = async (exc: ExceptionRecord) => {
    setInvestigatingIds((prev) => ({ ...prev, [exc.exception_id]: true }));
    setActionMessage(null);
    try {
      const inv = await investigateException(exc.exception_id);
      const updated: ExceptionRecord = { ...exc, investigation: inv };
      handleUpdated(updated);
      setActionMessage(`AI investigation completed for ${exc.exception_id}: Recommended ${inv.recommendation}`);
    } catch (err: any) {
      setActionMessage(`Investigation failed: ${err.message}`);
    } finally {
      setInvestigatingIds((prev) => ({ ...prev, [exc.exception_id]: false }));
    }
  };

  // Quick Approve
  const handleApproveCard = async (exc: ExceptionRecord) => {
    setActionLoadingIds((prev) => ({ ...prev, [exc.exception_id]: true }));
    setActionMessage(null);
    try {
      const notes = exc.investigation 
        ? `[APPROVED] 1-Click AI Approval (${exc.investigation.classification} - ${Math.round(exc.investigation.confidence * 100)}% Confidence)`
        : `[APPROVED] 1-Click Approval via Workspace`;
      const res = await approveException(exc.exception_id, notes);
      const updated = { ...res, investigation: exc.investigation };
      handleUpdated(updated);
      setActionMessage(`Exception ${exc.exception_id} approved and resolved successfully.`);
    } catch (err: any) {
      setActionMessage(`Approval failed: ${err.message}`);
    } finally {
      setActionLoadingIds((prev) => ({ ...prev, [exc.exception_id]: false }));
    }
  };

  // Quick Reject & Escalate
  const handleRejectCard = async (exc: ExceptionRecord) => {
    if (!rejectReason.trim()) {
      setRejectingId(exc.exception_id);
      return;
    }
    setActionLoadingIds((prev) => ({ ...prev, [exc.exception_id]: true }));
    setActionMessage(null);
    try {
      const res = await rejectException(exc.exception_id, rejectReason);
      const updated = { ...res, investigation: exc.investigation };
      handleUpdated(updated);
      setRejectingId(null);
      setRejectReason("");
      setActionMessage(`Exception ${exc.exception_id} rejected and escalated to supervisor queue.`);
    } catch (err: any) {
      setActionMessage(`Rejection failed: ${err.message}`);
    } finally {
      setActionLoadingIds((prev) => ({ ...prev, [exc.exception_id]: false }));
    }
  };

  // Filter exceptions client-side for type and search keyword
  const filteredExceptions = exceptions.filter((e) => {
    if (typeFilter && !e.exception_type.toUpperCase().includes(typeFilter.toUpperCase())) {
      // Check flexible type matching (e.g. MDR_FEE_VARIANCE vs FEE_VARIANCE)
      const cleanType = typeFilter.replace(/_/g, "");
      const excClean = e.exception_type.replace(/_/g, "");
      if (!excClean.includes(cleanType) && !cleanType.includes(excClean)) {
        return false;
      }
    }
    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      const matchId = e.exception_id.toLowerCase().includes(term);
      const matchExp = e.explanation.toLowerCase().includes(term);
      const matchBank = e.bank_txn_id?.toLowerCase().includes(term);
      const matchGateway = e.gateway_txn_id?.toLowerCase().includes(term);
      const matchInvoice = e.invoice_id?.toLowerCase().includes(term);
      const matchType = e.exception_type.toLowerCase().includes(term);
      if (!matchId && !matchExp && !matchBank && !matchGateway && !matchInvoice && !matchType) {
        return false;
      }
    }
    return true;
  });

  // Metrics summary
  const totalInvolved = exceptions.reduce((acc, e) => acc + (e.amount_involved || 0), 0);
  const totalDiscrepancy = exceptions.reduce((acc, e) => acc + (e.amount_discrepancy || 0), 0);
  const highRiskCount = exceptions.filter((e) => e.severity === "HIGH").length;

  return (
    <div className="space-y-6">
      
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="bg-rose-500/10 text-rose-400 border border-rose-500/30 px-2.5 py-0.5 rounded-full text-xs font-semibold">
              Production Exception Engine
            </span>
            <span className="text-xs text-gray-500 font-mono">Phase 5 AI Triage Queue</span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2 mt-1.5">
            <AlertTriangle className="h-6 w-6 text-rose-400" />
            Exception Triage & AI Investigation Workspace
          </h1>
          <p className="mt-1 text-xs text-gray-400">
            Dedicated audit queue for discrepant transactions, MDR fee variances, batch settlements, missing legs, and duplicate charges.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={loadExceptions}
            className="flex items-center gap-1.5 rounded-lg border border-border bg-gray-800/80 px-3 py-1.5 text-xs font-medium text-gray-300 hover:bg-gray-700 hover:text-white transition-all"
          >
            <RefreshCw className={cn("h-3.5 w-3.5", loading && "animate-spin")} />
            Refresh
          </button>
          <button
            onClick={handleResetAll}
            disabled={isResetting || total === 0}
            className="flex items-center gap-1.5 rounded-lg border border-rose-500/30 bg-rose-950/20 px-3 py-1.5 text-xs font-semibold text-rose-300 hover:bg-rose-900/40 hover:text-rose-200 transition-all disabled:opacity-40"
            title="Reset and clear all exceptions"
          >
            <RotateCcw className={cn("h-3.5 w-3.5", isResetting && "animate-spin")} />
            Reset All
          </button>
          <div className="text-xs text-gray-400 font-mono bg-background/60 px-3 py-1.5 rounded-lg border border-border">
            Showing {filteredExceptions.length} of {total} exceptions
          </div>
        </div>
      </div>

      {/* Summary KPI Strip */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="rounded-xl border border-rose-500/30 bg-rose-500/5 p-4 shadow-sm">
          <div className="text-xs font-semibold uppercase tracking-wider text-rose-400">Total Unresolved Exposure</div>
          <div className="text-2xl font-bold text-white mt-1">{formatCurrency(totalInvolved)}</div>
          <div className="text-[11px] text-gray-400 mt-0.5">Across {exceptions.length} active exceptions in queue</div>
        </div>

        <div className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-4 shadow-sm">
          <div className="text-xs font-semibold uppercase tracking-wider text-amber-400">Net Discrepancy Variance</div>
          <div className="text-2xl font-bold text-white mt-1">{formatCurrency(totalDiscrepancy)}</div>
          <div className="text-[11px] text-gray-400 mt-0.5">Direct monetary delta between records</div>
        </div>

        <div className="rounded-xl border border-border bg-card p-4 shadow-sm">
          <div className="text-xs font-semibold uppercase tracking-wider text-gray-400">High Risk Items</div>
          <div className="text-2xl font-bold text-rose-400 mt-1">{highRiskCount}</div>
          <div className="text-[11px] text-gray-500 mt-0.5">Requires immediate supervisor attention</div>
        </div>
      </div>

      {/* Action Toast Message */}
      {actionMessage && (
        <div className="rounded-xl bg-primary/10 border border-primary/30 p-3 text-xs text-primary-light flex items-center justify-between shadow-sm">
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-primary-light" />
            <span>{actionMessage}</span>
          </div>
          <button 
            onClick={() => setActionMessage(null)}
            className="text-xs text-gray-400 hover:text-white"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Main Filter & Navigation Controls */}
      <div className="space-y-3 bg-card p-4 rounded-xl border border-border shadow-sm">
        
        {/* Top Filter Row: Status Tabs & Severity */}
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
          
          {/* Status Tabs */}
          <div className="flex flex-wrap items-center gap-1.5">
            {[
              { key: "OPEN", label: "Open Exceptions" },
              { key: "IN_REVIEW", label: "In Review" },
              { key: "RESOLVED", label: "Resolved" },
              { key: "IGNORED", label: "Ignored" },
              { key: "", label: "All Items" },
            ].map((tab) => (
              <button
                key={tab.key || "ALL"}
                onClick={() => {
                  setStatusFilter(tab.key);
                  setPage(1);
                }}
                className={cn(
                  "px-3 py-1.5 rounded-lg text-xs font-medium transition-all",
                  statusFilter === tab.key
                    ? "bg-primary text-white font-semibold shadow-sm"
                    : "bg-background/40 text-gray-400 hover:text-white border border-border hover:bg-gray-800"
                )}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Right Controls: Severity & Search */}
          <div className="flex flex-wrap items-center gap-2">
            {/* Search Input */}
            <div className="relative">
              <Search className="absolute left-2.5 top-2 h-3.5 w-3.5 text-gray-500" />
              <input
                type="text"
                placeholder="Search ID, explanation, ref..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-8 pr-3 py-1 rounded-lg border border-border bg-background/60 text-xs text-white placeholder-gray-500 focus:border-primary focus:outline-none w-48 sm:w-60"
              />
            </div>

            {/* Severity Filters */}
            <div className="flex items-center gap-1">
              {["", "HIGH", "MEDIUM", "LOW"].map((sev) => (
                <button
                  key={sev || "ALL_SEV"}
                  onClick={() => {
                    setSeverityFilter(sev);
                    setPage(1);
                  }}
                  className={cn(
                    "px-2.5 py-1 rounded-lg text-xs font-medium transition-all",
                    severityFilter === sev
                      ? "bg-gray-700 text-white font-semibold"
                      : "bg-background/40 text-gray-500 hover:text-white border border-border"
                  )}
                >
                  {sev ? `${sev}` : "All Severities"}
                </button>
              ))}
            </div>
          </div>

        </div>

        {/* Bottom Filter Row: Quick Filters for Exception Types */}
        <div className="border-t border-border/60 pt-3">
          <div className="flex items-center gap-2 overflow-x-auto pb-1 scrollbar-thin">
            <span className="text-[11px] font-semibold text-gray-400 shrink-0 flex items-center gap-1">
              <Tag className="h-3 w-3 text-indigo-400" />
              Quick Type Filters:
            </span>
            {EXCEPTION_TYPE_FILTERS.map((f) => (
              <button
                key={f.key || "ALL_TYPE"}
                onClick={() => setTypeFilter(f.key)}
                className={cn(
                  "shrink-0 px-2.5 py-1 rounded-lg text-[11px] font-medium transition-all border",
                  typeFilter === f.key
                    ? "bg-indigo-600/30 text-indigo-300 border-indigo-500 font-semibold"
                    : "bg-background/40 text-gray-400 hover:text-white border-border/80 hover:bg-gray-800"
                )}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>

      </div>

      {/* Exception Cards / List */}
      {loading ? (
        <div className="rounded-xl border border-border bg-card p-12 text-center text-gray-500">
          <div className="flex items-center justify-center gap-2">
            <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
            Loading exception items...
          </div>
        </div>
      ) : filteredExceptions.length === 0 ? (
        <div className="rounded-xl border border-border bg-card p-12 text-center text-gray-500 space-y-2">
          <AlertTriangle className="h-8 w-8 text-gray-600 mx-auto" />
          <p className="text-sm text-gray-400">No exceptions match the selected filters.</p>
          <button 
            onClick={() => { setStatusFilter(""); setSeverityFilter(""); setTypeFilter(""); setSearchTerm(""); }}
            className="text-xs text-primary-light hover:underline mt-1"
          >
            Clear all filters
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          {filteredExceptions.map((exc) => {
            const isHigh = exc.severity === "HIGH";
            const isMedium = exc.severity === "MEDIUM";
            const inv = exc.investigation;
            const isInvestigating = !!investigatingIds[exc.exception_id];
            const isActing = !!actionLoadingIds[exc.exception_id];
            const isRejectPromptActive = rejectingId === exc.exception_id;

            return (
              <div
                key={exc.exception_id}
                className={cn(
                  "rounded-2xl border p-5 bg-card transition-all hover:border-gray-600 shadow-md space-y-4",
                  isHigh ? "border-rose-500/40 bg-gradient-to-r from-rose-950/10 via-card to-card" : 
                  isMedium ? "border-amber-500/30" : "border-border"
                )}
              >
                {/* Header Row */}
                <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
                  
                  {/* Left Metadata & Details */}
                  <div className="space-y-2.5 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-xs font-bold text-white">{exc.exception_id}</span>
                      
                      <span className={cn(
                        "text-[10px] font-bold px-2.5 py-0.5 rounded-full border",
                        isHigh ? "bg-rose-500/10 text-rose-400 border-rose-500/30" :
                        isMedium ? "bg-amber-500/10 text-amber-400 border-amber-500/30" :
                        "bg-blue-500/10 text-blue-400 border-blue-500/30"
                      )}>
                        {exc.severity} SEVERITY
                      </span>

                      <span className="text-[10px] bg-gray-800 text-gray-300 px-2 py-0.5 rounded border border-gray-700 font-mono">
                        {exc.exception_type}
                      </span>

                      <span className={cn(
                        "text-[10px] px-2.5 py-0.5 rounded-full font-medium ml-auto md:ml-0 border",
                        exc.status === "OPEN" ? "bg-rose-500/10 text-rose-400 border-rose-500/30" :
                        exc.status === "IN_REVIEW" ? "bg-amber-500/10 text-amber-400 border-amber-500/30" :
                        exc.status === "RESOLVED" ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30" :
                        "bg-gray-800 text-gray-400 border-gray-700"
                      )}>
                        STATUS: {exc.status}
                      </span>
                    </div>

                    {/* Explanation */}
                    <p className="text-xs text-gray-200 leading-relaxed font-medium">
                      {exc.explanation}
                    </p>

                    {/* Recommended Action */}
                    <div className="text-[11px] text-gray-400 flex items-center gap-1.5">
                      <span className="text-gray-500 font-semibold">Recommended Action:</span>
                      <span className="text-indigo-300 font-medium">{exc.recommended_action}</span>
                    </div>

                    {/* References IDs */}
                    <div className="flex flex-wrap items-center gap-3 text-[11px] text-gray-500 font-mono pt-0.5">
                      {exc.bank_txn_id && <span>Bank: <strong className="text-gray-300">{exc.bank_txn_id}</strong></span>}
                      {exc.gateway_txn_id && <span>Gateway: <strong className="text-gray-300">{exc.gateway_txn_id}</strong></span>}
                      {exc.invoice_id && <span>Invoice: <strong className="text-gray-300">{exc.invoice_id}</strong></span>}
                      <span>Created: {formatDate(exc.created_at)}</span>
                    </div>
                  </div>

                  {/* Right Financial Values & AI Investigate Trigger */}
                  <div className="flex flex-col md:items-end justify-between self-stretch shrink-0 gap-3 border-t md:border-t-0 md:border-l border-border/60 pt-3 md:pt-0 md:pl-5">
                    <div className="md:text-right">
                      <span className="text-[10px] text-gray-500 uppercase block">Amount Involved</span>
                      <div className="text-lg font-bold text-white">{formatCurrency(exc.amount_involved)}</div>
                      {exc.amount_discrepancy > 0 && (
                        <div className="text-xs font-semibold text-rose-400 mt-0.5">
                          Δ Variance: {formatCurrency(exc.amount_discrepancy)}
                        </div>
                      )}
                    </div>

                    {/* AI Investigate Button with Pulsing Spark Icon */}
                    <button
                      onClick={() => handleInvestigateCard(exc)}
                      disabled={isInvestigating || isActing}
                      className={cn(
                        "flex items-center gap-2 rounded-xl px-3.5 py-2 text-xs font-bold transition-all shadow-md",
                        inv 
                          ? "bg-indigo-950/40 text-indigo-300 border border-indigo-500/40 hover:bg-indigo-900/50" 
                          : "bg-primary text-white hover:bg-primary-hover glow-primary"
                      )}
                    >
                      <Sparkles className={cn("h-4 w-4", isInvestigating ? "animate-spin text-white" : "text-primary-light animate-pulse")} />
                      {isInvestigating ? "Investigating..." : inv ? "Re-Investigate (AI)" : "AI Investigate"}
                    </button>
                  </div>

                </div>

                {/* AI INVESTIGATION RESULTS BOX (When present) */}
                {inv && (
                  <div className="rounded-xl border border-indigo-500/30 bg-gradient-to-r from-indigo-950/30 via-background/80 to-background/50 p-4 space-y-3 shadow-inner">
                    
                    {/* Header Row of Investigation */}
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-indigo-500/20 pb-2.5">
                      <div className="flex items-center gap-2">
                        <div className="p-1 rounded-lg bg-indigo-500/20 text-indigo-400">
                          <Sparkles className="h-4 w-4" />
                        </div>
                        <span className="text-xs font-bold text-white tracking-wide">
                          AI Autonomous Investigation Findings
                        </span>
                      </div>

                      <div className="flex items-center gap-2">
                        {/* Confidence Score Pill */}
                        <span className="text-xs bg-indigo-500/20 text-indigo-300 px-3 py-1 rounded-full border border-indigo-500/40 font-bold flex items-center gap-1.5">
                          <ShieldCheck className="h-3.5 w-3.5 text-indigo-400" />
                          {formatPercent(inv.confidence)} Confidence
                        </span>

                        {/* Recommendation Pill */}
                        <span className={cn(
                          "text-xs px-2.5 py-1 rounded-full font-bold border",
                          inv.recommendation === "MARK_RECONCILED" ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30" :
                          inv.recommendation === "ESCALATE" ? "bg-rose-500/10 text-rose-400 border-rose-500/30" :
                          "bg-amber-500/10 text-amber-400 border-amber-500/30"
                        )}>
                          {inv.recommendation}
                        </span>
                      </div>
                    </div>

                    {/* Proposed Classification & Explanation */}
                    <div className="space-y-1.5 text-xs">
                      <div className="flex items-center justify-between">
                        <span className="text-[11px] font-semibold text-gray-400 uppercase">
                          Root Cause Analysis
                        </span>
                        <span className="font-mono text-[10px] text-indigo-300 font-semibold">
                          Classification: {inv.classification}
                        </span>
                      </div>
                      <p className="text-xs text-gray-200 leading-relaxed bg-background/60 p-2.5 rounded-lg border border-border/80">
                        {inv.explanation}
                      </p>
                    </div>

                    {/* Policy Citations Tag */}
                    {inv.policy_references && inv.policy_references.length > 0 && (
                      <div className="flex flex-wrap items-center gap-1.5 pt-1">
                        <span className="text-[11px] text-gray-400 font-medium">Policy Citations:</span>
                        {inv.policy_references.map((pol, idx) => (
                          <span
                            key={idx}
                            className="rounded-md bg-indigo-500/10 border border-indigo-500/30 px-2 py-0.5 text-[11px] font-medium text-indigo-300 flex items-center gap-1"
                          >
                            <Info className="h-3 w-3 text-indigo-400" />
                            {pol}
                          </span>
                        ))}
                      </div>
                    )}

                    {/* Actionable Buttons Strip: Approve Resolution (green), Reject & Escalate (red), Full Triage Modal */}
                    <div className="flex flex-wrap items-center justify-between gap-3 pt-2.5 border-t border-indigo-500/20">
                      <div className="text-[11px] text-gray-400">
                        {inv.requires_human_review 
                          ? "⚠️ Operator concurrence recommended before closing."
                          : "✅ Verified formula match — instant resolution available."}
                      </div>

                      <div className="flex items-center gap-2">
                        {/* Reject & Escalate (Red) */}
                        <button
                          onClick={() => handleRejectCard(exc)}
                          disabled={isActing}
                          className="flex items-center gap-1.5 rounded-lg border border-rose-500/40 bg-rose-500/10 px-3 py-1.5 text-xs font-bold text-rose-300 hover:bg-rose-500/20 hover:text-white transition-all disabled:opacity-50"
                        >
                          <Ban className="h-3.5 w-3.5" />
                          Reject & Escalate
                        </button>

                        {/* Approve Resolution (Green) */}
                        <button
                          onClick={() => handleApproveCard(exc)}
                          disabled={isActing}
                          className="flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3.5 py-1.5 text-xs font-bold text-white hover:bg-emerald-500 transition-all shadow-md glow-emerald disabled:opacity-50"
                        >
                          <CheckCircle2 className="h-3.5 w-3.5" />
                          {isActing ? "Updating..." : "Approve Resolution"}
                        </button>

                        {/* Full Triage Modal */}
                        <button
                          onClick={() => setSelectedException(exc)}
                          className="flex items-center gap-1.5 rounded-lg border border-border bg-gray-800 px-3 py-1.5 text-xs font-bold text-gray-200 hover:bg-gray-700 hover:text-white transition-colors"
                        >
                          <Edit3 className="h-3.5 w-3.5" />
                          Full Triage Modal
                        </button>
                      </div>
                    </div>

                  </div>
                )}

                {/* Rejection reason inline input if clicked */}
                {isRejectPromptActive && (
                  <div className="rounded-xl border border-rose-500/40 bg-rose-950/20 p-3.5 space-y-2">
                    <div className="flex items-center justify-between text-xs font-bold text-rose-300">
                      <span className="flex items-center gap-1">
                        <ShieldAlert className="h-4 w-4 text-rose-400" />
                        Specify reason for rejecting and escalating {exc.exception_id}:
                      </span>
                      <button onClick={() => setRejectingId(null)} className="text-gray-400 hover:text-white text-xs">
                        Cancel
                      </button>
                    </div>
                    <div className="flex items-center gap-2">
                      <input
                        type="text"
                        placeholder="e.g. Unexplained variance exceeds threshold; requires merchant invoice review..."
                        value={rejectReason}
                        onChange={(e) => setRejectReason(e.target.value)}
                        className="flex-1 rounded-lg border border-rose-500/30 bg-background/80 px-3 py-1.5 text-xs text-white placeholder-gray-500 focus:border-rose-400 focus:outline-none"
                      />
                      <button
                        onClick={() => handleRejectCard(exc)}
                        disabled={!rejectReason.trim()}
                        className="rounded-lg bg-rose-600 px-3 py-1.5 text-xs font-bold text-white hover:bg-rose-500 disabled:opacity-50 shrink-0"
                      >
                        Confirm Rejection
                      </button>
                    </div>
                  </div>
                )}

                {/* Audit notes if present on resolved/reviewed exceptions */}
                {exc.notes && !inv && (
                  <div className="rounded-lg bg-background/60 p-2.5 border border-border text-xs text-emerald-300 flex items-center justify-between">
                    <div>
                      <span className="font-semibold text-gray-400 block text-[10px]">OPERATOR AUDIT NOTE:</span>
                      {exc.notes}
                    </div>
                    <button
                      onClick={() => setSelectedException(exc)}
                      className="text-xs text-indigo-300 hover:underline shrink-0 ml-4"
                    >
                      Edit Note
                    </button>
                  </div>
                )}

                {/* Footer fallback button if no AI investigation displayed yet */}
                {!inv && (
                  <div className="flex items-center justify-end gap-2 pt-1 border-t border-border/40">
                    <button
                      onClick={() => setSelectedException(exc)}
                      className="flex items-center gap-1.5 rounded-lg bg-gray-800 px-3 py-1.5 text-xs font-bold text-white hover:bg-primary transition-colors shadow-sm"
                    >
                      <Edit3 className="h-3.5 w-3.5" />
                      Full Triage Modal
                    </button>
                  </div>
                )}

              </div>
            );
          })}
        </div>
      )}

      {/* Triage Modal */}
      {selectedException && (
        <ExceptionTriageModal
          exception={selectedException}
          onClose={() => setSelectedException(null)}
          onUpdated={handleUpdated}
        />
      )}

    </div>
  );
}
