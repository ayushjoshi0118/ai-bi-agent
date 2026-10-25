"use client";

import React from "react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  BarChart,
  Bar,
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from "recharts";
import { ChartSpec } from "../../lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "../ui/card";
import { KPICard } from "../ui/kpi-card";

const COLOR_PALETTE = [
  "#4f46e5", // Indigo
  "#06b6d4", // Cyan
  "#10b981", // Emerald
  "#f59e0b", // Amber
  "#ef4444", // Red
  "#8b5cf6", // Purple
  "#ec4899", // Pink
];

export function ChartRenderer({ spec }: { spec?: ChartSpec | null }) {
  if (!spec || !spec.data || spec.data.length === 0) {
    return (
      <div className="p-8 text-center text-xs text-gray-400 bg-gray-50 rounded-lg border border-dashed">
        No visualization data available for this query.
      </div>
    );
  }

  // 1. KPI Card
  if (spec.chart_type === "kpi_card") {
    return (
      <KPICard
        title={spec.title}
        value={spec.kpi_value || String(spec.data[0][spec.x_axis?.field || "value"] || "0")}
        change={spec.kpi_change}
        changeDirection={spec.kpi_change_direction}
        subtitle={spec.subtitle}
      />
    );
  }

  // 2. Data Table
  if (spec.chart_type === "table") {
    const columns = Object.keys(spec.data[0] || {});
    return (
      <Card className="my-3">
        <CardHeader>
          <CardTitle className="text-sm">{spec.title}</CardTitle>
          {spec.subtitle && <p className="text-xs text-gray-500">{spec.subtitle}</p>}
        </CardHeader>
        <div className="overflow-x-auto max-h-80">
          <table className="w-full text-left text-xs text-gray-600">
            <thead className="bg-gray-50 text-gray-700 font-semibold sticky top-0 border-b border-gray-200">
              <tr>
                {columns.map((col) => (
                  <th key={col} className="px-4 py-2 capitalize whitespace-nowrap">
                    {col.replace("_", " ")}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {spec.data.map((row, idx) => (
                <tr key={idx} className="hover:bg-gray-50">
                  {columns.map((col) => (
                    <td key={col} className="px-4 py-2 whitespace-nowrap">
                      {String(row[col] ?? "-")}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    );
  }

  const xField = spec.x_axis?.field || Object.keys(spec.data[0])[0];
  const seriesList =
    spec.series && spec.series.length > 0
      ? spec.series
      : [{ field: spec.y_axis?.field || Object.keys(spec.data[0])[1] || xField, label: "Value" }];

  return (
    <Card className="my-3">
      <CardHeader>
        <CardTitle className="text-sm font-semibold text-gray-900">{spec.title}</CardTitle>
        {spec.subtitle && <p className="text-xs text-gray-500">{spec.subtitle}</p>}
      </CardHeader>
      <CardContent>
        <div className="h-72 w-full pt-2">
          <ResponsiveContainer width="100%" height="100%">
            {/* 3. Line Chart */}
            {spec.chart_type === "line" ? (
              <LineChart data={spec.data}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey={xField} stroke="#64748b" fontSize={11} />
                <YAxis stroke="#64748b" fontSize={11} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#1e293b",
                    borderColor: "#334155",
                    borderRadius: "8px",
                    color: "#ffffff",
                    fontSize: "12px",
                  }}
                />
                <Legend wrapperStyle={{ fontSize: "11px" }} />
                {seriesList.map((s, idx) => (
                  <Line
                    key={s.field}
                    type="monotone"
                    dataKey={s.field}
                    name={s.label || s.field}
                    stroke={s.color || COLOR_PALETTE[idx % COLOR_PALETTE.length]}
                    strokeWidth={2}
                    dot={{ r: 3 }}
                  />
                ))}
              </LineChart>
            ) : spec.chart_type === "scatter" ? (
              /* 4. Scatter Plot */
              <ScatterChart>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey={xField} name={xField} stroke="#64748b" fontSize={11} />
                <YAxis dataKey={seriesList[0].field} name={seriesList[0].field} stroke="#64748b" fontSize={11} />
                <Tooltip cursor={{ strokeDasharray: "3 3" }} />
                <Scatter
                  name={spec.title}
                  data={spec.data}
                  fill="#4f46e5"
                />
              </ScatterChart>
            ) : (
              /* 5. Bar & Stacked Bar Chart */
              <BarChart data={spec.data}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey={xField} stroke="#64748b" fontSize={11} />
                <YAxis stroke="#64748b" fontSize={11} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#1e293b",
                    borderColor: "#334155",
                    borderRadius: "8px",
                    color: "#ffffff",
                    fontSize: "12px",
                  }}
                />
                <Legend wrapperStyle={{ fontSize: "11px" }} />
                {seriesList.map((s, idx) => (
                  <Bar
                    key={s.field}
                    dataKey={s.field}
                    name={s.label || s.field}
                    fill={s.color || COLOR_PALETTE[idx % COLOR_PALETTE.length]}
                    stackId={spec.chart_type === "stacked_bar" ? "stack1" : undefined}
                    radius={[4, 4, 0, 0]}
                  />
                ))}
              </BarChart>
            )}
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}
