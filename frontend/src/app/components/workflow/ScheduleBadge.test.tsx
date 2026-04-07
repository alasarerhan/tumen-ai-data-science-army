import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ScheduleBadge, formatNextRun, ScheduleStatusBadge } from "./ScheduleBadge";

describe("formatNextRun", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2024-01-15T12:00:00Z"));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("returns 'Not scheduled' for null", () => {
    expect(formatNextRun(null)).toBe("Not scheduled");
  });

  it("returns 'Invalid date' for invalid date string", () => {
    expect(formatNextRun("not-a-date")).toBe("Invalid date");
  });

  it("returns 'Overdue' for past dates", () => {
    expect(formatNextRun("2024-01-15T11:00:00Z")).toBe("Overdue");
  });

  it("returns 'In less than a minute' for < 60 seconds", () => {
    expect(formatNextRun("2024-01-15T12:00:30Z")).toBe("In less than a minute");
  });

  it("returns minutes for < 1 hour", () => {
    expect(formatNextRun("2024-01-15T12:30:00Z")).toBe("In 30 minutes");
  });

  it("returns singular minute", () => {
    expect(formatNextRun("2024-01-15T12:01:00Z")).toBe("In 1 minute");
  });

  it("returns hours for < 24 hours", () => {
    expect(formatNextRun("2024-01-15T15:00:00Z")).toBe("In 3 hours");
  });

  it("returns singular hour", () => {
    expect(formatNextRun("2024-01-15T13:00:00Z")).toBe("In 1 hour");
  });

  it("returns days for >= 24 hours", () => {
    expect(formatNextRun("2024-01-17T12:00:00Z")).toBe("In 2 days");
  });

  it("returns singular day", () => {
    expect(formatNextRun("2024-01-16T12:00:00Z")).toBe("In 1 day");
  });
});

describe("ScheduleBadge", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2024-01-15T12:00:00Z"));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders cron expression", () => {
    render(<ScheduleBadge cron="0 0 * * *" enabled={true} nextRunAt="2024-01-16T00:00:00Z" />);
    expect(screen.getByText("0 0 * * *")).toBeInTheDocument();
  });

  it("shows 'Active' badge when enabled", () => {
    render(<ScheduleBadge cron="0 0 * * *" enabled={true} nextRunAt="2024-01-16T00:00:00Z" />);
    expect(screen.getByText("Active")).toBeInTheDocument();
  });

  it("shows 'Paused' badge when disabled", () => {
    render(<ScheduleBadge cron="0 0 * * *" enabled={false} nextRunAt={null} />);
    expect(screen.getByText("Paused")).toBeInTheDocument();
  });

  it("shows next run time when enabled", () => {
    render(<ScheduleBadge cron="0 0 * * *" enabled={true} nextRunAt="2024-01-16T00:00:00Z" />);
    expect(screen.getByText(/Next run:/)).toBeInTheDocument();
  });

  it("hides next run time when disabled", () => {
    render(<ScheduleBadge cron="0 0 * * *" enabled={false} nextRunAt="2024-01-16T00:00:00Z" />);
    expect(screen.queryByText(/Next run:/)).not.toBeInTheDocument();
  });

  it("renders toggle button when onToggle provided", () => {
    const onToggle = vi.fn();
    render(<ScheduleBadge cron="0 0 * * *" enabled={true} nextRunAt="2024-01-16T00:00:00Z" onToggle={onToggle} />);
    expect(screen.getByText("Pause Schedule")).toBeInTheDocument();
  });

  it("does not render toggle button when onToggle not provided", () => {
    render(<ScheduleBadge cron="0 0 * * *" enabled={true} nextRunAt="2024-01-16T00:00:00Z" />);
    expect(screen.queryByText("Pause Schedule")).not.toBeInTheDocument();
  });

  it("calls onToggle when button clicked", () => {
    const onToggle = vi.fn();
    render(<ScheduleBadge cron="0 0 * * *" enabled={true} nextRunAt="2024-01-16T00:00:00Z" onToggle={onToggle} />);
    fireEvent.click(screen.getByText("Pause Schedule"));
    expect(onToggle).toHaveBeenCalledTimes(1);
  });

  it("shows 'Resume Schedule' when paused", () => {
    const onToggle = vi.fn();
    render(<ScheduleBadge cron="0 0 * * *" enabled={false} nextRunAt={null} onToggle={onToggle} />);
    expect(screen.getByText("Resume Schedule")).toBeInTheDocument();
  });

  it("renders compact mode correctly when enabled", () => {
    render(<ScheduleBadge cron="0 0 * * *" enabled={true} nextRunAt="2024-01-16T00:00:00Z" compact={true} />);
    expect(screen.getByText("In 12 hours")).toBeInTheDocument();
  });

  it("renders compact mode correctly when paused", () => {
    render(<ScheduleBadge cron="0 0 * * *" enabled={false} nextRunAt={null} compact={true} />);
    expect(screen.getByText("Paused")).toBeInTheDocument();
  });
});

describe("ScheduleStatusBadge", () => {
  it("shows 'Not scheduled' when hasSchedule is false", () => {
    render(<ScheduleStatusBadge hasSchedule={false} enabled={false} />);
    expect(screen.getByText("Not scheduled")).toBeInTheDocument();
  });

  it("shows 'Scheduled' when hasSchedule and enabled", () => {
    render(<ScheduleStatusBadge hasSchedule={true} enabled={true} />);
    expect(screen.getByText("Scheduled")).toBeInTheDocument();
  });

  it("shows 'Paused' when hasSchedule but not enabled", () => {
    render(<ScheduleStatusBadge hasSchedule={true} enabled={false} />);
    expect(screen.getByText("Paused")).toBeInTheDocument();
  });
});
