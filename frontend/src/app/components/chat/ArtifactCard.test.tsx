import { render, screen } from "@testing-library/react";
import { ArtifactCard } from "./ArtifactCard";

vi.mock("../charts/sankey-chart", () => ({
  SankeyChart: () => <div data-testid="sankey-chart" />,
}));

vi.mock("../charts/network-chart", () => ({
  NetworkChart: () => <div data-testid="network-chart" />,
}));

vi.mock("../charts/trend-chart", () => ({
  TrendChart: () => <div data-testid="trend-chart" />,
}));

describe("ArtifactCard", () => {
  it("renders table artifact", () => {
    render(
      <ArtifactCard
        artifact={{
          type: "table",
          columns: ["name", "value"],
          records: [{ name: "A", value: 10 }],
        }}
      />,
    );

    expect(screen.getByText("Table")).toBeInTheDocument();
    expect(screen.getByText("name")).toBeInTheDocument();
    expect(screen.getByText("A")).toBeInTheDocument();
  });

  it("renders chart artifact by chart_type", () => {
    render(
      <ArtifactCard
        artifact={{
          type: "chart",
          chart_type: "network",
          nodes: [{ name: "A" }],
          links: [],
        }}
      />,
    );

    expect(screen.getByTestId("network-chart")).toBeInTheDocument();
  });

  it("renders code artifact", () => {
    render(
      <ArtifactCard
        artifact={{
          type: "code",
          language: "python",
          code: "print('hello')",
        }}
      />,
    );

    expect(screen.getByText("python")).toBeInTheDocument();
    expect(screen.getByText("print('hello')")).toBeInTheDocument();
  });

  it("renders report artifact", () => {
    render(
      <ArtifactCard
        artifact={{
          type: "report",
          title: "Executive Summary",
          content: "## Result\nGrowth up by 12%",
        }}
      />,
    );

    expect(screen.getByText("Executive Summary")).toBeInTheDocument();
    expect(screen.getByText("Result")).toBeInTheDocument();
  });
});
