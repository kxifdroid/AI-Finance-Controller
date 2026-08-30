"use client";

import { useEffect, useState } from "react";
import { 
  Search, 
  Filter, 
  Layers, 
  Eye, 
  Sparkles, 
  ShieldCheck, 
  AlertTriangle, 
  CheckCircle2, 
  Clock, 
  Copy,
  ChevronLeft,
  ChevronRight,
  RotateCcw
} from "lucide-react";
import { MatchRecord } from "@/types";
import { fetchTransactions, resetReconciliation } from "@/lib/api";
import { MatchDetailModal } from "@/components/match-detail-modal";
import { formatCurrency, formatDate, formatPercent, cleanId, cn } from "@/lib/utils";

export default function TransactionsPage() {
  const [transactions, setTransactions] = useState<MatchRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(25);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [riskFilter, setRiskFilter] = useState<string>("");
  const [search, setSearch] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(true);
  const [isResetting, setIsResetting] = useState<boolean>(false);
  const [selectedMatchId, setSelectedMatchId] = useState<string | null>(null);

  const handleResetLedger = async () => {
    if (!window.confirm("Reset and clear all transaction ledger records to start 100% fresh?")) return;
    setIsResetting(true);
    try {
      await resetReconciliation(undefined, true);
      if (typeof window !== "undefined") {
        localStorage.removeItem("latest_dataset_id");
      }
      await loadTransactions();
    } catch (err: any) {
      alert(`Failed to reset: ${err.message}`);
    } finally {
      setIsResetting(false);
    }
  };

  const loadTransactions = async () => {
    setLoading(true);
    try {
      const res = await fetchTransactions({
        status: statusFilter || undefined,
        risk: riskFilter || undefined,
        search: search || undefined,
        page,
        pageSize,
      });
      setTransactions(res.items);
      setTotal(res.total);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTransactions();
  }, [page, statusFilter, riskFilter]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    loadTransactions();
  };

  const getStatusBadge = (decision: string, matchType?: string) => {
    if (matchType === "FEE_RECONCILED") {
      return <span className="bg-teal-500/10 text-teal-400 border border-teal-500/30 px-2 py-0.5 rounded-full text-[11px] font-semibold">FEE MATCH</span>;
    }
    if (matchType === "MANY_TO_ONE") {
      return <span className="bg-purple-500/10 text-purple-400 border border-purple-500/30 px-2 py-0.5 rounded-full text-[11px] font-semibold">BATCH MATCH</span>;
    }
    if (matchType === "TIMING_DIFFERENCE") {
      return <span className="bg-blue-500/10 text-blue-400 border border-blue-500/30 px-2 py-0.5 rounded-full text-[11px] font-semibold">CLEARED (T+2)</span>;
    }
    switch (decision) {
      case "MATCH":
        return <span className="bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 px-2 py-0.5 rounded-full text-[11px] font-semibold">MATCH</span>;
      case "REVIEW":
        return <span className="bg-amber-500/10 text-amber-400 border border-amber-500/30 px-2 py-0.5 rounded-full text-[11px] font-semibold">REVIEW</span>;
      case "EXCEPTION":
        return <span className="bg-rose-500/10 text-rose-400 border border-rose-500/30 px-2 py-0.5 rounded-full text-[11px] font-semibold">EXCEPTION</span>;
      case "DUPLICATE":
        return <span className="bg-purple-500/10 text-purple-400 border border-purple-500/30 px-2 py-0.5 rounded-full text-[11px] font-semibold">DUPLICATE</span>;
      case "MISSING":
        return <span className="bg-gray-500/10 text-gray-400 border border-gray-500/30 px-2 py-0.5 rounded-full text-[11px] font-semibold">MISSING</span>;
      default:
        return <span className="bg-gray-500/10 text-gray-400 border border-gray-500/30 px-2 py-0.5 rounded-full text-[11px] font-semibold">{decision}</span>;
    }
  };

  const getRiskBadge = (risk: string) => {
    switch (risk) {
      case "HIGH":
        return <span className="text-rose-400 text-xs font-semibold">HIGH</span>;
      case "MEDIUM":
        return <span className="text-amber-400 text-xs font-semibold">MEDIUM</span>;
      default:
        return <span className="text-emerald-400 text-xs font-semibold">LOW</span>;
    }
  };

  const totalPages = Math.ceil(total / pageSize) || 1;

  return (
    <div className="space-y-6">
      
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
            <Layers className="h-6 w-6 text-primary-light" />
            Transaction Ledger Explorer
          </h1>
          <p className="mt-1 text-xs text-gray-400">
            Search and inspect reconciled 3-way transactions across Bank, Gateway, and ERP Invoices.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-xs text-gray-400 font-mono">
            Showing {transactions.length} of {total} records
          </div>
          <button
            onClick={handleResetLedger}
            disabled={isResetting || total === 0}
            className="flex items-center gap-1.5 rounded-lg border border-rose-500/30 bg-rose-950/20 px-3 py-1.5 text-xs font-semibold text-rose-300 hover:bg-rose-900/40 hover:text-rose-200 transition-all disabled:opacity-40"
            title="Reset and clear all transactions"
          >
            <RotateCcw className={cn("h-3.5 w-3.5", isResetting && "animate-spin")} />
            Reset Ledger
          </button>
        </div>
      </div>

      {/* Filter & Search Bar */}
      <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3 bg-card p-3 rounded-xl border border-border">
        
        {/* Search */}
        <form onSubmit={handleSearchSubmit} className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-500" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by Match ID, reference code, customer, or description..."
            className="w-full rounded-lg border border-border bg-background/70 pl-9 pr-4 py-1.5 text-xs text-white placeholder-gray-500 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </form>

        {/* Status Filter Pills */}
        <div className="flex flex-wrap items-center gap-1.5">
          {["", "MATCH", "REVIEW", "EXCEPTION", "DUPLICATE", "MISSING"].map((st) => (
            <button
              key={st || "ALL"}
              onClick={() => {
                setStatusFilter(st);
                setPage(1);
              }}
              className={cn(
                "px-2.5 py-1 rounded-lg text-xs font-medium transition-all",
                statusFilter === st
                  ? "bg-primary text-white font-semibold shadow-sm"
                  : "bg-background/40 text-gray-400 hover:text-white border border-border hover:bg-gray-800"
              )}
            >
              {st || "ALL STATUS"}
            </button>
          ))}
        </div>

        {/* Risk Filter */}
        <div className="flex items-center gap-1.5">
          {["", "HIGH", "MEDIUM", "LOW"].map((rk) => (
            <button
              key={rk || "ALL_RISK"}
              onClick={() => {
                setRiskFilter(rk);
                setPage(1);
              }}
              className={cn(
                "px-2.5 py-1 rounded-lg text-xs font-medium transition-all",
                riskFilter === rk
                  ? "bg-gray-700 text-white font-semibold"
                  : "bg-background/40 text-gray-500 hover:text-white border border-border"
              )}
            >
              {rk ? `${rk} Risk` : "All Risk"}
            </button>
          ))}
        </div>

      </div>

      {/* Table */}
      <div className="rounded-xl border border-border bg-card overflow-hidden shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-background/60 text-gray-400 uppercase tracking-wider border-b border-border text-[10px]">
              <tr>
                <th className="px-4 py-3">Match ID</th>
                <th className="px-4 py-3">Date</th>
                <th className="px-4 py-3">Counterparty / Reference</th>
                <th className="px-4 py-3">Amount</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Confidence</th>
                <th className="px-4 py-3">Risk</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/60">
              {loading ? (
                <tr>
                  <td colSpan={8} className="px-4 py-12 text-center text-gray-500">
                    <div className="flex items-center justify-center gap-2">
                      <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
                      Loading records...
                    </div>
                  </td>
                </tr>
              ) : transactions.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-4 py-12 text-center text-gray-500">
                    No transactions matching your filter criteria.
                  </td>
                </tr>
              ) : (
                transactions.map((tx) => {
                  const counterpart = tx.invoice?.customer_name || tx.gateway_transaction?.customer_name || tx.bank_transaction?.description || "Unknown";
                  const refCode = cleanId(tx.bank_txn_id || tx.gateway_txn_id || tx.invoice_id || tx.match_id);
                  const amt = tx.bank_transaction?.amount || tx.gateway_transaction?.amount || tx.invoice?.amount || 0;
                  const dateStr = tx.bank_transaction?.transaction_date || tx.gateway_transaction?.transaction_date || tx.invoice?.invoice_date || tx.created_at;

                  return (
                    <tr
                      key={tx.match_id}
                      onClick={() => setSelectedMatchId(tx.match_id)}
                      className="hover:bg-gray-800/50 cursor-pointer transition-colors"
                    >
                      <td className="px-4 py-3 font-mono font-medium text-primary-light">
                        {tx.match_id}
                      </td>
                      <td className="px-4 py-3 text-gray-400 whitespace-nowrap">
                        {formatDate(dateStr)}
                      </td>
                      <td className="px-4 py-3 max-w-md">
                        <div className="font-medium text-white truncate">{counterpart}</div>
                        <div className="text-[10px] text-gray-500 font-mono truncate">{refCode}</div>
                        {tx.explanation && (
                          <div className="text-[11px] text-gray-400/90 truncate mt-0.5" title={tx.explanation}>
                            {tx.explanation}
                          </div>
                        )}
                      </td>
                      <td className="px-4 py-3 font-bold text-white whitespace-nowrap">
                        {formatCurrency(amt)}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        {getStatusBadge(tx.decision, tx.match_type)}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-gray-300 font-medium">{formatPercent(tx.confidence_score)}</span>
                          <div className="w-12 bg-gray-800 h-1.5 rounded-full overflow-hidden">
                            <div
                              className="bg-primary h-full rounded-full"
                              style={{ width: `${Math.min(100, tx.confidence_score * 100)}%` }}
                            />
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        {getRiskBadge(tx.risk_level)}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedMatchId(tx.match_id);
                          }}
                          className="rounded-lg bg-gray-800 px-2.5 py-1 text-[11px] font-medium text-gray-300 hover:bg-primary hover:text-white transition-colors"
                        >
                          3-Way View
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Controls */}
        <div className="flex items-center justify-between border-t border-border px-4 py-3 text-xs text-gray-400">
          <div>
            Page <span className="font-medium text-white">{page}</span> of <span className="font-medium text-white">{totalPages}</span>
          </div>
          <div className="flex items-center gap-2">
            <button
              disabled={page <= 1}
              onClick={() => setPage(page - 1)}
              className="flex items-center gap-1 rounded-lg border border-border bg-background/50 px-2.5 py-1 text-xs text-gray-300 hover:bg-gray-800 disabled:opacity-40"
            >
              <ChevronLeft className="h-4 w-4" /> Previous
            </button>
            <button
              disabled={page >= totalPages}
              onClick={() => setPage(page + 1)}
              className="flex items-center gap-1 rounded-lg border border-border bg-background/50 px-2.5 py-1 text-xs text-gray-300 hover:bg-gray-800 disabled:opacity-40"
            >
              Next <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>

      </div>

      {/* 3-Way Match Modal */}
      {selectedMatchId && (
        <MatchDetailModal
          matchId={selectedMatchId}
          onClose={() => setSelectedMatchId(null)}
        />
      )}

    </div>
  );
}
