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

export function CashForecastChart({ points }: CashForecastChartProps) {
  if (!points || points.length === 0) {
    return (
      <div className="flex h-72 items-center justify-center text-xs text-gray-500">
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
              <stop offset="5%" stopColor="#4f46e5" stopOpacity={0.4} />
              <stop offset="95%" stopColor="#4f46e5" stopOpacity={0.0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" vertical={false} />
          <XAxis dataKey="name" tick={{ fill: "#9ca3af", fontSize: 11 }} />
          <YAxis
            tick={{ fill: "#9ca3af", fontSize: 11 }}
            tickFormatter={(val) => `₹${(val / 1000).toFixed(0)}k`}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "#111827",
              borderColor: "#374151",
              borderRadius: "0.5rem",
              fontSize: "12px",
              color: "#fff",
            }}
            formatter={(val: number, name: string) => [
              `₹${val.toLocaleString()}`,
              name === "projectedBalance" ? "Projected Cash Position" : name,
            ]}
          />
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
