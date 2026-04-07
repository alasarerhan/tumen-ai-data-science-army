import React from "react";
import ReactECharts from "echarts-for-react";

interface SeriesItem {
  name: string;
  data: number[];
}

interface TrendChartProps {
  categories?: string[];
  series: SeriesItem[];
  height?: number;
}

export function TrendChart({ categories, series, height = 260 }: TrendChartProps) {
  const option = {
    tooltip: { trigger: "axis" },
    legend: { top: 0 },
    grid: { left: 28, right: 16, top: 38, bottom: 26 },
    xAxis: {
      type: "category",
      data: categories ?? series[0]?.data.map((_, idx) => `T${idx + 1}`),
      axisLine: { lineStyle: { color: "#cbd5e1" } },
    },
    yAxis: {
      type: "value",
      axisLine: { show: false },
      splitLine: { lineStyle: { color: "#e2e8f0" } },
    },
    series: series.map((item) => ({
      ...item,
      type: "line",
      smooth: true,
      showSymbol: false,
      areaStyle: { opacity: 0.08 },
    })),
  };

  return <ReactECharts option={option} style={{ width: "100%", height }} />;
}

