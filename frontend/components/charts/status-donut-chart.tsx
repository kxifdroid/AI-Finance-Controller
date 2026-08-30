"use client";

import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from "recharts";

interface StatusDonutChartProps {
  data: Array<{ name: string; value: number; color: string }>;
}

export function StatusDonutChart({ data }: StatusDonutChartProps) {
  if (!data || data.length === 0 || data.every(d => d.value === 0)) {
    return (
      <div className="flex h-64 items-center justify-center text-xs text-gray-500">
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
            formatter={(val: number) => [`${val} records`, "Count"]}
          />
          <Legend
            verticalAlign="bottom"
            height={36}
            formatter={(value) => <span className="text-xs text-gray-300 mr-2">{value}</span>}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
