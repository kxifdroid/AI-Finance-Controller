"use client";

import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from "recharts";

interface StatusDonutChartProps {
  data: Array<{ name: string; value: number; color: string }>;
}

const CustomTooltip = ({ active, payload }: any) => {
  if (active && payload && payload.length) {
    const item = payload[0];
    return (
      <div className="rounded-lg border border-border bg-surface p-2.5 shadow-lg text-xs space-y-0.5">
        <p className="font-semibold text-content">{item.name}</p>
        <p className="text-content-secondary tabular-nums">
          <span className="font-bold text-content">{item.value}</span> transactions
        </p>
      </div>
    );
  }
  return null;
};

export function StatusDonutChart({ data }: StatusDonutChartProps) {
  if (!data || data.length === 0 || data.every(d => d.value === 0)) {
    return (
      <div className="flex h-64 items-center justify-center text-xs text-content-muted">
        No reconciliation data available. Run the pipeline to populate.
      </div>
    );
  }

  const validData = data.filter(d => d.value > 0);

  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={validData}
            cx="50%"
            cy="50%"
            innerRadius={55}
            outerRadius={80}
            paddingAngle={4}
            dataKey="value"
          >
            {validData.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={entry.color} stroke="var(--bg-surface)" strokeWidth={2} />
            ))}
          </Pie>
          <Tooltip content={<CustomTooltip />} />
          <Legend
            verticalAlign="bottom"
            height={36}
            formatter={(value) => <span className="text-xs text-content-secondary mr-2">{value}</span>}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
