"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

interface ExceptionsBarChartProps {
  data: Array<{ type: string; count: number; amount: number }>;
}

export function ExceptionsBarChart({ data }: ExceptionsBarChartProps) {
  if (!data || data.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center text-xs text-gray-500">
        No exceptions recorded in this run.
      </div>
    );
  }

  // Format type labels for clean readability
  const formatted = data.map((d) => ({
    ...d,
    displayType: d.type.replace(/_/g, " ").toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase()),
  }));

  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={formatted}
          margin={{ top: 10, right: 10, left: -20, bottom: 25 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" vertical={false} />
          <XAxis
            dataKey="displayType"
            tick={{ fill: "#9ca3af", fontSize: 10 }}
            angle={-25}
            textAnchor="end"
            interval={0}
          />
          <YAxis tick={{ fill: "#9ca3af", fontSize: 11 }} />
          <Tooltip
            contentStyle={{
              backgroundColor: "#111827",
              borderColor: "#374151",
              borderRadius: "0.5rem",
              fontSize: "12px",
              color: "#fff",
            }}
            formatter={(val: number, name: string) => [
              name === "count" ? `${val} exceptions` : `₹${val.toLocaleString()}`,
              name === "count" ? "Total Items" : "Monetary Volume",
            ]}
          />
          <Bar dataKey="count" fill="#ef4444" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
