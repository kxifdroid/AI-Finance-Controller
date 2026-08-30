import { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface KPICardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon?: ReactNode;
  trend?: {
    value: string;
    positive: boolean;
  };
  variant?: "default" | "success" | "warning" | "danger" | "primary";
}

export function KPICard({
  title,
  value,
  subtitle,
  icon,
  trend,
  variant = "default",
}: KPICardProps) {
  const variantStyles = {
    default: "border-border bg-surface-secondary hover:border-border-strong",
    primary: "border-primary/30 bg-surface-secondary hover:border-primary/50",
    success: "border-emerald-500/30 bg-surface-secondary hover:border-emerald-500/50",
    warning: "border-amber-500/30 bg-surface-secondary hover:border-amber-500/50",
    danger: "border-rose-500/30 bg-surface-secondary hover:border-rose-500/50",
  };

  return (
    <div
      className={cn(
        "rounded-xl border p-4 transition-all duration-200 shadow-sm relative overflow-hidden",
        variantStyles[variant]
      )}
    >
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-semibold text-gray-400 tracking-wider uppercase">{title}</span>
        {icon && <div className="text-gray-400 p-1.5 rounded-lg bg-surface-elevated border border-border/60">{icon}</div>}
      </div>

      <div className="mt-2 flex items-baseline justify-between gap-2">
        <div className="text-2xl font-bold tracking-tight text-white tabular-nums">{value}</div>
        {trend && (
          <span
            className={cn(
              "text-[11px] font-semibold px-1.5 py-0.5 rounded tabular-nums shrink-0",
              trend.positive ? "text-emerald-400 bg-emerald-500/10" : "text-rose-400 bg-rose-500/10"
            )}
          >
            {trend.value}
          </span>
        )}
      </div>

      {subtitle && <p className="mt-1 text-xs text-gray-400 line-clamp-1">{subtitle}</p>}
    </div>
  );
}
