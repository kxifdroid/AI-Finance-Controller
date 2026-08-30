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

const CustomBarTooltip = ({ active, payload, label }: any) => {
  if (active && payload && payload.length) {
    const item = payload[0].payload;
    return (
      <div className="rounded-lg border border-border bg-surface p-2.5 shadow-xl text-xs space-y-1">
        <p className="font-bold text-content">{item.displayType}</p>
        <p className="text-rose-600 dark:text-rose-400 font-semibold tabular-nums">
          Count: {item.count} items
        </p>
        {item.amount > 0 && (
          <p className="text-content-secondary tabular-nums">
            Exposure: ₹{item.amount.toLocaleString()}
          </p>
        )}
      </div>
    );
  }
  return null;
};

export function ExceptionsBarChart({ data }: ExceptionsBarChartProps) {
  if (!data || data.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center text-xs text-content-muted">
        No exceptions recorded in this run.
      </div>
    );
  }

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
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color)" vertical={false} />
          <XAxis
            dataKey="displayType"
            tick={{ fill: "var(--text-secondary)", fontSize: 10 }}
            angle={-25}
            textAnchor="end"
            interval={0}
          />
          <YAxis tick={{ fill: "var(--text-secondary)", fontSize: 11 }} />
          <Tooltip content={<CustomBarTooltip />} />
          <Bar dataKey="count" fill="#ef4444" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
