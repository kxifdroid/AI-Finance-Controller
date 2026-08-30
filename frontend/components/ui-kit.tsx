import { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { formatCurrency } from "@/lib/utils";
import {
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Copy as CopyIcon,
  MinusCircle,
  Layers as LayersIcon,
} from "lucide-react";

/* ==========================================================================
   Shared enterprise UI primitives.

   Centralizes status/risk styling, page headers, metric cards, empty/error
   states and financial-number formatting so every page stays visually
   consistent and styling logic is not duplicated. Purely presentational —
   no data fetching, no business logic.
   ========================================================================== */

// ---------------------------------------------------------------------------
// Decision / Status
// ---------------------------------------------------------------------------

export type DecisionStatus =
  | "MATCH"
  | "REVIEW"
  | "EXCEPTION"
  | "DUPLICATE"
  | "MISSING"
  | string;

const STATUS_CONFIG: Record<
  string,
  { label: string; className: string; Icon: typeof CheckCircle2 }
> = {
  MATCH: {
    label: "Match",
    className: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border-emerald-500/30",
    Icon: CheckCircle2,
  },
  REVIEW: {
    label: "Review",
    className: "bg-amber-500/15 text-amber-700 dark:text-amber-300 border-amber-500/30",
    Icon: AlertTriangle,
  },
  EXCEPTION: {
    label: "Exception",
    className: "bg-rose-500/15 text-rose-700 dark:text-rose-300 border-rose-500/30",
    Icon: XCircle,
  },
  DUPLICATE: {
    label: "Duplicate",
    className: "bg-violet-500/15 text-violet-700 dark:text-violet-300 border-violet-500/30",
    Icon: CopyIcon,
  },
  MISSING: {
    label: "Missing",
    className: "bg-slate-500/15 text-slate-700 dark:text-slate-300 border-slate-500/30",
    Icon: MinusCircle,
  },
};

export function StatusBadge({
  status,
  size = "sm",
  withIcon = true,
  className,
}: {
  status: DecisionStatus;
  size?: "sm" | "md";
  withIcon?: boolean;
  className?: string;
}) {
  const key = (status || "").toUpperCase();
  const cfg = STATUS_CONFIG[key] || STATUS_CONFIG.MISSING;
  const Icon = cfg.Icon;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border font-semibold uppercase tracking-wide",
        size === "sm" ? "px-2 py-0.5 text-[11px]" : "px-2.5 py-1 text-xs",
        cfg.className,
        className
      )}
    >
      {withIcon && <Icon className={size === "sm" ? "h-3 w-3" : "h-3.5 w-3.5"} />}
      {cfg.label}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Risk
// ---------------------------------------------------------------------------

const RISK_CONFIG: Record<string, string> = {
  LOW: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border-emerald-500/30",
  MEDIUM: "bg-amber-500/15 text-amber-700 dark:text-amber-300 border-amber-500/30",
  HIGH: "bg-rose-500/15 text-rose-700 dark:text-rose-300 border-rose-500/30",
};

export function RiskBadge({
  risk,
  className,
}: {
  risk: string;
  className?: string;
}) {
  const key = (risk || "").toUpperCase();
  const style = RISK_CONFIG[key] || RISK_CONFIG.MEDIUM;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide",
        style,
        className
      )}
    >
      <span
        className={cn(
          "h-1.5 w-1.5 rounded-full",
          key === "HIGH"
            ? "bg-rose-400"
            : key === "MEDIUM"
            ? "bg-amber-400"
            : "bg-emerald-400"
        )}
      />
      {key} {key === "LOW" || key === "MEDIUM" || key === "HIGH" ? "Risk" : ""}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Match type (secondary metadata — visually distinct from status)
// ---------------------------------------------------------------------------

const MATCH_TYPE_LABELS: Record<string, string> = {
  EXACT: "Exact 3-Way",
  EXACT_3_WAY_MATCH: "Exact 3-Way",
  TIMING_DIFFERENCE: "Timing Difference",
  FEE_RECONCILED: "Fee Reconciled",
  MANY_TO_ONE: "Many-to-One",
  ONE_TO_MANY: "One-to-Many",
  FUZZY: "Fuzzy",
  AMOUNT_MISMATCH: "Amount Mismatch",
  MISSING_BANK_SETTLEMENT: "Missing Bank",
  MISSING_GATEWAY_TRANSACTION: "Missing Gateway",
  MISSING_ERP_TRANSACTION: "Missing ERP",
  CURRENCY_MISMATCH: "Currency Mismatch",
};

