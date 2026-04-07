import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { SankeyChart } from "./sankey-chart";

vi.mock("echarts-for-react", () => ({
  default: ({ option, style }: { option: unknown; style: React.CSSProperties }) => (
    <div
      data-testid="echarts-mock"
      data-option={JSON.stringify(option)}
      data-height={style?.height}
    />
  ),
}));

describe("SankeyChart", () => {
  it("renders with valid data", () => {
    const nodes = [{ name: "A" }, { name: "B" }];
    const links = [{ source: "A", target: "B", value: 10 }];
    render(<SankeyChart nodes={nodes} links={links} />);

    const chart = screen.getByTestId("echarts-mock");
    expect(chart).toBeInTheDocument();

    const option = JSON.parse(chart.getAttribute("data-option") || "{}");
    expect(option.series[0].type).toBe("sankey");
    expect(option.series[0].data).toEqual(nodes);
    expect(option.series[0].links).toEqual(links);
  });

  it("renders with empty data", () => {
    render(<SankeyChart nodes={[]} links={[]} />);

    const chart = screen.getByTestId("echarts-mock");
    expect(chart).toBeInTheDocument();

    const option = JSON.parse(chart.getAttribute("data-option") || "{}");
    expect(option.series[0].data).toEqual([]);
    expect(option.series[0].links).toEqual([]);
  });

  it("uses custom height when provided", () => {
    render(<SankeyChart nodes={[]} links={[]} height={400} />);

    const chart = screen.getByTestId("echarts-mock");
    expect(chart.getAttribute("data-height")).toBe("400");
  });

  it("uses default height of 280", () => {
    render(<SankeyChart nodes={[]} links={[]} />);

    const chart = screen.getByTestId("echarts-mock");
    expect(chart.getAttribute("data-height")).toBe("280");
  });

  it("includes tooltip configuration", () => {
    render(<SankeyChart nodes={[]} links={[]} />);

    const chart = screen.getByTestId("echarts-mock");
    const option = JSON.parse(chart.getAttribute("data-option") || "{}");
    expect(option.tooltip.trigger).toBe("item");
  });
});
