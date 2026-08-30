"use client";

import { useState } from "react";
import { 
  X, 
  AlertTriangle, 
  CheckCircle2, 
  Clock, 
  EyeOff, 
  Save, 
  Sparkles, 
  Building, 
  CreditCard, 
  FileText, 
  ChevronDown, 
  ChevronUp, 
  ShieldCheck, 
  ShieldAlert, 
  Calculator, 
  Check, 
  Ban, 
  Info,
  Scale
} from "lucide-react";
import { ExceptionRecord, AIInvestigation } from "@/types";
import { updateExceptionStatus, investigateException, approveException, rejectException } from "@/lib/api";
import { formatCurrency, formatDate, formatPercent, cleanId, cn } from "@/lib/utils";

interface ExceptionTriageModalProps {
  exception: ExceptionRecord | null;
  onClose: () => void;
  onUpdated: (updated: ExceptionRecord) => void;
}

export function ExceptionTriageModal({
  exception,
  onClose,
  onUpdated,
}: ExceptionTriageModalProps) {
  const [currentException, setCurrentException] = useState<ExceptionRecord | null>(exception);
  const [investigation, setInvestigation] = useState<AIInvestigation | null>(
    exception?.investigation || null
  );
  const [status, setStatus] = useState<string>(exception?.status || "OPEN");
  const [notes, setNotes] = useState<string>(exception?.notes || "");
  const [rejectReason, setRejectReason] = useState<string>("");
  const [showRejectPrompt, setShowRejectPrompt] = useState<boolean>(false);
  
  const [isInvestigating, setIsInvestigating] = useState<boolean>(false);
  const [isApproving, setIsApproving] = useState<boolean>(false);
  const [isRejecting, setIsRejecting] = useState<boolean>(false);
  const [saving, setSaving] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedEvidence, setExpandedEvidence] = useState<boolean>(true);

  if (!currentException) return null;

  // Derive ledger values
  const grossAmt = currentException.amount_involved || 
    currentException.gateway_transaction?.amount || 
    currentException.invoice?.amount || 
    0;
  const mdrRate = 0.02; // 2% MDR standard
  const gstRate = 0.18; // 18% GST on MDR
  const mdrFee = grossAmt * mdrRate;
  const gstFee = mdrFee * gstRate;
  const totalDeduction = mdrFee + gstFee;
  const expectedNet = grossAmt - totalDeduction;
  const actualBankAmt = currentException.bank_transaction?.amount || (grossAmt - (currentException.amount_discrepancy || 0));
  const variance = Math.abs(expectedNet - actualBankAmt);

  // Parse evidence chain items
  let evidenceList: string[] = [];
  if (investigation?.evidence) {
    if (Array.isArray(investigation.evidence)) {
      evidenceList = investigation.evidence;
    } else if (typeof investigation.evidence === "object") {
      evidenceList = Object.entries(investigation.evidence).map(
        ([k, v]) => `${k.replace(/_/g, " ").toUpperCase()}: ${typeof v === "object" ? JSON.stringify(v) : v}`
      );
    }
  } else if (currentException.evidence_json) {
    try {
      const parsed = JSON.parse(currentException.evidence_json);
      if (Array.isArray(parsed)) {
        evidenceList = parsed;
      } else if (parsed.reason || parsed.rule || parsed.policy_citation) {
        evidenceList = [];
        if (parsed.reason) evidenceList.push(`Audit Finding: ${parsed.reason}`);
        if (parsed.rule) evidenceList.push(`Classification Rule: ${parsed.rule.replace(/_/g, " ")}`);
        if (parsed.policy_citation) evidenceList.push(`Policy Reference: ${parsed.policy_citation}`);
      } else {
        evidenceList = Object.entries(parsed).map(([k, v]) => `${k.replace(/_/g, " ")}: ${typeof v === "object" ? JSON.stringify(v) : v}`);
      }
    } catch {
      evidenceList = [currentException.evidence_json];
    }
  }

  // Fallback default audit evidence if none provided
  if (evidenceList.length === 0) {
    evidenceList = [
      `Amount Involved: ₹${(currentException.amount_involved || 0).toLocaleString()}`,
      `Discrepancy Variance: ₹${(currentException.amount_discrepancy || 0).toLocaleString()}`,
      `Classification: ${currentException.exception_type}`,
      `Severity Level: ${currentException.severity} Priority`,
      `Bank Leg: ${currentException.bank_txn_id ? `Linked (${currentException.bank_txn_id})` : "Missing or Delayed"}`,
      `Gateway Leg: ${currentException.gateway_txn_id ? `Linked (${currentException.gateway_txn_id})` : "Missing or Delayed"}`,
      `Invoice Leg: ${currentException.invoice_id ? `Linked (${currentException.invoice_id})` : "Missing or Delayed"}`,
    ];
  }

  // Handle Manual Save
  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      const res = await updateExceptionStatus(currentException.exception_id, status, notes);
      const updated = { ...res, investigation: investigation || undefined };
      setCurrentException(updated);
      onUpdated(updated);
      onClose();
    } catch (err: any) {
      setError(err.message || "Failed to update exception status");
    } finally {
      setSaving(false);
    }
  };

  // Handle AI Investigation
  const handleRunInvestigation = async () => {
    setIsInvestigating(true);
    setError(null);
    try {
      const inv = await investigateException(currentException.exception_id);
      setInvestigation(inv);
      const updated = { ...currentException, investigation: inv };
      setCurrentException(updated);
      onUpdated(updated);
    } catch (err: any) {
      setError(err.message || "Failed to execute AI investigation");
    } finally {
      setIsInvestigating(false);
    }
  };

  // Handle 1-Click Approve
  const handleApprove = async () => {
    setIsApproving(true);
    setError(null);
    try {
      const auditNote = notes 
        ? `${notes} | AI Verified & Approved (${investigation?.classification || currentException.exception_type})`
        : `Approved resolution via AI Investigation (${investigation?.classification || currentException.exception_type}). Verified fee structure & clearance policies.`;
      const res = await approveException(currentException.exception_id, auditNote);
      const updated = { ...res, investigation: investigation || undefined };
      setCurrentException(updated);
      setStatus("RESOLVED");
      onUpdated(updated);
      onClose();
    } catch (err: any) {
      setError(err.message || "Failed to approve exception");
    } finally {
      setIsApproving(false);
    }
  };

  // Handle 1-Click Reject & Escalate
  const handleReject = async () => {
    if (!rejectReason.trim()) {
      setShowRejectPrompt(true);
      return;
    }
    setIsRejecting(true);
    setError(null);
    try {
      const res = await rejectException(currentException.exception_id, rejectReason);
      const updated = { ...res, investigation: investigation || undefined };
      setCurrentException(updated);
      setStatus("IN_REVIEW");
      onUpdated(updated);
      onClose();
    } catch (err: any) {
      setError(err.message || "Failed to reject and escalate exception");
    } finally {
      setIsRejecting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4 backdrop-blur-md overflow-y-auto">
      <div className="relative w-full max-w-4xl max-h-[92vh] flex flex-col rounded-2xl border border-border bg-card shadow-2xl overflow-hidden my-auto">
        
        {/* Modal Header */}
        <div className="flex items-center justify-between border-b border-border/80 bg-background/50 px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-rose-500/10 text-rose-400 border border-rose-500/20">
              <AlertTriangle className="h-5 w-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-bold text-white tracking-tight">
                  Exception Triage & Investigation Workspace
                </h2>
                <span className={cn(
                  "text-[10px] font-bold px-2.5 py-0.5 rounded-full border",
                  currentException.severity === "HIGH" 
                    ? "bg-rose-500/10 text-rose-400 border-rose-500/30" 
                    : currentException.severity === "MEDIUM"
                    ? "bg-amber-500/10 text-amber-400 border-amber-500/30"
                    : "bg-blue-500/10 text-blue-400 border-blue-500/30"
                )}>
                  {currentException.severity} SEVERITY
                </span>
                <span className="text-[10px] font-mono bg-gray-800 text-gray-300 px-2 py-0.5 rounded border border-gray-700">
                  {currentException.exception_type}
                </span>
              </div>
              <p className="mt-0.5 text-xs text-gray-400 font-mono">
                ID: <span className="text-gray-200">{currentException.exception_id}</span> • Run: <span className="text-gray-200">{currentException.run_id}</span>
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="rounded-lg p-2 text-gray-400 hover:bg-gray-800 hover:text-white transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Modal Body - Scrollable Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          
          {/* Top Quick Numbers */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="rounded-xl border border-border/80 bg-background/40 p-3.5">
              <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider block">Principal Amount Involved</span>
              <span className="text-xl font-bold text-white mt-1 block">{formatCurrency(grossAmt)}</span>
              <span className="text-[10px] text-gray-500 mt-0.5 block">Total transaction face value</span>
            </div>

            <div className="rounded-xl border border-rose-500/30 bg-rose-500/5 p-3.5">
              <span className="text-[11px] font-semibold text-rose-400 uppercase tracking-wider block">Discrepancy / Delta</span>
              <span className="text-xl font-bold text-rose-400 mt-1 block">
                {currentException.amount_discrepancy > 0 ? formatCurrency(currentException.amount_discrepancy) : "₹0.00"}
              </span>
              <span className="text-[10px] text-gray-400 mt-0.5 block">Monetary variance between sources</span>
            </div>

            <div className="rounded-xl border border-border/80 bg-background/40 p-3.5">
              <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider block">Current Workflow State</span>
              <div className="flex items-center gap-2 mt-1">
                <span className={cn(
                  "text-xs font-bold px-2.5 py-1 rounded-lg border",
                  currentException.status === "OPEN" ? "bg-rose-500/10 text-rose-400 border-rose-500/30" :
                  currentException.status === "IN_REVIEW" ? "bg-amber-500/10 text-amber-400 border-amber-500/30" :
                  currentException.status === "RESOLVED" ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30" :
                  "bg-gray-800 text-gray-400 border-gray-700"
                )}>
                  {currentException.status}
                </span>
                {currentException.resolved_by && (
                  <span className="text-[11px] text-gray-400">by {currentException.resolved_by}</span>
                )}
              </div>
            </div>
          </div>

          {/* 1. 3-WAY LEDGER COMPARISON CARD */}
          <div className="rounded-xl border border-border bg-background/50 p-4 space-y-3">
            <div className="flex items-center justify-between border-b border-border/60 pb-2.5">
              <div className="flex items-center gap-2">
                <Scale className="h-4 w-4 text-indigo-400" />
                <h3 className="text-xs font-bold text-white uppercase tracking-wider">
                  3-Way Ledger Triangulation
                </h3>
              </div>
              <span className="text-[11px] text-gray-400">Bank vs Gateway vs ERP Invoice</span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              
              {/* Bank Statement Leg */}
              <div className={cn(
                "rounded-xl border p-3.5 flex flex-col justify-between space-y-3 transition-all",
                currentException.bank_txn_id 
                  ? "bg-card border-indigo-500/30" 
                  : "bg-rose-950/10 border-rose-500/30 border-dashed"
              )}>
                <div>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5 text-xs font-bold text-white">
                      <Building className="h-3.5 w-3.5 text-indigo-400" />
                      Bank Statement
                    </div>
                    {currentException.bank_txn_id ? (
                      <span className="text-[10px] bg-emerald-500/10 text-emerald-400 px-1.5 py-0.5 rounded border border-emerald-500/30 font-semibold flex items-center gap-1">
                        <Check className="h-3 w-3" /> Linked
                      </span>
                    ) : (
                      <span className="text-[10px] bg-rose-500/10 text-rose-400 px-1.5 py-0.5 rounded border border-rose-500/30 font-semibold">
                        Missing Leg
                      </span>
                    )}
                  </div>
                  
                  <div className="mt-3 space-y-1.5 text-xs">
                    <div className="text-gray-400 flex justify-between">
                      <span>Txn ID:</span>
                      <span className="font-mono text-gray-200">{cleanId(currentException.bank_txn_id)}</span>
                    </div>
                    <div className="text-gray-400 flex justify-between">
                      <span>Cleared Amount:</span>
                      <span className="font-bold text-white">
                        {currentException.bank_transaction ? formatCurrency(currentException.bank_transaction.amount) : formatCurrency(actualBankAmt)}
                      </span>
                    </div>
                    <div className="text-gray-400 flex justify-between">
                      <span>Date:</span>
                      <span className="text-gray-300">
                        {currentException.bank_transaction?.transaction_date ? formatDate(currentException.bank_transaction.transaction_date) : "Pending Clearance"}
                      </span>
                    </div>
                  </div>
                </div>
                {currentException.bank_transaction?.description && (
                  <p className="text-[10px] text-gray-400 bg-background/60 p-2 rounded border border-border/60 line-clamp-2">
                    {currentException.bank_transaction.description}
                  </p>
                )}
              </div>

              {/* Gateway Transaction Leg */}
              <div className={cn(
                "rounded-xl border p-3.5 flex flex-col justify-between space-y-3 transition-all",
                currentException.gateway_txn_id 
                  ? "bg-card border-purple-500/30" 
                  : "bg-rose-950/10 border-rose-500/30 border-dashed"
              )}>
                <div>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5 text-xs font-bold text-white">
                      <CreditCard className="h-3.5 w-3.5 text-purple-400" />
                      Payment Gateway
                    </div>
                    {currentException.gateway_txn_id ? (
                      <span className="text-[10px] bg-emerald-500/10 text-emerald-400 px-1.5 py-0.5 rounded border border-emerald-500/30 font-semibold flex items-center gap-1">
                        <Check className="h-3 w-3" /> Captured
                      </span>
                    ) : (
                      <span className="text-[10px] bg-rose-500/10 text-rose-400 px-1.5 py-0.5 rounded border border-rose-500/30 font-semibold">
                        Missing Leg
                      </span>
                    )}
                  </div>

                  <div className="mt-3 space-y-1.5 text-xs">
                    <div className="text-gray-400 flex justify-between">
                      <span>Gateway Ref:</span>
                      <span className="font-mono text-gray-200">{cleanId(currentException.gateway_txn_id)}</span>
                    </div>
                    <div className="text-gray-400 flex justify-between">
                      <span>Captured Gross:</span>
                      <span className="font-bold text-white">
                        {currentException.gateway_transaction ? formatCurrency(currentException.gateway_transaction.amount) : formatCurrency(grossAmt)}
                      </span>
                    </div>
                    <div className="text-gray-400 flex justify-between">
                      <span>Customer:</span>
                      <span className="text-gray-300 truncate max-w-[120px]">
                        {currentException.gateway_transaction?.customer_name || "Merchant Settlement"}
                      </span>
                    </div>
                  </div>
                </div>
                {currentException.gateway_transaction?.status && (
                  <p className="text-[10px] text-gray-400 bg-background/60 p-2 rounded border border-border/60">
                    Status: <strong className="text-purple-300">{currentException.gateway_transaction.status}</strong>
                  </p>
                )}
              </div>

              {/* ERP Invoice Leg */}
              <div className={cn(
                "rounded-xl border p-3.5 flex flex-col justify-between space-y-3 transition-all",
                currentException.invoice_id 
                  ? "bg-card border-blue-500/30" 
                  : "bg-rose-950/10 border-rose-500/30 border-dashed"
              )}>
                <div>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5 text-xs font-bold text-white">
                      <FileText className="h-3.5 w-3.5 text-blue-400" />
                      ERP Invoice
                    </div>
                    {currentException.invoice_id ? (
                      <span className="text-[10px] bg-emerald-500/10 text-emerald-400 px-1.5 py-0.5 rounded border border-emerald-500/30 font-semibold flex items-center gap-1">
                        <Check className="h-3 w-3" /> Invoiced
                      </span>
                    ) : (
                      <span className="text-[10px] bg-rose-500/10 text-rose-400 px-1.5 py-0.5 rounded border border-rose-500/30 font-semibold">
                        Missing Leg
                      </span>
                    )}
                  </div>

                  <div className="mt-3 space-y-1.5 text-xs">
                    <div className="text-gray-400 flex justify-between">
                      <span>Invoice ID:</span>
                      <span className="font-mono text-gray-200">{cleanId(currentException.invoice_id)}</span>
                    </div>
                    <div className="text-gray-400 flex justify-between">
                      <span>Invoice Amount:</span>
                      <span className="font-bold text-white">
                        {currentException.invoice ? formatCurrency(currentException.invoice.amount) : formatCurrency(grossAmt)}
                      </span>
                    </div>
                    <div className="text-gray-400 flex justify-between">
                      <span>Client Account:</span>
                      <span className="text-gray-300 truncate max-w-[120px]">
                        {currentException.invoice?.customer_name || "Enterprise Client"}
                      </span>
                    </div>
                  </div>
                </div>
                {currentException.invoice?.status && (
                  <p className="text-[10px] text-gray-400 bg-background/60 p-2 rounded border border-border/60">
                    ERP Status: <strong className="text-blue-300">{currentException.invoice.status}</strong>
                  </p>
                )}
              </div>

            </div>
          </div>

          {/* 2. SETTLEMENT MATH FORMULA CARD */}
          <div className="rounded-xl border border-indigo-500/30 bg-gradient-to-br from-indigo-950/30 via-card to-background p-4 space-y-3">
            <div className="flex items-center justify-between border-b border-indigo-500/20 pb-2.5">
              <div className="flex items-center gap-2">
                <Calculator className="h-4 w-4 text-indigo-400" />
                <h3 className="text-xs font-bold text-white uppercase tracking-wider">
                  Settlement Math Breakdown & Variance Formula
                </h3>
              </div>
              <span className="text-[10px] bg-indigo-500/20 text-indigo-300 px-2 py-0.5 rounded border border-indigo-500/30 font-mono">
                Formula: Expected Net vs Actual Bank Deposit
              </span>
            </div>

            {/* Formula display ribbon */}
            <div className="bg-background/80 rounded-xl p-3 border border-border text-xs font-mono flex flex-wrap items-center justify-between gap-2">
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="text-gray-400">Gross</span>
                <span className="font-bold text-white">({formatCurrency(grossAmt)})</span>
                <span className="text-indigo-400 font-bold">-</span>
                <span className="text-gray-400">Fee</span>
                <span className="font-bold text-amber-400">({formatCurrency(mdrFee)})</span>
                <span className="text-indigo-400 font-bold">-</span>
                <span className="text-gray-400">GST</span>
                <span className="font-bold text-amber-400">({formatCurrency(gstFee)})</span>
                <span className="text-indigo-400 font-bold">=</span>
                <span className="text-gray-400">Expected Net</span>
                <span className="font-bold text-emerald-400">({formatCurrency(expectedNet)})</span>
              </div>
              
              <div className="flex items-center gap-2 text-xs">
                <span className="text-gray-400">vs Actual Deposit:</span>
                <span className="font-bold text-white">{formatCurrency(actualBankAmt)}</span>
                <span className="text-gray-500">|</span>
                <span className="text-gray-400">Variance:</span>
                <span className={cn("font-bold", variance > 0.05 ? "text-rose-400" : "text-emerald-400")}>
                  {formatCurrency(variance)}
                </span>
              </div>
            </div>

            {/* Sub-components breakdown grid */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 text-xs">
              <div className="rounded-lg bg-background/50 p-2.5 border border-border/60">
                <span className="text-[10px] text-gray-500 block">Gross Capture</span>
                <span className="text-sm font-bold text-white">{formatCurrency(grossAmt)}</span>
                <span className="text-[10px] text-gray-400 block mt-0.5">100.00%</span>
              </div>

              <div className="rounded-lg bg-background/50 p-2.5 border border-border/60">
                <span className="text-[10px] text-amber-400/80 block">Gateway MDR (2.0%)</span>
                <span className="text-sm font-bold text-amber-400">-{formatCurrency(mdrFee)}</span>
                <span className="text-[10px] text-gray-400 block mt-0.5">Base Gateway Fee</span>
              </div>

              <div className="rounded-lg bg-background/50 p-2.5 border border-border/60">
                <span className="text-[10px] text-amber-400/80 block">GST (18% on MDR)</span>
                <span className="text-sm font-bold text-amber-400">-{formatCurrency(gstFee)}</span>
                <span className="text-[10px] text-gray-400 block mt-0.5">Statutory Tax</span>
              </div>

              <div className="rounded-lg bg-background/50 p-2.5 border border-border/60">
                <span className="text-[10px] text-emerald-400/80 block">Calculated Net Settlement</span>
                <span className="text-sm font-bold text-emerald-400">{formatCurrency(expectedNet)}</span>
                <span className="text-[10px] text-gray-400 block mt-0.5">Effective 97.64%</span>
              </div>
            </div>
          </div>

          {/* 3. AI INVESTIGATOR PANEL */}
          <div className="rounded-xl border border-indigo-500/40 bg-gradient-to-br from-card via-card to-indigo-950/20 p-4 space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-border/80 pb-3">
              <div className="flex items-center gap-2">
                <Sparkles className="h-5 w-5 text-primary-light animate-pulse" />
                <h3 className="text-sm font-bold text-white tracking-tight">
                  Autonomous AI Investigation Engine
                </h3>
              </div>

              {investigation ? (
                <div className="flex items-center gap-2">
                  <span className="text-xs bg-primary/20 text-primary-light px-3 py-1 rounded-full border border-primary/40 font-semibold flex items-center gap-1.5">
                    <ShieldCheck className="h-3.5 w-3.5" />
                    {formatPercent(investigation.confidence)} Confidence
                  </span>
                  <span className={cn(
                    "text-xs px-2.5 py-1 rounded-full font-bold border",
                    investigation.recommendation === "MARK_RECONCILED" 
                      ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                      : investigation.recommendation === "ESCALATE"
                      ? "bg-rose-500/10 text-rose-400 border-rose-500/30"
                      : "bg-amber-500/10 text-amber-400 border-amber-500/30"
                  )}>
                    REC: {investigation.recommendation}
                  </span>
                </div>
              ) : (
                <button
                  onClick={handleRunInvestigation}
                  disabled={isInvestigating}
                  className="flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-xs font-bold text-white hover:bg-primary-hover transition-all shadow-sm glow-primary disabled:opacity-50"
                >
                  <Sparkles className={cn("h-3.5 w-3.5", isInvestigating && "animate-spin")} />
                  {isInvestigating ? "Investigating Record..." : "Run AI Investigation"}
                </button>
              )}
            </div>

            {investigation ? (
              <div className="space-y-3 text-xs">
                
                {/* Proposed Classification & Root Cause Explanation */}
                <div className="rounded-xl bg-background/60 border border-border p-3.5 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-semibold text-gray-400 uppercase">
                      Classification & Root Cause Analysis
                    </span>
                    <span className="font-mono text-[10px] text-primary-light font-bold">
                      {investigation.classification}
                    </span>
                  </div>
                  <p className="text-xs text-gray-200 leading-relaxed font-medium">
                    {investigation.explanation}
                  </p>
                </div>

                {/* Policy Citations Tag */}
                {investigation.policy_references && investigation.policy_references.length > 0 && (
                  <div className="space-y-1.5">
                    <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider block">
                      Policy & Compliance Citations
                    </span>
                    <div className="flex flex-wrap gap-1.5">
                      {investigation.policy_references.map((policy, idx) => (
                        <span
                          key={idx}
                          className="rounded-md bg-indigo-500/10 border border-indigo-500/20 px-2.5 py-1 text-[11px] font-medium text-indigo-300 flex items-center gap-1"
                        >
                          <Info className="h-3 w-3 text-indigo-400" />
                          {policy}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* 1-Click Action Buttons Strip inside AI Panel */}
                <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-border/60">
                  <div className="text-[11px] text-gray-400">
                    {investigation.requires_human_review 
                      ? "⚠️ Recommendation requires operator concurrence before closing."
                      : "✅ High certainty match — safe for instant 1-click reconciliation."}
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      disabled={isRejecting || isApproving}
                      onClick={() => setShowRejectPrompt(true)}
                      className="flex items-center gap-1.5 rounded-lg border border-rose-500/40 bg-rose-500/10 px-3.5 py-2 text-xs font-bold text-rose-300 hover:bg-rose-500/20 hover:text-white transition-all disabled:opacity-50"
                    >
                      <Ban className="h-3.5 w-3.5" />
                      Reject & Escalate
                    </button>

                    <button
                      type="button"
                      disabled={isApproving || isRejecting}
                      onClick={handleApprove}
                      className="flex items-center gap-1.5 rounded-lg bg-emerald-600 px-4 py-2 text-xs font-bold text-white hover:bg-emerald-500 transition-all shadow-md glow-emerald disabled:opacity-50"
                    >
                      <CheckCircle2 className="h-4 w-4" />
                      {isApproving ? "Approving..." : "Approve Resolution"}
                    </button>
                  </div>
                </div>

              </div>
            ) : (
              <div className="rounded-xl border border-dashed border-border bg-background/30 p-6 text-center text-xs text-gray-400">
                Click &ldquo;Run AI Investigation&rdquo; to analyze settlement formulas, detect merchant fees, and evaluate compliance policies.
              </div>
            )}
          </div>

          {/* 4. EVIDENCE CHAIN SECTION (Expandable Audit Badges) */}
          <div className="rounded-xl border border-border bg-background/40 p-4 space-y-3">
            <div 
              onClick={() => setExpandedEvidence(!expandedEvidence)}
              className="flex items-center justify-between cursor-pointer select-none"
            >
              <div className="flex items-center gap-2">
                <ShieldCheck className="h-4 w-4 text-emerald-400" />
                <h3 className="text-xs font-bold text-white uppercase tracking-wider">
                  Audit Evidence Chain ({evidenceList.length} Verified Assertions)
                </h3>
              </div>
              <button type="button" className="text-gray-400 hover:text-white">
                {expandedEvidence ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
              </button>
            </div>

            {expandedEvidence && (
              <div className="space-y-2 pt-1">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {evidenceList.map((item, idx) => (
                    <div
                      key={idx}
                      className="flex items-start gap-2 rounded-lg bg-card p-2.5 border border-border/80 text-xs text-gray-300 font-mono"
                    >
                      <span className="h-2 w-2 rounded-full bg-emerald-400 mt-1.5 shrink-0" />
                      <span className="leading-relaxed">{item}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* 5. MANUAL LIFECYCLE CONTROLS & AUDIT NOTES */}
          <div className="rounded-xl border border-border bg-background/40 p-4 space-y-3">
            <h3 className="text-xs font-bold text-gray-300 uppercase tracking-wider">
              Operator Lifecycle Management & Audit Notes
            </h3>

            <div>
              <label className="block text-xs font-semibold text-gray-400 mb-2">Set Workflow Status</label>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                {[
                  { key: "OPEN", label: "Open", icon: AlertTriangle, color: "hover:border-rose-500 text-rose-400" },
                  { key: "IN_REVIEW", label: "In Review", icon: Clock, color: "hover:border-amber-500 text-amber-400" },
                  { key: "RESOLVED", label: "Resolved", icon: CheckCircle2, color: "hover:border-emerald-500 text-emerald-400" },
                  { key: "IGNORED", label: "Ignored", icon: EyeOff, color: "hover:border-gray-500 text-gray-400" },
                ].map((s) => {
                  const Icon = s.icon;
                  const isSelected = status === s.key;
                  return (
                    <button
                      key={s.key}
                      type="button"
                      onClick={() => setStatus(s.key)}
                      className={cn(
                        "flex items-center justify-center gap-1.5 py-2 px-3 rounded-lg border text-xs font-medium transition-all",
                        isSelected
                          ? "bg-gray-800 border-primary text-white font-bold shadow-sm ring-1 ring-primary"
                          : "border-border bg-background/40 text-gray-400 hover:bg-gray-800 hover:text-white"
                      )}
                    >
                      <Icon className={cn("h-3.5 w-3.5", s.color)} />
                      {s.label}
                    </button>
                  );
                })}
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-400 mb-1">Resolution Audit Notes</label>
              <textarea
                rows={2}
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Add manual notes or actions taken..."
                className="w-full rounded-lg border border-border bg-background/60 p-2.5 text-xs text-white placeholder-gray-500 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>
          </div>

          {/* Rejection Prompt Modal Input (if active) */}
          {showRejectPrompt && (
            <div className="rounded-xl border border-rose-500/40 bg-rose-950/30 p-4 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-rose-300 flex items-center gap-1.5">
                  <ShieldAlert className="h-4 w-4 text-rose-400" />
                  Reason for Rejection & Escalation:
                </span>
                <button 
                  onClick={() => setShowRejectPrompt(false)}
                  className="text-xs text-gray-400 hover:text-white"
                >
                  Cancel
                </button>
              </div>
              <input
                type="text"
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                placeholder="e.g. Unexplained variance exceeds tolerance; suspect fraud or missing gateway invoice..."
                className="w-full rounded-lg border border-rose-500/40 bg-background/80 p-2.5 text-xs text-white placeholder-gray-500 focus:border-rose-400 focus:outline-none"
              />
              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowRejectPrompt(false)}
                  className="rounded-lg bg-gray-800 px-3 py-1.5 text-xs text-gray-300 hover:bg-gray-700"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  disabled={isRejecting || !rejectReason.trim()}
                  onClick={handleReject}
                  className="rounded-lg bg-rose-600 px-3.5 py-1.5 text-xs font-bold text-white hover:bg-rose-500 disabled:opacity-50"
                >
                  {isRejecting ? "Escalating..." : "Confirm Rejection & Escalate"}
                </button>
              </div>
            </div>
          )}

          {error && (
            <div className="rounded-lg bg-rose-500/10 border border-rose-500/30 p-3 text-xs text-rose-400">
              {error}
            </div>
          )}

        </div>

        {/* Modal Footer */}
        <div className="flex items-center justify-between border-t border-border/80 bg-background/50 px-6 py-4">
          <div className="text-xs text-gray-400">
            Last Updated: {formatDate(currentException.updated_at || currentException.created_at)}
          </div>

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg bg-gray-800 px-4 py-2 text-xs font-medium text-gray-300 hover:bg-gray-700 transition-colors"
            >
              Close
            </button>
            <button
              type="button"
              disabled={saving}
              onClick={handleSave}
              className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-xs font-bold text-white hover:bg-primary-hover transition-colors disabled:opacity-50 shadow-md glow-primary"
            >
              <Save className="h-4 w-4" />
              {saving ? "Saving..." : "Save Triage Record"}
            </button>
          </div>
        </div>

      </div>
    </div>
  );
}
