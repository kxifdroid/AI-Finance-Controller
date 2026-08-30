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

export function SeverityChart({ data }: SeverityChartProps) {
  if (!data || data.length === 0 || data.every((d) => d.count === 0)) {
    return (
      <div className="flex h-64 items-center justify-center text-xs text-gray-500">
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
              <Cell key={`cell-${index}`} fill={entry.color} stroke="#111827" strokeWidth={2} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{
              backgroundColor: "#111827",
              borderColor: "#374151",
              borderRadius: "0.5rem",
              fontSize: "12px",
              color: "#fff",
            }}
            formatter={(val: number) => [`${val} items`, "Severity Count"]}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
