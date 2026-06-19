import { fireEvent, render, screen } from "@testing-library/react";
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

  it("renders platform query results with provenance and action confirmation", () => {
    const onConfirm = vi.fn();
    render(
      <ArtifactCard
        artifact={{
          type: "platform_query_result",
          summary: "Control plane resolved 1 resource surface.",
          query: "platform status",
          plan: { query: "platform status", resource_keys: ["runs"], filters: {}, limit: 20 },
          sections: [
            {
              resource_key: "runs",
              label: "Workflow Runs",
              status: "ok",
              message: null,
              columns: ["flow_key", "status"],
              records: [{ flow_key: "Revenue", status: "RUNNING" }],
              metrics: { runs: 1 },
              links: [{ label: "Runs", href: "/runs" }],
              relationships: [
                {
                  source: { resource_key: "artifacts", entity_id: "a1", label: "dataset:a1", href: "/reports" },
                  target: { resource_key: "artifacts", entity_id: "a2", label: "model:a2", href: "/reports" },
                  relationship_type: "parent_of",
                },
              ],
              provenance: {
                resource_key: "runs",
                resolver: "runs",
                generated_at: "2026-06-04T10:00:00Z",
                filters: {},
                redactions: [],
              },
            },
          ],
          action_plan: {
            action_name: "runs.cancel",
            resource_key: "runs",
            risk_level: "medium",
            confirmation_required: true,
            allowed: true,
            summary: "Cancel run r1.",
            arguments: { run_id: "r1" },
            missing_arguments: [],
            denial_reason: null,
          },
        }}
        onPlatformActionConfirm={onConfirm}
      />,
    );

    expect(screen.getByText("Platform Query")).toBeInTheDocument();
    expect(screen.getByText("Workflow Runs")).toBeInTheDocument();
    expect(screen.getByText("Revenue")).toBeInTheDocument();
    expect(screen.getByText("Relationships")).toBeInTheDocument();
    expect(screen.getByText("parent_of")).toBeInTheDocument();
    expect(screen.getByText(/runs at 2026-06-04/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /confirm action/i }));
    expect(onConfirm).toHaveBeenCalledWith(expect.objectContaining({ action_name: "runs.cancel" }));
  });
});
