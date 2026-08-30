"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { 
  Play, 
  Sparkles, 
  Database, 
  Activity, 
  CheckCircle2, 
  AlertTriangle, 
  Layers, 
  Clock, 
  TrendingUp, 
  Target, 
  ArrowRight,
  ShieldAlert,
  BarChart,
  RefreshCw,
  Upload,
  RotateCcw,
  Scale,
  CopyCheck,
  CheckCheck
} from "lucide-react";
import { MetricsSummary } from "@/types";
import { fetchMetrics, generateSyntheticData, triggerReconciliation, resetReconciliation } from "@/lib/api";
import { KPICard } from "@/components/kpi-card";
import { StatusDonutChart } from "@/components/charts/status-donut-chart";
import { ExceptionsBarChart } from "@/components/charts/exceptions-bar-chart";
import { SeverityChart } from "@/components/charts/severity-chart";
import { formatCurrency, formatPercent, cn } from "@/lib/utils";

export default function DashboardPage() {
  const [metrics, setMetrics] = useState<MetricsSummary | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [isReconciling, setIsReconciling] = useState<boolean>(false);
  const [isResetting, setIsResetting] = useState<boolean>(false);
  const [useAi, setUseAi] = useState<boolean>(true);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  const loadData = async () => {
    setLoading(true);
    try {
      const datasetId = typeof window !== "undefined" ? localStorage.getItem("latest_dataset_id") || undefined : undefined;
      const data = await fetchMetrics(datasetId);
      setMetrics(data);
    } catch (err: any) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleGenerateData = async (count: number = 250) => {
    setIsGenerating(true);
    setStatusMessage(`Generating realistic dataset of ${count} multi-source records...`);
    try {
      const res = await generateSyntheticData(count);
      setStatusMessage(`Dataset generated: ${res.bank_records_count} Bank, ${res.gateway_records_count} Gateway, ${res.invoice_records_count} Invoices.`);
      localStorage.removeItem("latest_dataset_id");
      await loadData();
    } catch (err: any) {
      setStatusMessage(`Generation failed: ${err.message}`);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleRunReconciliation = async () => {
    setIsReconciling(true);
    setStatusMessage("Executing reconciliation pipeline (Candidate Generation -> Scoring -> AI Verification)...");
    try {
      const datasetId = typeof window !== "undefined" ? localStorage.getItem("latest_dataset_id") || undefined : undefined;
      const res = await triggerReconciliation(useAi, datasetId);
      setStatusMessage(`Reconciliation completed in ${res.processing_time_ms}ms: ${res.matched_count} matched, ${res.exception_count} exceptions.`);
      await loadData();
    } catch (err: any) {
      setStatusMessage(`Reconciliation failed: ${err.message}`);
    } finally {
      setIsReconciling(false);
    }
  };

  const handleResetAnalysis = async (clearAllData: boolean = true) => {
    const confirmText = "Reset all data and previous analysis to start 100% fresh? This will remove all uploaded transactions, matches, and exceptions.";
    if (!window.confirm(confirmText)) return;

    setIsResetting(true);
    setStatusMessage("Clearing all data and resetting pipeline...");
    try {
      await resetReconciliation(undefined, true);
      if (typeof window !== "undefined") {
        localStorage.removeItem("latest_dataset_id");
      }
      setMetrics(null);
      setStatusMessage("All data cleared successfully. Ready for fresh upload or demo data.");
      await loadData();
    } catch (err: any) {
      setStatusMessage(`Reset failed: ${err.message}`);
    } finally {
      setIsResetting(false);
    }
  };

  // Computed production metrics
  const settlementVarianceExposure = metrics?.settlement_variance_exposure ?? metrics?.total_exception_volume ?? 0;
  const matchedVolume = metrics?.total_matched_volume ?? 0;
  const reviewCount = metrics?.review_count ?? 
    metrics?.status_distribution?.find(s => s.name === "REVIEW")?.value ?? 0;
  const exceptionCount = metrics?.exception_count ?? 
    metrics?.status_distribution?.find(s => s.name === "EXCEPTION")?.value ?? 0;
  const duplicateCount = metrics?.duplicate_detection_count ?? metrics?.duplicate_count ??
    metrics?.status_distribution?.find(s => s.name === "DUPLICATE")?.value ?? 0;
  const missingCount = metrics?.status_distribution?.find(s => s.name === "MISSING")?.value ?? 0;
  const matchedCount = metrics?.matched_count ?? 
    metrics?.status_distribution?.find(s => s.name === "MATCH")?.value ?? 0;
  const totalCount = metrics?.total_records || (matchedCount + reviewCount + exceptionCount + duplicateCount + missingCount);

  // Exception exposure breakdown
  const amountMismatchItem = metrics?.exceptions_by_type?.find(e => e.type.includes("AMOUNT_MISMATCH"));
  const missingBankItem = metrics?.exceptions_by_type?.find(e => e.type.includes("MISSING_BANK") || e.type.includes("NO_MATCH"));
  const feeVarianceItem = metrics?.exceptions_by_type?.find(e => e.type.includes("MDR_FEE") || e.type.includes("FEE"));
  const duplicateItem = metrics?.exceptions_by_type?.find(e => e.type.includes("DUPLICATE"));
  const highRiskItem = metrics?.severity_distribution?.find(s => s.severity === "HIGH");
  const mediumRiskItem = metrics?.severity_distribution?.find(s => s.severity === "MEDIUM");

  return (
    <div className="space-y-8">
      
      {/* Top Header & Operational Control Bar */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6 border-b border-border pb-6">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-2xl sm:text-[28px] font-bold tracking-tight text-content">
              Financial Control Center
            </h1>
            <span className="bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/25 px-2.5 py-0.5 rounded-full text-xs font-semibold">
              ● Active Ledger
            </span>
          </div>
          <p className="mt-1 text-sm text-content-secondary max-w-2xl">
            Monitor 3-way reconciliation health, settlement exposure, exceptions, and cash position across Bank, Gateway, and ERP sources.
          </p>
        </div>

        {/* Action Button Hierarchy */}
        <div className="flex flex-wrap items-center gap-2.5">
          {/* AI Toggle */}
          <div className="flex items-center gap-2 rounded-xl bg-surface-secondary border border-border px-3 py-2 text-xs shadow-xs">
            <Sparkles className={cn("h-3.5 w-3.5", useAi ? "text-ai-light" : "text-content-muted")} />
            <span className="text-content-secondary font-medium">AI Advisory</span>
            <button
              type="button"
              onClick={() => setUseAi(!useAi)}
              className={cn(
                "relative inline-flex h-4 w-7 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus-ring",
                useAi ? "bg-primary" : "bg-slate-300 dark:bg-gray-700"
              )}
              aria-label="Toggle AI Advisory"
            >
              <span
                className={cn(
                  "pointer-events-none inline-block h-3 w-3 transform rounded-full bg-white shadow-sm ring-0 transition duration-200 ease-in-out",
                  useAi ? "translate-x-3" : "translate-x-0"
                )}
              />
            </button>
          </div>

          {/* Tertiary / Utility Buttons */}
          <button
            onClick={() => handleResetAnalysis(true)}
            disabled={isResetting || isReconciling || isGenerating}
            className="flex items-center gap-1.5 rounded-xl border border-border bg-surface-secondary px-3 py-2 text-xs font-semibold text-content-secondary hover:text-rose-600 dark:hover:text-rose-300 hover:border-rose-500/40 hover:bg-rose-500/10 transition-all disabled:opacity-40 focus-ring shadow-xs"
            title="Reset all ledger records to start fresh"
          >
            <RotateCcw className={cn("h-3.5 w-3.5", isResetting && "animate-spin")} />
            Reset
          </button>

          <button
            onClick={() => handleGenerateData(250)}
            disabled={isGenerating || isReconciling}
            className="flex items-center gap-1.5 rounded-xl border border-border bg-surface-secondary px-3 py-2 text-xs font-semibold text-content-secondary hover:bg-surface-elevated hover:text-content transition-all disabled:opacity-40 focus-ring shadow-xs"
          >
            <Database className={cn("h-3.5 w-3.5", isGenerating && "animate-spin")} />
            Demo Data
          </button>

          {/* Secondary CTA: Upload Data */}
          <Link
            href="/upload"
            className="flex items-center gap-1.5 rounded-xl border border-border-strong bg-surface-elevated px-3.5 py-2 text-xs font-semibold text-content hover:bg-surface transition-all focus-ring shadow-xs"
          >
            <Upload className="h-3.5 w-3.5 text-content-secondary" />
            Upload Data
          </Link>

          {/* Primary CTA: Run Reconciliation */}
          <button
            onClick={handleRunReconciliation}
            disabled={isReconciling || isGenerating}
            className="flex items-center gap-2 rounded-xl bg-primary px-4 py-2 text-xs font-bold text-white hover:bg-primary-hover transition-all shadow-sm disabled:opacity-50 focus-ring"
          >
            <Play className={cn("h-3.5 w-3.5 fill-current", isReconciling && "animate-spin")} />
            {isReconciling ? "Reconciling..." : "Run Reconciliation"}
          </button>
        </div>
      </div>

      {/* Status Toast Message */}
      {statusMessage && (
        <div className="rounded-lg bg-surface-secondary border border-border px-4 py-2.5 text-xs text-content flex items-center justify-between shadow-xs">
          <div className="flex items-center gap-2">
            <RefreshCw className={cn("h-3.5 w-3.5 text-primary-light", (isGenerating || isReconciling) && "animate-spin")} />
            <span>{statusMessage}</span>
          </div>
          <button onClick={() => setStatusMessage(null)} className="text-content-muted hover:text-content text-xs">
            Dismiss
          </button>
        </div>
      )}

      {/* 6 Financial Operations KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-3">
        
        {/* Match Rate Card */}
        <KPICard
          title="Match Rate"
          value={`${metrics?.match_rate_pct ?? 0}%`}
          subtitle={totalCount > 0 ? `${matchedCount} of ${totalCount} reconciled` : "Awaiting data"}
          icon={<CheckCircle2 className="h-4 w-4 text-emerald-400" />}
          variant="success"
        />

        {/* Matched Volume Card */}
        <KPICard
          title="Matched Volume"
          value={formatCurrency(matchedVolume)}
          subtitle={`${matchedCount} verified records`}
          icon={<CheckCheck className="h-4 w-4 text-emerald-400" />}
          variant="default"
        />

        {/* Needs Review Card */}
        <KPICard
          title="Needs Review"
          value={reviewCount}
          subtitle="Controller review needed"
          icon={<AlertTriangle className="h-4 w-4 text-amber-400" />}
          variant={reviewCount > 0 ? "warning" : "default"}
        />

        {/* Exception Exposure Card */}
        <KPICard
          title="Exception Exposure"
          value={formatCurrency(settlementVarianceExposure)}
          subtitle={`${exceptionCount} active exceptions`}
          icon={<Scale className="h-4 w-4 text-rose-400" />}
          variant={settlementVarianceExposure > 0 ? "danger" : "default"}
        />

        {/* Settlement Variance Card */}
        <KPICard
          title="Settlement Variance"
          value={formatCurrency(metrics?.total_exception_volume ?? 0)}
          subtitle="Unexplained net delta"
          icon={<ShieldAlert className="h-4 w-4 text-indigo-400" />}
          variant="default"
        />

        {/* Throughput Speed Card */}
        <KPICard
          title="Throughput"
          value={`${metrics?.throughput_rps ?? 0} rps`}
          subtitle={`Latency: ${metrics?.processing_time_ms ?? 0} ms`}
          icon={<TrendingUp className="h-4 w-4 text-primary-light" />}
          variant="default"
        />

      </div>

      {/* Ground Truth Benchmark Performance (When Hidden Evaluation Available) */}
      {metrics?.evaluation && metrics.evaluation.has_evaluation && (
        <div className="rounded-xl border border-indigo-500/30 bg-surface-secondary p-5 shadow-sm">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-border pb-3">
            <div className="flex items-center gap-2">
              <Target className="h-4 w-4 text-indigo-400" />
              <h2 className="text-sm font-semibold text-white">
                Reconciliation Audit Benchmark (Ground-Truth Inference)
              </h2>
            </div>
            <span className="text-[11px] font-mono text-indigo-300 bg-indigo-500/10 px-2 py-0.5 rounded border border-indigo-500/25">
              Zero-Leakage Empirical Verification
            </span>
          </div>

          <div className="mt-4 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 text-center">
            <div className="rounded-lg bg-surface p-3 border border-border">
              <span className="text-[10px] text-gray-400 uppercase font-semibold">Precision</span>
              <div className="text-lg font-bold text-emerald-400 mt-1 tabular-nums">
                {formatPercent(metrics.evaluation.precision)}
              </div>
              <span className="text-[10px] text-gray-500">TP / (TP + FP)</span>
            </div>

            <div className="rounded-lg bg-surface p-3 border border-border">
              <span className="text-[10px] text-gray-400 uppercase font-semibold">Recall</span>
              <div className="text-lg font-bold text-indigo-300 mt-1 tabular-nums">
                {formatPercent(metrics.evaluation.recall)}
              </div>
              <span className="text-[10px] text-gray-500">TP / (TP + FN)</span>
            </div>

            <div className="rounded-lg bg-surface p-3 border border-border">
              <span className="text-[10px] text-gray-400 uppercase font-semibold">F1 Score</span>
              <div className="text-lg font-bold text-primary-light mt-1 tabular-nums">
                {formatPercent(metrics.evaluation.f1_score)}
              </div>
              <span className="text-[10px] text-gray-500">Harmonic Mean</span>
            </div>

            <div className="rounded-lg bg-surface p-3 border border-border">
              <span className="text-[10px] text-gray-400 uppercase font-semibold">Accuracy</span>
              <div className="text-lg font-bold text-white mt-1 tabular-nums">
                {formatPercent(metrics.evaluation.accuracy)}
              </div>
              <span className="text-[10px] text-gray-500">(TP + TN) / Total</span>
            </div>

            <div className="rounded-lg bg-surface p-3 border border-border">
              <span className="text-[10px] text-gray-400 uppercase font-semibold">False Positives</span>
              <div className="text-lg font-bold text-emerald-400 mt-1 tabular-nums">
                {formatPercent(metrics.evaluation.false_positive_rate)}
              </div>
              <span className="text-[10px] text-gray-500">FP / (FP + TN)</span>
            </div>

            <div className="rounded-lg bg-surface p-3 border border-border">
              <span className="text-[10px] text-gray-400 uppercase font-semibold">Anomaly Catch</span>
              <div className="text-lg font-bold text-amber-400 mt-1 tabular-nums">
                {formatPercent(metrics.evaluation.exception_detection_accuracy)}
              </div>
              <span className="text-[10px] text-gray-500">Caught Rate</span>
            </div>
          </div>
        </div>
      )}

      {/* Main Analysis Grid: Status Breakdown & Exception Exposure */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Status Breakdown with Side-by-Side Counters */}
        <div className="rounded-xl border border-border bg-surface-secondary p-5 shadow-xs lg:col-span-1 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between border-b border-border pb-3 mb-4">
              <div>
                <h3 className="text-sm font-semibold text-content">Reconciliation Status</h3>
                <p className="text-xs text-content-secondary">Distribution across full ledger</p>
              </div>
              <span className="text-xs font-mono text-content-secondary bg-surface px-2 py-0.5 rounded border border-border">
                {totalCount} Total
              </span>
            </div>

            {/* Donut Chart */}
            <StatusDonutChart data={metrics?.status_distribution || []} />
          </div>

          {/* Direct Numerical Breakdown List (No Hover Required) */}
          <div className="mt-4 space-y-2 border-t border-border pt-4 text-xs">
            <div className="flex items-center justify-between p-1.5 rounded hover:bg-surface transition-colors">
              <div className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 rounded-full bg-emerald-500" />
                <span className="font-medium text-content">MATCH (Reconciled)</span>
              </div>
              <div className="flex items-center gap-3 tabular-nums">
                <span className="font-bold text-content">{matchedCount}</span>
                <span className="text-content-secondary font-mono w-12 text-right">
                  {totalCount > 0 ? `${((matchedCount / totalCount) * 100).toFixed(1)}%` : "0%"}
                </span>
              </div>
            </div>

            <div className="flex items-center justify-between p-1.5 rounded hover:bg-surface transition-colors">
              <div className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 rounded-full bg-amber-500" />
                <span className="font-medium text-content">REVIEW (Discrepancy)</span>
              </div>
              <div className="flex items-center gap-3 tabular-nums">
                <span className="font-bold text-amber-600 dark:text-amber-300">{reviewCount}</span>
                <span className="text-content-secondary font-mono w-12 text-right">
                  {totalCount > 0 ? `${((reviewCount / totalCount) * 100).toFixed(1)}%` : "0%"}
                </span>
              </div>
            </div>

            <div className="flex items-center justify-between p-1.5 rounded hover:bg-surface transition-colors">
              <div className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 rounded-full bg-rose-500" />
                <span className="font-medium text-content">EXCEPTION (Unresolved)</span>
              </div>
              <div className="flex items-center gap-3 tabular-nums">
                <span className="font-bold text-rose-600 dark:text-rose-300">{exceptionCount}</span>
                <span className="text-content-secondary font-mono w-12 text-right">
                  {totalCount > 0 ? `${((exceptionCount / totalCount) * 100).toFixed(1)}%` : "0%"}
                </span>
              </div>
            </div>

            <div className="flex items-center justify-between p-1.5 rounded hover:bg-surface transition-colors">
              <div className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 rounded-full bg-violet-500" />
                <span className="font-medium text-content">DUPLICATE</span>
              </div>
              <div className="flex items-center gap-3 tabular-nums">
                <span className="font-bold text-violet-600 dark:text-violet-300">{duplicateCount}</span>
                <span className="text-content-secondary font-mono w-12 text-right">
                  {totalCount > 0 ? `${((duplicateCount / totalCount) * 100).toFixed(1)}%` : "0%"}
                </span>
              </div>
            </div>

            <div className="flex items-center justify-between p-1.5 rounded hover:bg-surface transition-colors">
              <div className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 rounded-full bg-slate-400" />
                <span className="font-medium text-content">MISSING LEGS</span>
              </div>
              <div className="flex items-center gap-3 tabular-nums">
                <span className="font-bold text-content-secondary">{missingCount}</span>
                <span className="text-content-secondary font-mono w-12 text-right">
                  {totalCount > 0 ? `${((missingCount / totalCount) * 100).toFixed(1)}%` : "0%"}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* "Requires Attention" & Financial Exposure Section */}
        <div className="rounded-xl border border-border bg-surface-secondary p-5 shadow-xs lg:col-span-2 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between border-b border-border pb-3 mb-4">
              <div>
                <h3 className="text-sm font-semibold text-content flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4 text-amber-500" />
                  Requires Controller Attention
                </h3>
                <p className="text-xs text-content-secondary">Financial exposure categorized by root cause</p>
              </div>
              <Link
                href="/exceptions"
                className="text-xs font-semibold text-primary-light hover:text-primary transition-colors flex items-center gap-1"
              >
                Open Workspace <ArrowRight className="h-3 w-3" />
              </Link>
            </div>

            {/* Financial Exposure Cards Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
              
              {/* Amount Mismatch */}
              <div className="rounded-lg bg-surface p-3.5 border border-border space-y-1 shadow-xs">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] uppercase font-bold text-amber-600 dark:text-amber-400">Amount Mismatch</span>
                  <span className="text-xs font-mono font-semibold text-content tabular-nums">
                    {amountMismatchItem?.count ?? 0} txns
                  </span>
                </div>
                <div className="text-base font-bold text-content tabular-nums">
                  {formatCurrency(amountMismatchItem?.amount ?? 0)}
                </div>
                <span className="text-[10px] text-content-muted block">Settlement variance detected</span>
              </div>

              {/* Missing Bank Settlement */}
              <div className="rounded-lg bg-surface p-3.5 border border-border space-y-1 shadow-xs">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] uppercase font-bold text-rose-600 dark:text-rose-400">Missing Settlement</span>
                  <span className="text-xs font-mono font-semibold text-content tabular-nums">
                    {missingBankItem?.count ?? 0} txns
                  </span>
                </div>
                <div className="text-base font-bold text-content tabular-nums">
                  {formatCurrency(missingBankItem?.amount ?? 0)}
                </div>
                <span className="text-[10px] text-content-muted block">Unsettled gateway capture</span>
              </div>

              {/* High Risk Items */}
              <div className="rounded-lg bg-surface p-3.5 border border-rose-500/30 space-y-1 shadow-xs">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] uppercase font-bold text-rose-600 dark:text-rose-400">High Risk Exposure</span>
                  <span className="text-xs font-mono font-semibold text-content tabular-nums">
                    {highRiskItem?.count ?? 0} txns
                  </span>
                </div>
                <div className="text-base font-bold text-rose-600 dark:text-rose-300 tabular-nums">
                  {highRiskItem?.count ?? 0} Discrepancies
                </div>
                <span className="text-[10px] text-content-muted block">Immediate escalation</span>
              </div>

              {/* Duplicate Captures */}
              <div className="rounded-lg bg-surface p-3.5 border border-border space-y-1 shadow-xs">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] uppercase font-bold text-violet-600 dark:text-violet-400">Duplicate Captures</span>
                  <span className="text-xs font-mono font-semibold text-content tabular-nums">
                    {duplicateItem?.count ?? 0} txns
                  </span>
                </div>
                <div className="text-base font-bold text-content tabular-nums">
                  {formatCurrency(duplicateItem?.amount ?? 0)}
                </div>
                <span className="text-[10px] text-content-muted block">Double billing collisions</span>
              </div>

              {/* Fee & MDR Variance */}
              <div className="rounded-lg bg-surface p-3.5 border border-border space-y-1 shadow-xs">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] uppercase font-bold text-teal-600 dark:text-teal-400">Fee / MDR Delta</span>
                  <span className="text-xs font-mono font-semibold text-content tabular-nums">
                    {feeVarianceItem?.count ?? 0} txns
                  </span>
                </div>
                <div className="text-base font-bold text-content tabular-nums">
                  {formatCurrency(feeVarianceItem?.amount ?? 0)}
                </div>
                <span className="text-[10px] text-content-muted block">Gateway fee overcharges</span>
              </div>

              {/* Medium Risk Items */}
              <div className="rounded-lg bg-surface p-3.5 border border-border space-y-1 shadow-xs">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] uppercase font-bold text-amber-600 dark:text-amber-400">Medium Risk</span>
                  <span className="text-xs font-mono font-semibold text-content tabular-nums">
                    {mediumRiskItem?.count ?? 0} txns
                  </span>
                </div>
                <div className="text-base font-bold text-content tabular-nums">
                  {mediumRiskItem?.count ?? 0} Discrepancies
                </div>
                <span className="text-[10px] text-content-muted block">Standard review queue</span>
              </div>

            </div>
          </div>

          {/* Exceptions by Root Cause Chart */}
          <div className="mt-4 pt-4 border-t border-border">
            <h4 className="text-xs font-semibold text-gray-300 uppercase tracking-wider mb-2">
              Exception Breakdown by Category
            </h4>
            <ExceptionsBarChart data={metrics?.exceptions_by_type || []} />
          </div>
        </div>

      </div>

      {/* Operational Shortcuts Navigation */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        
        <Link
          href="/transactions"
          className="group rounded-xl border border-border bg-surface-secondary p-4 hover:border-border-strong hover:bg-surface-elevated transition-all shadow-sm"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-primary/10 text-primary-light">
                <Layers className="h-5 w-5" />
              </div>
              <div>
                <h4 className="text-sm font-semibold text-white group-hover:text-primary-light transition-colors">
                  Transaction Ledger Explorer
                </h4>
                <p className="text-xs text-gray-400">Inspect 3-way matches, variance breakdown & evidence</p>
              </div>
            </div>
            <ArrowRight className="h-4 w-4 text-gray-500 group-hover:text-primary-light group-hover:translate-x-1 transition-all" />
          </div>
        </Link>

        <Link
          href="/exceptions"
          className="group rounded-xl border border-border bg-surface-secondary p-4 hover:border-border-strong hover:bg-surface-elevated transition-all shadow-sm"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-rose-500/10 text-rose-400">
                <AlertTriangle className="h-5 w-5" />
              </div>
              <div>
                <h4 className="text-sm font-semibold text-white group-hover:text-rose-400 transition-colors">
                  Exception Triage Workspace
                </h4>
                <p className="text-xs text-gray-400">Investigate root causes, approve overrides & resolve</p>
              </div>
            </div>
            <ArrowRight className="h-4 w-4 text-gray-500 group-hover:text-rose-400 group-hover:translate-x-1 transition-all" />
          </div>
        </Link>

        <Link
          href="/chat"
          className="group rounded-xl border border-border bg-surface-secondary p-4 hover:border-border-strong hover:bg-surface-elevated transition-all shadow-sm"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-ai/10 text-ai-light">
                <Sparkles className="h-5 w-5" />
              </div>
              <div>
                <h4 className="text-sm font-semibold text-white group-hover:text-ai-light transition-colors">
                  Finance Operations Copilot
                </h4>
                <p className="text-xs text-gray-400">Query ledgers with tool-grounded financial accuracy</p>
              </div>
            </div>
            <ArrowRight className="h-4 w-4 text-gray-500 group-hover:text-ai-light group-hover:translate-x-1 transition-all" />
          </div>
        </Link>

      </div>

    </div>
  );
}
