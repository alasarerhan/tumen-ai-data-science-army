import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { TrendChart } from "./trend-chart";

vi.mock("echarts-for-react", () => ({
  default: ({ option, style }: { option: unknown; style: React.CSSProperties }) => (
    <div
      data-testid="echarts-mock"
      data-option={JSON.stringify(option)}
      data-height={style?.height}
    />
  ),
}));

describe("TrendChart", () => {
  it("renders with valid data", () => {
    const series = [{ name: "Series A", data: [1, 2, 3, 4, 5] }];
    render(<TrendChart series={series} />);

    const chart = screen.getByTestId("echarts-mock");
    expect(chart).toBeInTheDocument();

    const option = JSON.parse(chart.getAttribute("data-option") || "{}");
    expect(option.series[0].type).toBe("line");
    expect(option.series[0].name).toBe("Series A");
    expect(option.series[0].data).toEqual([1, 2, 3, 4, 5]);
  });

  it("renders with multiple series", () => {
    const series = [
      { name: "Series A", data: [1, 2, 3] },
      { name: "Series B", data: [4, 5, 6] },
    ];
    render(<TrendChart series={series} />);

    const chart = screen.getByTestId("echarts-mock");
    const option = JSON.parse(chart.getAttribute("data-option") || "{}");
    expect(option.series).toHaveLength(2);
  });

  it("renders with empty series", () => {
    render(<TrendChart series={[]} />);

    const chart = screen.getByTestId("echarts-mock");
    expect(chart).toBeInTheDocument();

    const option = JSON.parse(chart.getAttribute("data-option") || "{}");
    expect(option.series).toEqual([]);
  });

  it("uses custom height when provided", () => {
    render(<TrendChart series={[]} height={400} />);

    const chart = screen.getByTestId("echarts-mock");
    expect(chart.getAttribute("data-height")).toBe("400");
  });

  it("uses default height of 260", () => {
    render(<TrendChart series={[]} />);

    const chart = screen.getByTestId("echarts-mock");
    expect(chart.getAttribute("data-height")).toBe("260");
  });

  it("uses provided categories for xAxis", () => {
    const categories = ["Jan", "Feb", "Mar"];
    const series = [{ name: "Sales", data: [100, 200, 150] }];
    render(<TrendChart categories={categories} series={series} />);

    const chart = screen.getByTestId("echarts-mock");
    const option = JSON.parse(chart.getAttribute("data-option") || "{}");
    expect(option.xAxis.data).toEqual(categories);
  });

  it("generates default categories when not provided", () => {
    const series = [{ name: "Sales", data: [100, 200, 150] }];
    render(<TrendChart series={series} />);

    const chart = screen.getByTestId("echarts-mock");
    const option = JSON.parse(chart.getAttribute("data-option") || "{}");
    expect(option.xAxis.data).toEqual(["T1", "T2", "T3"]);
  });

  it("includes tooltip configuration", () => {
    render(<TrendChart series={[]} />);

    const chart = screen.getByTestId("echarts-mock");
    const option = JSON.parse(chart.getAttribute("data-option") || "{}");
    expect(option.tooltip.trigger).toBe("axis");
  });

  it("includes legend configuration", () => {
    render(<TrendChart series={[]} />);

    const chart = screen.getByTestId("echarts-mock");
    const option = JSON.parse(chart.getAttribute("data-option") || "{}");
    expect(option.legend).toBeDefined();
  });
});
