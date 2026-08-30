"use client";

import { useEffect, useState } from "react";
import { 
  Search, 
  Filter, 
  Layers, 
  Eye, 
  RotateCcw,
  ChevronLeft,
  ChevronRight,
  SlidersHorizontal,
  XCircle,
  RefreshCw
} from "lucide-react";
import { MatchRecord } from "@/types";
import { fetchTransactions, resetReconciliation } from "@/lib/api";
import { MatchDetailModal } from "@/components/match-detail-modal";
import { 
  StatusBadge, 
  RiskBadge, 
  MatchTypeTag, 
  FilterChip, 
  EmptyState, 
  SkeletonRows 
} from "@/components/ui-kit";
import { formatCurrency, formatDate, formatPercent, cleanId, cn } from "@/lib/utils";

export default function TransactionsPage() {
  const [transactions, setTransactions] = useState<MatchRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(25);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [riskFilter, setRiskFilter] = useState<string>("");
  const [matchTypeFilter, setMatchTypeFilter] = useState<string>("");
  const [search, setSearch] = useState<string>("");
  const [filterPanelOpen, setFilterPanelOpen] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(true);
  const [isResetting, setIsResetting] = useState<boolean>(false);
  const [selectedMatchId, setSelectedMatchId] = useState<string | null>(null);

  // Summary statistics computed across currently visible/loaded transactions
  const matchedSummary = transactions.filter(t => t.decision === "MATCH").length;
  const reviewSummary = transactions.filter(t => t.decision === "REVIEW").length;
  const exceptionSummary = transactions.filter(t => t.decision === "EXCEPTION").length;

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
      console.error("Failed to load transactions:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTransactions();
  }, [page, statusFilter, riskFilter, matchTypeFilter]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    loadTransactions();
  };

  const clearAllFilters = () => {
    setStatusFilter("");
    setRiskFilter("");
    setMatchTypeFilter("");
    setSearch("");
    setPage(1);
  };

  const hasActiveFilters = Boolean(statusFilter || riskFilter || matchTypeFilter || search);
  const totalPages = Math.ceil(total / pageSize) || 1;

  return (
    <div className="space-y-6">
      
      {/* Header & Contextual Summary */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-5">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-2xl sm:text-[26px] font-bold tracking-tight text-content">
              Transaction Ledger
            </h1>
            <span className="text-xs font-mono text-content-secondary bg-surface-secondary px-2.5 py-0.5 rounded-full border border-border">
              {total} Reconciliations
            </span>
          </div>
          <p className="mt-1 text-xs text-content-secondary">
            Review every 3-way reconciliation unit across Bank, Gateway, and ERP sources with deterministic audit trails.
          </p>
        </div>

        {/* Counter Summary Pills */}
        <div className="flex items-center gap-2 flex-wrap">
          <div className="flex items-center gap-1.5 rounded-lg bg-surface-secondary border border-border px-2.5 py-1 text-xs shadow-xs">
            <span className="h-2 w-2 rounded-full bg-emerald-500" />
            <span className="text-content-secondary">Matched:</span>
            <span className="font-bold text-content tabular-nums">{matchedSummary}</span>
          </div>
          <div className="flex items-center gap-1.5 rounded-lg bg-surface-secondary border border-border px-2.5 py-1 text-xs shadow-xs">
            <span className="h-2 w-2 rounded-full bg-amber-500" />
            <span className="text-content-secondary">Review:</span>
            <span className="font-bold text-amber-600 dark:text-amber-300 tabular-nums">{reviewSummary}</span>
          </div>
          <div className="flex items-center gap-1.5 rounded-lg bg-surface-secondary border border-border px-2.5 py-1 text-xs shadow-xs">
            <span className="h-2 w-2 rounded-full bg-rose-500" />
            <span className="text-content-secondary">Exceptions:</span>
            <span className="font-bold text-rose-600 dark:text-rose-300 tabular-nums">{exceptionSummary}</span>
          </div>
          <button
            onClick={handleResetLedger}
            disabled={isResetting || total === 0}
            className="flex items-center gap-1.5 rounded-lg border border-border bg-surface-secondary px-2.5 py-1 text-xs font-medium text-content-secondary hover:text-rose-600 dark:hover:text-rose-300 hover:border-rose-500/40 hover:bg-rose-500/10 transition-all disabled:opacity-40 focus-ring shadow-xs"
            title="Reset and clear ledger"
          >
            <RotateCcw className={cn("h-3.5 w-3.5", isResetting && "animate-spin")} />
            Reset
          </button>
        </div>
      </div>

      {/* Unified Search & Filter Toolbar */}
      <div className="rounded-xl border border-border bg-surface-secondary p-3 space-y-3 shadow-xs">
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-2.5">
          
          {/* Search Input */}
          <form onSubmit={handleSearchSubmit} className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-content-muted" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search reference (e.g. ORD-5001), customer, match ID, or description..."
              className="w-full rounded-lg border border-border bg-surface pl-9 pr-4 py-1.5 text-xs text-content placeholder-content-muted focus-ring"
            />
          </form>

          {/* Filter Popover Toggle */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => setFilterPanelOpen(!filterPanelOpen)}
              className={cn(
                "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors focus-ring shadow-xs",
                filterPanelOpen || hasActiveFilters
                  ? "bg-surface-elevated text-content border-border-strong font-semibold"
                  : "bg-surface text-content-secondary border-border hover:text-content"
              )}
            >
              <SlidersHorizontal className="h-3.5 w-3.5" />
              <span>Filters</span>
              {hasActiveFilters && (
                <span className="h-1.5 w-1.5 rounded-full bg-primary-light ml-0.5" />
              )}
            </button>

            {hasActiveFilters && (
              <button
                onClick={clearAllFilters}
                className="text-xs text-content-muted hover:text-content px-2 py-1 transition-colors"
              >
                Clear all
              </button>
            )}
          </div>
        </div>

        {/* Expandable Filter Controls */}
        {filterPanelOpen && (
          <div className="pt-3 border-t border-border grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs animate-fade-in">
            <div>
              <label className="text-[11px] font-semibold uppercase text-content-secondary block mb-1">Status</label>
              <select
                value={statusFilter}
                onChange={(e) => {
                  setStatusFilter(e.target.value);
                  setPage(1);
                }}
                className="w-full rounded-lg border border-border bg-surface px-2.5 py-1.5 text-xs text-content focus-ring"
              >
                <option value="">All Statuses</option>
                <option value="MATCH">MATCH</option>
                <option value="REVIEW">REVIEW</option>
                <option value="EXCEPTION">EXCEPTION</option>
                <option value="DUPLICATE">DUPLICATE</option>
                <option value="MISSING">MISSING</option>
              </select>
            </div>

            <div>
              <label className="text-[11px] font-semibold uppercase text-content-secondary block mb-1">Risk Level</label>
              <select
                value={riskFilter}
                onChange={(e) => {
                  setRiskFilter(e.target.value);
                  setPage(1);
                }}
                className="w-full rounded-lg border border-border bg-surface px-2.5 py-1.5 text-xs text-content focus-ring"
              >
                <option value="">All Risk Levels</option>
                <option value="LOW">LOW</option>
                <option value="MEDIUM">MEDIUM</option>
                <option value="HIGH">HIGH</option>
              </select>
            </div>

            <div>
              <label className="text-[11px] font-semibold uppercase text-content-secondary block mb-1">Topology</label>
              <select
                value={matchTypeFilter}
                onChange={(e) => {
                  setMatchTypeFilter(e.target.value);
                  setPage(1);
                }}
                className="w-full rounded-lg border border-border bg-surface px-2.5 py-1.5 text-xs text-content focus-ring"
              >
                <option value="">All Topologies</option>
                <option value="EXACT">Exact 3-Way</option>
                <option value="MANY_TO_ONE">Many-to-One Batch</option>
                <option value="FEE_RECONCILED">Fee Reconciled</option>
                <option value="TIMING_DIFFERENCE">Timing Difference</option>
                <option value="AMOUNT_MISMATCH">Amount Mismatch</option>
              </select>
            </div>
          </div>
        )}

        {/* Active Filter Chips */}
        {hasActiveFilters && (
          <div className="flex flex-wrap items-center gap-1.5 pt-1">
            {search && (
              <FilterChip label="Search" value={`"${search}"`} onRemove={() => setSearch("")} />
            )}
            {statusFilter && (
              <FilterChip label="Status" value={statusFilter} onRemove={() => setStatusFilter("")} />
            )}
            {riskFilter && (
              <FilterChip label="Risk" value={riskFilter} onRemove={() => setRiskFilter("")} />
            )}
            {matchTypeFilter && (
              <FilterChip label="Topology" value={matchTypeFilter} onRemove={() => setMatchTypeFilter("")} />
            )}
          </div>
        )}
      </div>

      {/* Transaction Table */}
      <div className="rounded-xl border border-border bg-surface-secondary overflow-hidden shadow-xs">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-surface text-content-secondary uppercase tracking-wider border-b border-border text-[10px]">
              <tr>
                <th className="px-4 py-3">Transaction / Ref</th>
                <th className="px-4 py-3">Counterparty</th>
                <th className="px-4 py-3">Date</th>
                <th className="px-4 py-3">Amount</th>
                <th className="px-4 py-3">Match Type</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Confidence</th>
                <th className="px-4 py-3">Risk</th>
                <th className="px-4 py-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/60">
              {loading ? (
                <tr>
                  <td colSpan={9} className="p-4">
                    <SkeletonRows rows={6} cols={9} />
                  </td>
                </tr>
              ) : transactions.length === 0 ? (
                <tr>
                  <td colSpan={9} className="py-12 px-4">
                    <EmptyState
                      title="No transactions match your criteria"
                      description="Try adjusting your search query, status filters, or risk levels."
                      action={
                        hasActiveFilters ? (
                          <button
                            onClick={clearAllFilters}
                            className="rounded-lg bg-surface-elevated border border-border px-3 py-1.5 text-xs text-content hover:bg-surface focus-ring"
                          >
                            Reset all filters
                          </button>
                        ) : undefined
                      }
                    />
                  </td>
                </tr>
              ) : (
                transactions.map((tx) => {
                  const counterpart = tx.invoice?.customer_name || tx.gateway_transaction?.customer_name || tx.bank_transaction?.description || "Unknown Counterparty";
                  const orderId = tx.gateway_transaction?.payment_reference || tx.invoice?.invoice_reference || tx.bank_transaction?.reference || "";
                  const sourcePills = [
                    tx.invoice_id ? { label: "INV", id: cleanId(tx.invoice_id) } : null,
                    tx.gateway_txn_id ? { label: "GTW", id: cleanId(tx.gateway_txn_id) } : null,
                    tx.bank_txn_id ? { label: "BNK", id: cleanId(tx.bank_txn_id) } : null,
                  ].filter(Boolean);
                  const amt = tx.primary_amount || tx.bank_transaction?.amount || tx.gateway_transaction?.amount || tx.invoice?.amount || 0;
                  const dateStr = tx.bank_transaction?.transaction_date || tx.gateway_transaction?.transaction_date || tx.invoice?.invoice_date || tx.created_at;

                  return (
                    <tr
                      key={tx.match_id}
                      onClick={() => setSelectedMatchId(tx.match_id)}
                      className="hover:bg-surface-elevated/50 cursor-pointer transition-colors"
                    >
                      {/* Transaction / Reference Primary Column */}
                      <td className="px-4 py-3 whitespace-nowrap">
                        <div className="flex items-center gap-1.5">
                          <span className="font-bold text-content font-mono">{orderId || cleanId(tx.match_id)}</span>
                          {tx.topology === "MANY_TO_ONE" && (
                            <span className="px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-700 dark:text-purple-300 border border-purple-500/30 text-[9px] font-mono font-bold">
                              BATCH
                            </span>
                          )}
                        </div>
                        <div className="text-[10px] text-content-muted font-mono mt-0.5">
                          ID: {cleanId(tx.match_id)}
                        </div>
                      </td>

                      {/* Counterparty */}
                      <td className="px-4 py-3 max-w-[200px]">
                        <div className="font-medium text-content truncate">{counterpart}</div>
                        {sourcePills.length > 0 && (
                          <div className="flex items-center gap-1 mt-0.5 text-[9px] font-mono text-content-secondary">
                            {sourcePills.map((p, idx) => (
                              <span key={idx} className="bg-surface px-1 py-0.2 rounded border border-border">
                                {p!.label}:{p!.id}
                              </span>
                            ))}
                          </div>
                        )}
                      </td>

                      {/* Date */}
                      <td className="px-4 py-3 text-content-secondary whitespace-nowrap font-mono">
                        {formatDate(dateStr)}
                      </td>

                      {/* Financial Amount */}
                      <td className="px-4 py-3 whitespace-nowrap">
                        <div className="font-bold text-content tabular-nums">{formatCurrency(amt)}</div>
                        {tx.variance_amount !== undefined && Math.abs(tx.variance_amount) >= 0.01 && (
                          <div className="text-[10px] font-mono text-amber-600 dark:text-amber-400 font-semibold tabular-nums">
                            Var: {tx.variance_amount > 0 ? "+" : ""}{formatCurrency(tx.variance_amount)}
                          </div>
                        )}
                      </td>

                      {/* Match Type */}
                      <td className="px-4 py-3 whitespace-nowrap">
                        <MatchTypeTag matchType={tx.reason_code || tx.match_type} />
                      </td>

                      {/* Status Badge */}
                      <td className="px-4 py-3 whitespace-nowrap">
                        <StatusBadge status={tx.decision} />
                      </td>

                      {/* Confidence Score */}
                      <td className="px-4 py-3 whitespace-nowrap">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-content font-semibold tabular-nums">
                            {formatPercent(tx.confidence_score)}
                          </span>
                          <div className="w-10 bg-surface-elevated h-1.5 rounded-full overflow-hidden">
                            <div
                              className="bg-primary-light h-full rounded-full"
                              style={{ width: `${Math.min(100, tx.confidence_score * 100)}%` }}
                            />
                          </div>
                        </div>
                      </td>

                      {/* Risk Level */}
                      <td className="px-4 py-3 whitespace-nowrap">
                        <RiskBadge risk={tx.risk_level} />
                      </td>

                      {/* View Action Trigger */}
                      <td className="px-4 py-3 text-right whitespace-nowrap">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedMatchId(tx.match_id);
                          }}
                          className="rounded-lg bg-surface-elevated border border-border px-2.5 py-1 text-[11px] font-semibold text-content hover:bg-surface transition-colors focus-ring shadow-xs"
                        >
                          View
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Footer */}
        <div className="flex items-center justify-between border-t border-border px-4 py-3 text-xs text-content-secondary bg-surface/50">
          <div>
            Page <span className="font-semibold text-content tabular-nums">{page}</span> of{" "}
            <span className="font-semibold text-content tabular-nums">{totalPages}</span>
          </div>
          <div className="flex items-center gap-2">
            <button
              disabled={page <= 1}
              onClick={() => setPage(page - 1)}
              className="rounded-lg border border-border bg-surface px-3 py-1 text-content-secondary hover:text-content hover:bg-surface-elevated disabled:opacity-40 transition-colors focus-ring"
            >
              Previous
            </button>
            <button
              disabled={page >= totalPages}
              onClick={() => setPage(page + 1)}
              className="rounded-lg border border-border bg-surface px-3 py-1 text-content-secondary hover:text-content hover:bg-surface-elevated disabled:opacity-40 transition-colors focus-ring"
            >
              Next
            </button>
          </div>
        </div>

      </div>

      {/* 3-Way Match Investigation Modal */}
      {selectedMatchId && (
        <MatchDetailModal
          matchId={selectedMatchId}
          onClose={() => setSelectedMatchId(null)}
        />
      )}

    </div>
  );
}
