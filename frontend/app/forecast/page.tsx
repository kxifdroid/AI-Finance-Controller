"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { 
  TrendingUp, 
  DollarSign, 
  Calendar, 
  AlertCircle, 
  ShieldCheck, 
  Info, 
  ArrowUpRight,
  ArrowDownRight,
  RotateCcw
} from "lucide-react";
import { CashForecastData } from "@/types";
import { fetchCashForecast, fetchMetrics, resetReconciliation } from "@/lib/api";
import { CashForecastChart } from "@/components/charts/cash-forecast-chart";
import { formatCurrency, formatDate, cn } from "@/lib/utils";

export default function ForecastPage() {
  const [forecast, setForecast] = useState<CashForecastData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [isResetting, setIsResetting] = useState<boolean>(false);

  const loadForecast = async () => {
    setLoading(true);
    try {
      const datasetId = typeof window !== "undefined" ? localStorage.getItem("latest_dataset_id") || undefined : undefined;
      // Gate the forecast on whether a reconciliation run actually exists.
      // Without this, the backend returns a fabricated baseline projection even
      // when no data has been reconciled, making the page "show something on its own".
      const metrics = await fetchMetrics(datasetId);
      if (!metrics.has_run) {
        setForecast(null);
        return;
      }
      const data = await fetchCashForecast(datasetId);
      setForecast(data);
    } catch (err) {
      console.error(err);
      setForecast(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadForecast();
  }, []);

  const handleReset = async () => {
    if (!window.confirm("Reset and clear all reconciliation data? This will clear the cash forecast until you upload and reconcile new data.")) return;
    setIsResetting(true);
    try {
      await resetReconciliation(undefined, true);
      if (typeof window !== "undefined") {
        localStorage.removeItem("latest_dataset_id");
      }
      await loadForecast();
    } catch (err: any) {
      alert(`Failed to reset: ${err.message}`);
    } finally {
      setIsResetting(false);
    }
  };

  return (
    <div className="space-y-6">
      
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
            <TrendingUp className="h-6 w-6 text-primary-light" />
            7-Day Rolling Cash Flow Forecast
          </h1>
          <p className="mt-1 text-xs text-gray-400">
            Rule-based projection combining reconciled cleared cash, pending gateway settlements (T+2 lag), and open invoice receivables.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs bg-primary/20 text-primary-light px-3 py-1 rounded-full border border-primary/30 font-medium">
            Rule-Based Deterministic Model
          </span>
          <button
            onClick={handleReset}
            disabled={loading || isResetting}
            aria-label="Reset forecast and clear all reconciliation data"
            className="flex items-center gap-1.5 rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-1.5 text-xs font-semibold text-rose-300 transition-colors hover:bg-rose-500/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-500/50 disabled:opacity-50"
          >
            <RotateCcw className={cn("h-3.5 w-3.5", isResetting && "animate-spin")} />
            {isResetting ? "Resetting..." : "Reset"}
          </button>
        </div>
      </div>

      {/* Empty state — no reconciliation run exists (e.g. after a reset) */}
      {!loading && !forecast ? (
        <div className="rounded-2xl border border-border bg-card p-12 flex flex-col items-center justify-center text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-gray-800/60 border border-border mb-4">
            <TrendingUp className="h-6 w-6 text-gray-500" />
          </div>
          <h3 className="text-base font-semibold text-white">No forecast available</h3>
          <p className="mt-1.5 max-w-sm text-xs text-gray-400">
            Run a reconciliation to generate the cash forecast. The projection is derived
            from reconciled cleared cash, pending gateway settlements, and open receivables.
          </p>
          <Link
            href="/"
            className="mt-5 inline-flex items-center gap-1.5 rounded-lg border border-primary/40 bg-primary/10 px-4 py-2 text-xs font-semibold text-primary-light transition-colors hover:bg-primary/20"
          >
            Go to Dashboard
          </Link>
        </div>
      ) : (
      <>
      {/* Methodology & Limitations Disclosure Banner */}
      <div className="rounded-xl border border-indigo-500/30 bg-indigo-950/20 p-4 flex items-start gap-3">
        <Info className="h-5 w-5 text-indigo-400 shrink-0 mt-0.5" />
        <div className="space-y-1 text-xs text-gray-300">
          <div className="font-bold text-white">Forecast Methodology & Modeling Assumptions:</div>
          <p className="leading-relaxed text-gray-400">
            {forecast?.methodology || "Cleared Cash + Settling Payments (T+2) + Open Receivables - Estimated Disbursements"}
          </p>
          <div className="text-[11px] text-indigo-300/80 font-mono">
            <strong>Limitation:</strong> {forecast?.limitations || "Deterministic projection based on existing invoice due dates and gateway settlement schedules. Not a stochastic or market-risk predictive model."}
          </div>
        </div>
      </div>

      {/* Chart Section */}
      <div className="rounded-2xl border border-border bg-card p-6 shadow-sm">
        <div className="flex items-center justify-between mb-4 border-b border-border pb-3">
          <div>
            <h3 className="text-sm font-bold text-white">Projected Cash Trajectory (Next 7 Days)</h3>
            <p className="text-xs text-gray-400">Expected liquid balance progression</p>
          </div>
          <div className="text-right">
            <span className="text-[10px] text-gray-500 uppercase block">Current Cleared Cash</span>
            <span className="text-lg font-bold text-emerald-400">
              {formatCurrency(forecast?.current_cleared_cash || 0)}
            </span>
          </div>
        </div>
        {loading ? (
          <div className="flex h-72 items-center justify-center text-xs text-gray-500">
            Calculating liquidity projections...
          </div>
        ) : (
          <CashForecastChart points={forecast?.forecast_points || []} />
        )}
      </div>

      {/* Forecast Points Table */}
      <div className="rounded-xl border border-border bg-card overflow-hidden shadow-sm">
        <div className="px-4 py-3 border-b border-border bg-background/40">
          <h3 className="text-xs font-bold text-white uppercase tracking-wider">
            Daily Forecast Breakdown & Financial Drivers
          </h3>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-background/60 text-gray-400 uppercase tracking-wider border-b border-border text-[10px]">
              <tr>
                <th className="px-4 py-3">Timeline</th>
                <th className="px-4 py-3">Date</th>
                <th className="px-4 py-3">Cleared Cash</th>
                <th className="px-4 py-3">Gateway Inflows</th>
                <th className="px-4 py-3">Receivables</th>
                <th className="px-4 py-3">OPEX Buffer</th>
                <th className="px-4 py-3">Projected Balance</th>
                <th className="px-4 py-3">Confidence</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/60">
              {forecast?.forecast_points?.map((point) => {
                const isToday = point.day_offset === 0;
                return (
                  <tr key={point.day_offset} className={cn("hover:bg-gray-800/40", isToday && "bg-primary/5")}>
                    <td className="px-4 py-3 font-semibold text-white">
                      {isToday ? "Day 0 (Today)" : `Day +${point.day_offset}`}
                    </td>
                    <td className="px-4 py-3 text-gray-400 font-mono">
                      {formatDate(point.forecast_date)}
                    </td>
                    <td className="px-4 py-3 font-medium text-gray-200">
                      {formatCurrency(point.cleared_cash)}
                    </td>
                    <td className="px-4 py-3 font-medium text-emerald-400">
                      +{formatCurrency(point.expected_settlements)}
                    </td>
                    <td className="px-4 py-3 font-medium text-indigo-400">
                      +{formatCurrency(point.expected_receivables)}
                    </td>
                    <td className="px-4 py-3 font-medium text-rose-400">
                      -{formatCurrency(point.recurring_expenses)}
                    </td>
                    <td className="px-4 py-3 font-bold text-white text-sm">
                      {formatCurrency(point.projected_balance)}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={cn(
                          "px-2 py-0.5 rounded-full text-[10px] font-bold border",
                          point.confidence_level === "HIGH"
                            ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                            : "bg-amber-500/10 text-amber-400 border-amber-500/30"
                        )}
                      >
                        {point.confidence_level}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
      </>
      )}

    </div>
  );
}
