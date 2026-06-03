import ReactECharts from "echarts-for-react";

interface NetworkNode {
  name: string;
  value?: number;
  category?: string;
}

interface NetworkLink {
  source: string;
  target: string;
  value?: number;
}

interface NetworkChartProps {
  nodes: NetworkNode[];
  links: NetworkLink[];
  height?: number;
}

export function NetworkChart({ nodes, links, height = 280 }: NetworkChartProps) {
  const categories = Array.from(new Set(nodes.map((n) => n.category).filter(Boolean))).map((c) => ({ name: c }));

  const option = {
    tooltip: { trigger: "item" },
    legend: categories.length > 0 ? [{ data: categories.map((c) => c.name) }] : undefined,
    series: [
      {
        type: "graph",
        layout: "force",
        roam: true,
        label: { show: true, color: "#334155", fontSize: 11 },
        force: { repulsion: 140, edgeLength: [40, 120] },
        data: nodes,
        links,
        categories,
        lineStyle: { color: "#94a3b8", width: 1.2 },
      },
    ],
  };

  return <ReactECharts option={option} style={{ width: "100%", height }} />;
}

