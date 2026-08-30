"use client";

import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from "recharts";

interface SeverityChartProps {
  data: Array<{ severity: string; count: number }>;
}

const SEVERITY_COLORS: Record<string, string> = {
  HIGH: "#ef4444",
  MEDIUM: "#f59e0b",
  LOW: "#3b82f6",
};

const CustomSeverityTooltip = ({ active, payload }: any) => {
  if (active && payload && payload.length) {
    const item = payload[0];
    return (
      <div className="rounded-lg border border-border bg-surface p-2.5 shadow-xl text-xs space-y-0.5">
        <p className="font-semibold text-content">{item.name}</p>
        <p className="text-content-secondary tabular-nums">
          <span className="font-bold text-content">{item.value}</span> discrepancies
        </p>
      </div>
    );
  }
  return null;
};

export function SeverityChart({ data }: SeverityChartProps) {
  if (!data || data.length === 0 || data.every((d) => d.count === 0)) {
    return (
      <div className="flex h-64 items-center justify-center text-xs text-content-muted">
        No severity data available.
      </div>
    );
  }

  const chartData = data
    .filter((d) => d.count > 0)
    .map((d) => ({
      name: `${d.severity} Risk`,
      value: d.count,
      color: SEVERITY_COLORS[d.severity] || "#6b7280",
    }));

  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={chartData}
            cx="50%"
            cy="50%"
            outerRadius={75}
            dataKey="value"
            label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
            labelLine={false}
          >
            {chartData.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={entry.color} stroke="var(--bg-surface)" strokeWidth={2} />
            ))}
          </Pie>
          <Tooltip content={<CustomSeverityTooltip />} />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
