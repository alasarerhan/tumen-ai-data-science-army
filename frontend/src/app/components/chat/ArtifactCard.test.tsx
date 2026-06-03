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

  it("sanitizes unsafe report markdown before rendering", () => {
    const { container } = render(
      <ArtifactCard
        artifact={{
          type: "report",
          title: "Unsafe Report",
          content: "Click [bad](javascript:alert(1))<script>alert('x')</script><img src=\"javascript:alert(1)\" onerror=\"alert(1)\" />",
        }}
      />,
    );

    expect(screen.getByText("Unsafe Report")).toBeInTheDocument();
    expect(container.querySelector("script")).toBeNull();
    expect(container.querySelector("a[href^='javascript']")).toBeNull();
    expect(container.querySelector("img[onerror]")).toBeNull();
  });

  it("renders table cell markup as text instead of executable html", () => {
    const { container } = render(
      <ArtifactCard
        artifact={{
          type: "table",
          columns: ["payload"],
          records: [{ payload: "<img src=x onerror=alert(1)>" }],
        }}
      />,
    );

    expect(screen.getByText("<img src=x onerror=alert(1)>")).toBeInTheDocument();
    expect(container.querySelector("img[onerror]")).toBeNull();
  });
});
