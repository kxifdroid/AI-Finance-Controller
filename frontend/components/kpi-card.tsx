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
    default: "border-border bg-card/70 hover:border-gray-700",
    primary: "border-primary/30 bg-primary/5 hover:border-primary/50",
    success: "border-emerald-500/30 bg-emerald-500/5 hover:border-emerald-500/50",
    warning: "border-amber-500/30 bg-amber-500/5 hover:border-amber-500/50",
    danger: "border-rose-500/30 bg-rose-500/5 hover:border-rose-500/50",
  };

  return (
    <div
      className={cn(
        "rounded-xl border p-4 backdrop-blur-sm transition-all duration-200 shadow-sm",
        variantStyles[variant]
      )}
    >
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-gray-400 tracking-wide uppercase">{title}</span>
        {icon && <div className="text-gray-400 p-1.5 rounded-lg bg-gray-800/40">{icon}</div>}
      </div>

      <div className="mt-2 flex items-baseline justify-between">
        <div className="text-2xl font-bold tracking-tight text-white">{value}</div>
        {trend && (
          <span
            className={cn(
              "text-[11px] font-semibold px-1.5 py-0.5 rounded",
              trend.positive ? "text-emerald-400 bg-emerald-500/10" : "text-rose-400 bg-rose-500/10"
            )}
          >
            {trend.value}
          </span>
        )}
      </div>

      {subtitle && <p className="mt-1 text-xs text-gray-500 line-clamp-1">{subtitle}</p>}
    </div>
  );
}
