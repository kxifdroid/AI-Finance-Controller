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
  const batchSettlementCount = metrics?.batch_settlement_count ?? 
    metrics?.exceptions_by_type?.find(e => e.type.includes("MANY_TO_ONE") || e.type.includes("SETTLEMENT"))?.count ?? 0;
  const duplicateDetectionCount = metrics?.duplicate_detection_count ?? metrics?.duplicate_count ??
    metrics?.exceptions_by_type?.find(e => e.type.includes("DUPLICATE"))?.count ?? 0;

  return (
    <div className="space-y-8">
      
      {/* Top Banner & Pipeline Control Bar */}
      <div className="rounded-2xl border border-border/90 bg-card p-6 shadow-xl relative overflow-hidden">
        <div className="absolute top-0 right-0 h-40 w-40 bg-primary/10 rounded-full blur-3xl -z-10 pointer-events-none" />
        
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div>
            <div className="flex items-center gap-2">
              <span className="bg-primary/20 text-primary-light border border-primary/30 px-2.5 py-0.5 rounded-full text-xs font-semibold">
                Autonomous Finance Operations
              </span>
              <span className="text-xs text-gray-500 font-mono">Run: {metrics?.run_id || "None"}</span>
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-white mt-2">
              Financial Reconciliation Engine
            </h1>
            <p className="mt-1 text-xs text-gray-400 max-w-2xl">
              Deterministic candidate scoring paired with AI-assisted verification across Bank Statements, Gateway Captures, and ERP Invoices. Never forces uncertain matches.
            </p>
          </div>

          {/* Action Buttons */}
          <div className="flex flex-wrap items-center gap-3">
            {/* AI Toggle */}
            <div className="flex items-center gap-2 rounded-xl bg-background/60 border border-border p-2 px-3 text-xs">
              <Sparkles className={cn("h-4 w-4", useAi ? "text-primary-light" : "text-gray-500")} />
              <span className="text-gray-300 font-medium">AI Verification:</span>
              <button
                type="button"
                onClick={() => setUseAi(!useAi)}
                className={cn(
                  "relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out",
                  useAi ? "bg-primary" : "bg-gray-700"
                )}
              >
                <span
                  className={cn(
                    "pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow-lg ring-0 transition duration-200 ease-in-out",
                    useAi ? "translate-x-4" : "translate-x-0"
                  )}
                />
              </button>
            </div>

            {/* Upload Data Button */}
            <Link
              href="/upload"
              className="flex items-center gap-2 rounded-xl border border-border bg-gray-800/80 px-4 py-2.5 text-xs font-semibold text-gray-200 hover:bg-gray-700 hover:text-white transition-all"
            >
              <Upload className="h-4 w-4" />
              Upload Data
            </Link>

            {/* Generate Data Button */}
            <button
              onClick={() => handleGenerateData(250)}
              disabled={isGenerating || isReconciling}
              className="flex items-center gap-2 rounded-xl border border-border bg-gray-800/80 px-4 py-2.5 text-xs font-semibold text-gray-200 hover:bg-gray-700 hover:text-white transition-all disabled:opacity-50"
            >
              <Database className={cn("h-4 w-4", isGenerating && "animate-spin")} />
              Demo Data
            </button>

            {/* Reset / Start Fresh Button */}
            <button
              onClick={() => handleResetAnalysis(true)}
              disabled={isResetting || isReconciling || isGenerating}
              className="flex items-center gap-2 rounded-xl border border-rose-500/30 bg-rose-950/20 px-3.5 py-2.5 text-xs font-semibold text-rose-300 hover:bg-rose-900/40 hover:text-rose-200 transition-all disabled:opacity-50"
              title="Cancel previous analysis and start fresh"
            >
              <RotateCcw className={cn("h-4 w-4", isResetting && "animate-spin")} />
              Reset / Start Fresh
            </button>

            {/* Run Reconciliation Button */}
            <button
              onClick={handleRunReconciliation}
              disabled={isReconciling || isGenerating}
              className="flex items-center gap-2 rounded-xl bg-primary px-5 py-2.5 text-xs font-bold text-white hover:bg-primary-hover transition-all shadow-lg glow-primary disabled:opacity-50"
            >
              <Play className={cn("h-4 w-4 fill-current", isReconciling && "animate-spin")} />
              {isReconciling ? "Running..." : "Run Reconciliation"}
            </button>
          </div>
        </div>

        {/* Status Toast Message */}
        {statusMessage && (
          <div className="mt-4 rounded-lg bg-background/80 border border-border/80 px-3.5 py-2 text-xs text-gray-300 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <RefreshCw className={cn("h-3.5 w-3.5 text-primary-light", (isGenerating || isReconciling) && "animate-spin")} />
              <span>{statusMessage}</span>
            </div>
            <button onClick={() => setStatusMessage(null)} className="text-gray-500 hover:text-white text-xs">
              Dismiss
            </button>
          </div>
        )}
      </div>

      {/* Top Production Metric Cards Strip */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        
        {/* Match Rate Card */}
        <KPICard
          title="Match Rate"
          value={`${metrics?.match_rate_pct || 0}%`}
          subtitle={metrics?.value_match_rate_pct ? `Value Match: ${metrics.value_match_rate_pct}%` : `${metrics?.matched_count || 0} matched sets`}
          icon={<CheckCircle2 className="h-4 w-4 text-emerald-400" />}
          variant="success"
        />

        {/* Settlement Variance Exposure Card */}
        <KPICard
          title="Variance Exposure"
          value={formatCurrency(settlementVarianceExposure)}
          subtitle={`${metrics?.exception_count || 0} unresolved discrepancies`}
          icon={<Scale className="h-4 w-4 text-rose-400" />}
          variant="danger"
        />

        {/* Batch Settlement Count (many-to-one) Card */}
        <KPICard
          title="Batch Settlements"
          value={batchSettlementCount}
          subtitle="Many-to-one batch bundles"
          icon={<Layers className="h-4 w-4 text-indigo-400" />}
          variant="primary"
        />

        {/* Duplicate Detection Count Card */}
        <KPICard
          title="Duplicate Detections"
          value={duplicateDetectionCount}
          subtitle="Idempotency collisions flagged"
          icon={<CopyCheck className="h-4 w-4 text-amber-400" />}
          variant="warning"
        />

        {/* Throughput Card */}
        <KPICard
          title="Throughput"
          value={`${metrics?.throughput_rps || 0} rps`}
          subtitle={`in ${metrics?.processing_time_ms || 0} ms`}
          icon={<TrendingUp className="h-4 w-4 text-primary-light" />}
          variant="default"
        />

        {/* AI Verifications Card */}
        <KPICard
          title="AI Verifications"
          value={metrics?.ai_verified_count || 0}
          subtitle={metrics?.ai_failed_count ? `${metrics.ai_failed_count} fallback to human` : "Structured reasoning"}
          icon={<Sparkles className="h-4 w-4 text-indigo-400" />}
          variant="default"
        />

      </div>

      {/* Ground Truth Benchmark Report Card */}
      {metrics?.evaluation && metrics.evaluation.has_evaluation && (
        <div className="rounded-2xl border border-indigo-500/30 bg-gradient-to-r from-indigo-950/40 via-card to-background p-6 shadow-xl">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-indigo-500/20 pb-4">
            <div>
              <div className="flex items-center gap-2">
                <Target className="h-5 w-5 text-indigo-400" />
                <h2 className="text-base font-bold text-white tracking-tight">
                  Ground Truth Benchmark Performance (Hidden Inference Evaluation)
                </h2>
              </div>
              <p className="mt-1 text-xs text-gray-400">
                Ground truth was isolated during inference and strictly queried post-reconciliation to compute true empirical metrics.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs bg-indigo-500/20 text-indigo-300 px-3 py-1 rounded-full border border-indigo-500/40 font-mono">
                Zero Ground-Truth Leakage
              </span>
            </div>
          </div>

          <div className="mt-4 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            <div className="rounded-xl bg-background/50 border border-indigo-500/20 p-3 text-center">
              <div className="text-[11px] text-gray-400 uppercase font-medium">Precision</div>
              <div className="text-xl font-black text-emerald-400 mt-1">
                {formatPercent(metrics.evaluation.precision)}
              </div>
              <div className="text-[10px] text-gray-500 mt-0.5">TP / (TP + FP)</div>
            </div>

            <div className="rounded-xl bg-background/50 border border-indigo-500/20 p-3 text-center">
              <div className="text-[11px] text-gray-400 uppercase font-medium">Recall</div>
              <div className="text-xl font-black text-indigo-400 mt-1">
                {formatPercent(metrics.evaluation.recall)}
              </div>
              <div className="text-[10px] text-gray-500 mt-0.5">TP / (TP + FN)</div>
            </div>

            <div className="rounded-xl bg-background/50 border border-indigo-500/20 p-3 text-center">
              <div className="text-[11px] text-gray-400 uppercase font-medium">F1 Score</div>
              <div className="text-xl font-black text-primary-light mt-1">
                {formatPercent(metrics.evaluation.f1_score)}
              </div>
              <div className="text-[10px] text-gray-500 mt-0.5">Harmonic Mean</div>
            </div>

            <div className="rounded-xl bg-background/50 border border-indigo-500/20 p-3 text-center">
              <div className="text-[11px] text-gray-400 uppercase font-medium">Accuracy</div>
              <div className="text-xl font-black text-white mt-1">
                {formatPercent(metrics.evaluation.accuracy)}
              </div>
              <div className="text-[10px] text-gray-500 mt-0.5">(TP + TN) / Total</div>
            </div>

            <div className="rounded-xl bg-background/50 border border-indigo-500/20 p-3 text-center">
              <div className="text-[11px] text-gray-400 uppercase font-medium">False Positive Rate</div>
              <div className="text-xl font-black text-emerald-400 mt-1">
                {formatPercent(metrics.evaluation.false_positive_rate)}
              </div>
              <div className="text-[10px] text-gray-500 mt-0.5">FP / (FP + TN)</div>
            </div>

            <div className="rounded-xl bg-background/50 border border-indigo-500/20 p-3 text-center">
              <div className="text-[11px] text-gray-400 uppercase font-medium">Exception Detection</div>
              <div className="text-xl font-black text-amber-400 mt-1">
                {formatPercent(metrics.evaluation.exception_detection_accuracy)}
              </div>
              <div className="text-[10px] text-gray-500 mt-0.5">Caught Anomaly Rate</div>
            </div>
          </div>
        </div>
      )}

      {/* Visual Analytics Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Status Donut Chart */}
        <div className="rounded-2xl border border-border bg-card p-5 shadow-sm">
          <div className="flex items-center justify-between mb-4 border-b border-border pb-3">
            <div>
              <h3 className="text-sm font-bold text-white">Reconciliation Decisions</h3>
              <p className="text-xs text-gray-400">Match vs Review vs Exceptions</p>
            </div>
            <span className="text-xs font-mono text-gray-400">{metrics?.total_records || 0} Total</span>
          </div>
          <StatusDonutChart data={metrics?.status_distribution || []} />
        </div>

        {/* Exceptions by Type Bar Chart */}
        <div className="rounded-2xl border border-border bg-card p-5 shadow-sm">
          <div className="flex items-center justify-between mb-4 border-b border-border pb-3">
            <div>
              <h3 className="text-sm font-bold text-white">Exceptions by Classification</h3>
              <p className="text-xs text-gray-400">Root causes identified</p>
            </div>
            <Link href="/exceptions" className="text-xs text-primary-light hover:underline flex items-center gap-1">
              Triage <ArrowRight className="h-3 w-3" />
            </Link>
          </div>
          <ExceptionsBarChart data={metrics?.exceptions_by_type || []} />
        </div>

        {/* Severity Distribution */}
        <div className="rounded-2xl border border-border bg-card p-5 shadow-sm">
          <div className="flex items-center justify-between mb-4 border-b border-border pb-3">
            <div>
              <h3 className="text-sm font-bold text-white">Exception Severity Breakdown</h3>
              <p className="text-xs text-gray-400">High vs Medium vs Low Risk</p>
            </div>
            <span className="text-xs font-mono text-rose-400 font-semibold">
              {metrics?.exception_count || 0} Discrepancies
            </span>
          </div>
          <SeverityChart data={metrics?.severity_distribution || []} />
        </div>

      </div>

      {/* Quick Navigation Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        
        <Link
          href="/transactions"
          className="group rounded-xl border border-border bg-card p-4 hover:border-primary/50 transition-all shadow-sm"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-primary/10 text-primary-light">
                <Layers className="h-5 w-5" />
              </div>
              <div>
                <h4 className="text-sm font-bold text-white group-hover:text-primary-light transition-colors">
                  Transaction Explorer
                </h4>
                <p className="text-xs text-gray-400">Inspect 3-way matches & score breakdown</p>
              </div>
            </div>
            <ArrowRight className="h-4 w-4 text-gray-500 group-hover:text-primary-light group-hover:translate-x-1 transition-all" />
          </div>
        </Link>

        <Link
          href="/exceptions"
          className="group rounded-xl border border-border bg-card p-4 hover:border-rose-500/50 transition-all shadow-sm"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-rose-500/10 text-rose-400">
                <AlertTriangle className="h-5 w-5" />
              </div>
              <div>
                <h4 className="text-sm font-bold text-white group-hover:text-rose-400 transition-colors">
                  Exception Triage Workspace
                </h4>
                <p className="text-xs text-gray-400">Investigate & resolve discrepancies</p>
              </div>
            </div>
            <ArrowRight className="h-4 w-4 text-gray-500 group-hover:text-rose-400 group-hover:translate-x-1 transition-all" />
          </div>
        </Link>

        <Link
          href="/chat"
          className="group rounded-xl border border-border bg-card p-4 hover:border-indigo-500/50 transition-all shadow-sm"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-indigo-500/10 text-indigo-400">
                <Sparkles className="h-5 w-5" />
              </div>
              <div>
                <h4 className="text-sm font-bold text-white group-hover:text-indigo-400 transition-colors">
                  Finance Q&A Assistant
                </h4>
                <p className="text-xs text-gray-400">Query ledgers with tool-grounded AI</p>
              </div>
            </div>
            <ArrowRight className="h-4 w-4 text-gray-500 group-hover:text-indigo-400 group-hover:translate-x-1 transition-all" />
          </div>
        </Link>

      </div>

    </div>
  );
}