export function humanizeMatchType(raw?: string | null): string {
  if (!raw) return "—";
  return (
    MATCH_TYPE_LABELS[raw.toUpperCase()] ||
    raw
      .replace(/_/g, " ")
      .toLowerCase()
      .replace(/\b\w/g, (c) => c.toUpperCase())
  );
}

export function MatchTypeTag({
  matchType,
  className,
}: {
  matchType?: string | null;
  className?: string;
}) {
  if (!matchType) return <span className="text-xs text-gray-500">—</span>;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md bg-surface-elevated border border-border px-2 py-0.5 text-[11px] font-medium text-gray-300",
        className
      )}
    >
      <LayersIcon className="h-3 w-3 text-gray-500" />
      {humanizeMatchType(matchType)}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Page header
// ---------------------------------------------------------------------------

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
      <div className="min-w-0">
        <h1 className="text-2xl font-bold tracking-tight text-content sm:text-[26px]">
          {title}
        </h1>
        {description && (
          <p className="mt-1 text-sm text-content-secondary">{description}</p>
        )}
      </div>
      {actions && (
        <div className="flex flex-wrap items-center gap-2 shrink-0">{actions}</div>
      )}
    </div>
  );
}

export function SectionHeader({
  title,
  description,
  actions,
  className,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex items-center justify-between gap-4", className)}>
      <div>
        <h2 className="text-base font-semibold text-content">{title}</h2>
        {description && (
          <p className="mt-0.5 text-xs text-content-secondary">{description}</p>
        )}
      </div>
      {actions}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Metric card
// ---------------------------------------------------------------------------

export function MetricCard({
  label,
  value,
  context,
  icon,
  trend,
  accent = "neutral",
}: {
  label: string;
  value: string | number;
  context?: string;
  icon?: ReactNode;
  trend?: { value: string; positive: boolean };
  accent?: "neutral" | "primary" | "success" | "warning" | "danger" | "ai";
}) {
  const accentBar: Record<string, string> = {
    neutral: "bg-slate-500",
    primary: "bg-indigo-500",
    success: "bg-emerald-500",
    warning: "bg-amber-500",
    danger: "bg-rose-500",
    ai: "bg-violet-500",
  };
  const iconTint: Record<string, string> = {
    neutral: "text-slate-600 dark:text-gray-400 bg-slate-200/50 dark:bg-gray-800/50",
    primary: "text-indigo-600 dark:text-indigo-300 bg-indigo-500/10",
    success: "text-emerald-600 dark:text-emerald-300 bg-emerald-500/10",
    warning: "text-amber-600 dark:text-amber-300 bg-amber-500/10",
    danger: "text-rose-600 dark:text-rose-300 bg-rose-500/10",
    ai: "text-violet-600 dark:text-violet-300 bg-violet-500/10",
  };
  return (
    <div className="relative overflow-hidden rounded-xl border border-border bg-surface-secondary p-4 transition-colors hover:border-border-strong shadow-xs">
      <span
        className={cn("absolute left-0 top-0 h-full w-0.5", accentBar[accent])}
        aria-hidden
      />
      <div className="flex items-start justify-between">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-content-secondary">
          {label}
        </span>
        {icon && (
          <div className={cn("rounded-lg p-1.5", iconTint[accent])}>{icon}</div>
        )}
      </div>
      <div className="mt-2 flex items-baseline gap-2">
        <span className="text-2xl font-bold tracking-tight text-content tabular-nums">
          {value}
        </span>
        {trend && (
          <span
            className={cn(
              "rounded px-1.5 py-0.5 text-[11px] font-semibold tabular-nums",
              trend.positive
                ? "text-emerald-700 dark:text-emerald-400 bg-emerald-500/10"
                : "text-rose-700 dark:text-rose-400 bg-rose-500/10"
            )}
          >
            {trend.value}
          </span>
        )}
      </div>
      {context && <p className="mt-1 text-xs text-content-muted">{context}</p>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Financial amount
// ---------------------------------------------------------------------------

export function FinancialAmount({
  value,
  size = "md",
  emphasis = "normal",
  showSign = false,
  className,
}: {
  value: number | null | undefined;
  size?: "sm" | "md" | "lg" | "xl";
  emphasis?: "normal" | "muted" | "danger" | "success";
  showSign?: boolean;
  className?: string;
}) {
  const sizeClass = {
    sm: "text-sm",
    md: "text-base",
    lg: "text-lg",
    xl: "text-2xl",
  }[size];
  const emphasisClass = {
    normal: "text-content",
    muted: "text-content-secondary",
    danger: "text-rose-600 dark:text-rose-300",
    success: "text-emerald-600 dark:text-emerald-300",
  }[emphasis];
  const n = value ?? 0;
  const formatted = formatCurrency(Math.abs(n));
  const sign = n < 0 ? "−" : showSign && n > 0 ? "+" : "";
  return (
    <span
      className={cn(
        "font-semibold tabular-nums",
        sizeClass,
        emphasisClass,
        className
      )}
    >
      {sign}
      {formatted}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Empty / Error / Loading states
// ---------------------------------------------------------------------------

export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border bg-surface-secondary/50 px-6 py-14 text-center">
      {icon && (
        <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-surface-elevated text-content-muted">
          {icon}
        </div>
      )}
      <h3 className="text-sm font-semibold text-content">{title}</h3>
      {description && (
        <p className="mt-1 max-w-sm text-xs text-content-secondary">{description}</p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ErrorState({
  title = "Something went wrong",
  message,
  detail,
  onRetry,
}: {
  title?: string;
  message: string;
  detail?: string;
  onRetry?: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-rose-500/30 bg-rose-500/5 px-6 py-12 text-center">
      <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-rose-500/10 text-rose-500 dark:text-rose-400">
        <AlertTriangle className="h-6 w-6" />
      </div>
      <h3 className="text-sm font-semibold text-content">{title}</h3>
      <p className="mt-1 max-w-sm text-xs text-content-secondary">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-4 rounded-lg border border-border bg-surface-elevated px-4 py-2 text-xs font-semibold text-content transition-colors hover:bg-surface focus-ring"
        >
          Retry
        </button>
      )}
      {detail && (
        <details className="mt-3 max-w-md text-left">
          <summary className="cursor-pointer text-[11px] text-content-muted hover:text-content-secondary">
            View technical details
          </summary>
          <pre className="mt-2 overflow-auto rounded-lg bg-surface-elevated p-2 text-[10px] text-content-muted border border-border">
            {detail}
          </pre>
        </details>
      )}
    </div>
  );
}

export function SkeletonRows({
  rows = 6,
  cols = 6,
}: {
  rows?: number;
  cols?: number;
}) {
  return (
    <div className="space-y-2 p-2" aria-busy="true" aria-label="Loading">
      {Array.from({ length: rows }).map((_, r) => (
        <div key={r} className="flex gap-3">
          {Array.from({ length: cols }).map((_, c) => (
            <div
              key={c}
              className="skeleton h-9 flex-1 rounded-md"
              style={{ opacity: 1 - r * 0.08 }}
            />
          ))}
        </div>
      ))}
    </div>
  );
}

export function SkeletonCards({ count = 4 }: { count?: number }) {
  return (
    <div
      className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4"
      aria-busy="true"
      aria-label="Loading"
    >
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          className="rounded-xl border border-border bg-surface-secondary p-4"
        >
          <div className="skeleton h-3 w-24 rounded" />
          <div className="skeleton mt-3 h-7 w-20 rounded" />
          <div className="skeleton mt-2 h-3 w-28 rounded" />
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Decision Banner (Enterprise Investigation Summary)
// ---------------------------------------------------------------------------

export function DecisionBanner({
  decision,
  reasonCode,
  explanation,
  recommendedAction,
  amounts,
}: {
  decision: DecisionStatus;
  reasonCode?: string | null;
  explanation: string;
  recommendedAction?: string | null;
  amounts?: {
    invoice_total?: number;
    gateway_gross_total?: number;
    bank_credit_total?: number;
    variance?: number;
  } | null;
}) {
  const isMatch = decision === "MATCH";
  const isReview = decision === "REVIEW";
  const isException = decision === "EXCEPTION";

  const bannerColor = isMatch
    ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-900 dark:text-emerald-300"
    : isReview
    ? "border-amber-500/30 bg-amber-500/10 text-amber-900 dark:text-amber-300"
    : isException
    ? "border-rose-500/30 bg-rose-500/10 text-rose-900 dark:text-rose-300"
    : "border-border bg-surface-secondary text-content";

  return (
    <div className={cn("rounded-xl border p-4 space-y-3 shadow-xs", bannerColor)}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <StatusBadge status={decision} size="md" />
          {reasonCode && <MatchTypeTag matchType={reasonCode} />}
        </div>
        {amounts && Math.abs(amounts.variance ?? 0) >= 0.01 && (
          <span className="text-xs font-mono font-bold text-rose-600 dark:text-rose-400 bg-rose-500/15 border border-rose-500/30 px-2 py-0.5 rounded">
            Variance: {formatCurrency(Math.abs(amounts.variance ?? 0))}
          </span>
        )}
      </div>

      <p className="text-sm font-semibold text-content leading-relaxed">{explanation}</p>

      {/* Amounts breakdown if present */}
      {amounts && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2 border-t border-border/80 text-xs">
          <div className="rounded-lg bg-surface p-2 border border-border">
            <span className="text-content-secondary block text-[10px] uppercase font-semibold">ERP Invoice</span>
            <span className="font-bold text-content tabular-nums">{formatCurrency(amounts.invoice_total)}</span>
          </div>
          <div className="rounded-lg bg-surface p-2 border border-border">
            <span className="text-content-secondary block text-[10px] uppercase font-semibold">Gateway Gross</span>
            <span className="font-bold text-content tabular-nums">{formatCurrency(amounts.gateway_gross_total)}</span>
          </div>
          <div className="rounded-lg bg-surface p-2 border border-border">
            <span className="text-content-secondary block text-[10px] uppercase font-semibold">Bank Credit</span>
            <span className="font-bold text-content tabular-nums">{formatCurrency(amounts.bank_credit_total)}</span>
          </div>
          <div className="rounded-lg bg-surface p-2 border border-border">
            <span className="text-content-secondary block text-[10px] uppercase font-semibold">Discrepancy</span>
            <span className={cn("font-bold tabular-nums", Math.abs(amounts.variance ?? 0) < 0.01 ? "text-emerald-600 dark:text-emerald-400" : "text-amber-600 dark:text-amber-400")}>
              {Math.abs(amounts.variance ?? 0) < 0.01 ? "₹0.00 ✓" : formatCurrency(Math.abs(amounts.variance ?? 0))}
            </span>
          </div>
        </div>
      )}

      {recommendedAction && (
        <div className="pt-2 border-t border-border/80 flex flex-col sm:flex-row sm:items-center justify-between gap-1 text-xs">
          <span className="text-content-secondary font-medium">Recommended Action:</span>
          <span className="font-bold text-content">{recommendedAction}</span>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Evidence Signal (Qualitative strength indicator)
// ---------------------------------------------------------------------------

export function EvidenceSignal({
  label,
  score,
  weight,
}: {
  label: string;
  score: number;
  weight: number;
}) {
  const strength =
    score >= 0.95
      ? { text: "Strong Match", color: "text-emerald-600 dark:text-emerald-400", bar: "bg-emerald-500" }
      : score >= 0.70
      ? { text: "Partial Alignment", color: "text-amber-600 dark:text-amber-400", bar: "bg-amber-500" }
      : { text: "Discrepancy", color: "text-rose-600 dark:text-rose-400", bar: "bg-rose-500" };

  return (
    <div className="rounded-lg bg-surface p-2.5 border border-border shadow-xs">
      <div className="flex items-center justify-between text-[11px]">
        <span className="text-content-secondary font-medium">{label} ({weight.toFixed(2)})</span>
        <span className={cn("font-semibold text-[10px]", strength.color)}>{strength.text}</span>
      </div>
      <div className="mt-1 flex items-baseline justify-between">
        <span className="text-sm font-bold text-content tabular-nums">{(score * 100).toFixed(1)}%</span>
        <span className="text-[10px] font-mono text-content-muted">score: {score.toFixed(4)}</span>
      </div>
      <div className="w-full bg-surface-elevated h-1.5 rounded-full mt-1.5 overflow-hidden">
        <div className={cn("h-full rounded-full", strength.bar)} style={{ width: `${Math.min(100, Math.max(0, score * 100))}%` }} />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Filter Chip (Active Removable Filter)
// ---------------------------------------------------------------------------

export function FilterChip({
  label,
  value,
  onRemove,
}: {
  label: string;
  value: string;
  onRemove: () => void;
}) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-lg border border-border-strong bg-surface-elevated px-2.5 py-1 text-xs font-medium text-content shadow-xs">
      <span className="text-content-secondary">{label}:</span>
      <span className="font-semibold text-content">{value}</span>
      <button
        type="button"
        onClick={onRemove}
        className="ml-0.5 rounded p-0.5 text-content-secondary hover:bg-surface hover:text-content transition-colors focus-ring"
        aria-label={`Remove ${label} filter`}
      >
        ✕
      </button>
    </span>
  );
}
