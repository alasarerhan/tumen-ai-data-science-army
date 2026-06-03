import ReactECharts from "echarts-for-react";

interface SankeyNode {
  name: string;
  value?: number;
}

interface SankeyLink {
  source: string;
  target: string;
  value?: number;
}

interface SankeyChartProps {
  nodes: SankeyNode[];
  links: SankeyLink[];
  height?: number;
}

export function SankeyChart({ nodes, links, height = 280 }: SankeyChartProps) {
  const option = {
    tooltip: { trigger: "item" },
    series: [
      {
        type: "sankey",
        data: nodes,
        links,
        emphasis: { focus: "adjacency" },
        lineStyle: { color: "source", curveness: 0.5 },
        label: { color: "#334155", fontSize: 12 },
      },
    ],
  };

  return <ReactECharts option={option} style={{ width: "100%", height }} />;
}

