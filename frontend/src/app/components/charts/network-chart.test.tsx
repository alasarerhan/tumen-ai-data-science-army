import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { NetworkChart } from "./network-chart";

vi.mock("echarts-for-react", () => ({
  default: ({ option, style }: { option: unknown; style: React.CSSProperties }) => (
    <div
      data-testid="echarts-mock"
      data-option={JSON.stringify(option)}
      data-height={style?.height}
    />
  ),
}));

describe("NetworkChart", () => {
  it("renders with valid data", () => {
    const nodes = [{ name: "A", value: 10 }, { name: "B", value: 20 }];
    const links = [{ source: "A", target: "B", value: 5 }];
    render(<NetworkChart nodes={nodes} links={links} />);

    const chart = screen.getByTestId("echarts-mock");
    expect(chart).toBeInTheDocument();

    const option = JSON.parse(chart.getAttribute("data-option") || "{}");
    expect(option.series[0].type).toBe("graph");
    expect(option.series[0].data).toEqual(nodes);
    expect(option.series[0].links).toEqual(links);
  });

  it("renders with empty data", () => {
    render(<NetworkChart nodes={[]} links={[]} />);

    const chart = screen.getByTestId("echarts-mock");
    expect(chart).toBeInTheDocument();

    const option = JSON.parse(chart.getAttribute("data-option") || "{}");
    expect(option.series[0].data).toEqual([]);
    expect(option.series[0].links).toEqual([]);
  });

  it("uses custom height when provided", () => {
    render(<NetworkChart nodes={[]} links={[]} height={400} />);

    const chart = screen.getByTestId("echarts-mock");
    expect(chart.getAttribute("data-height")).toBe("400");
  });

  it("uses default height of 280", () => {
    render(<NetworkChart nodes={[]} links={[]} />);

    const chart = screen.getByTestId("echarts-mock");
    expect(chart.getAttribute("data-height")).toBe("280");
  });

  it("includes categories from nodes", () => {
    const nodes = [
      { name: "A", category: "type1" },
      { name: "B", category: "type2" },
    ];
    render(<NetworkChart nodes={nodes} links={[]} />);

    const chart = screen.getByTestId("echarts-mock");
    const option = JSON.parse(chart.getAttribute("data-option") || "{}");
    expect(option.series[0].categories).toEqual([{ name: "type1" }, { name: "type2" }]);
  });

  it("includes legend when categories exist", () => {
    const nodes = [{ name: "A", category: "type1" }];
    render(<NetworkChart nodes={nodes} links={[]} />);

    const chart = screen.getByTestId("echarts-mock");
    const option = JSON.parse(chart.getAttribute("data-option") || "{}");
    expect(option.legend).toBeDefined();
  });

  it("does not include legend when no categories", () => {
    const nodes = [{ name: "A" }];
    render(<NetworkChart nodes={nodes} links={[]} />);

    const chart = screen.getByTestId("echarts-mock");
    const option = JSON.parse(chart.getAttribute("data-option") || "{}");
    expect(option.legend).toBeUndefined();
  });
});
