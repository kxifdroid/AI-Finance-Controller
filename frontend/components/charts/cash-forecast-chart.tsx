"use client";

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { ForecastPoint } from "@/types";

interface CashForecastChartProps {
  points: ForecastPoint[];
}

const CustomForecastTooltip = ({ active, payload, label }: any) => {
  if (active && payload && payload.length) {
    return (
      <div className="rounded-lg border border-border bg-surface p-3 shadow-xl text-xs space-y-1.5 min-w-[180px]">
        <p className="font-bold text-content border-b border-border pb-1">{label}</p>
        <div className="space-y-1">
          <div className="flex justify-between items-center text-indigo-600 dark:text-indigo-400 font-semibold">
            <span>Projected Balance:</span>
            <span className="tabular-nums">₹{payload[0].value?.toLocaleString()}</span>
          </div>
        </div>
      </div>
    );
  }
  return null;
};

export function CashForecastChart({ points }: CashForecastChartProps) {
  if (!points || points.length === 0) {
    return (
      <div className="flex h-72 items-center justify-center text-xs text-content-muted">
        No forecast points available.
      </div>
    );
  }

  const chartData = points.map((p) => {
    const d = new Date(p.forecast_date);
    const label = p.day_offset === 0 ? "Today" : `Day +${p.day_offset} (${d.toLocaleDateString("en-GB", { day: "2-digit", month: "short" })})`;
    return {
      name: label,
      projectedBalance: p.projected_balance,
      clearedCash: p.cleared_cash,
      settlements: p.expected_settlements,
      receivables: p.expected_receivables,
    };
  });

  return (
    <div className="h-72 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={chartData} margin={{ top: 10, right: 20, left: 10, bottom: 0 }}>
          <defs>
            <linearGradient id="balanceGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#4f46e5" stopOpacity={0.35} />
              <stop offset="95%" stopColor="#4f46e5" stopOpacity={0.0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color)" vertical={false} />
          <XAxis dataKey="name" tick={{ fill: "var(--text-secondary)", fontSize: 11 }} />
          <YAxis
            tick={{ fill: "var(--text-secondary)", fontSize: 11 }}
            tickFormatter={(val) => `₹${(val / 1000).toFixed(0)}k`}
          />
          <Tooltip content={<CustomForecastTooltip />} />
          <Area
            type="monotone"
            dataKey="projectedBalance"
            stroke="#6366f1"
            strokeWidth={3}
            fillOpacity={1}
            fill="url(#balanceGradient)"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
