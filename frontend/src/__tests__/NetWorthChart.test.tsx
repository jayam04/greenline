import { describe, it, expect } from "vitest";
import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { NetWorthChart, SnapshotData } from "@/components/NetWorthChart";

describe("NetWorthChart Dynamic Bounds", () => {
  it("calculates realistic lower bound (0) and upper bound (6k) for net worth between 3k and 5k", () => {
    const mockData: SnapshotData[] = [
      { snapshot_date: "2026-01-01", net_worth: 3000 },
      { snapshot_date: "2026-02-01", net_worth: 3800 },
      { snapshot_date: "2026-03-01", net_worth: 4500 },
      { snapshot_date: "2026-04-01", net_worth: 5000 },
    ];

    const { container } = render(
      <NetWorthChart data={mockData} />
    );

    // Ticks should include €0 and €6k (or bounded by 0 and 6k)
    // Ticks should definitely NOT include -35k or +35k
    expect(screen.queryByText(/€-35k|-35k/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/€35k|\+35k/i)).not.toBeInTheDocument();
    expect(screen.getByText(/€0/i)).toBeInTheDocument();
    expect(screen.getByText(/€6k/i)).toBeInTheDocument();
  });

  it("filters strictly to current year (YTD) when snapshots span multiple years", () => {
    const multiYearData: SnapshotData[] = [
      { snapshot_date: "2024-06-01", net_worth: 1000 },
      { snapshot_date: "2025-06-01", net_worth: 2000 },
      { snapshot_date: "2026-01-01", net_worth: 3000 },
      { snapshot_date: "2026-06-01", net_worth: 3500 },
      { snapshot_date: "2026-11-17", net_worth: 4000 },
    ];

    const { rerender } = render(<NetWorthChart data={multiYearData} />);

    // Default range is YTD: starting label on X-axis must be from 2026, NOT 2024
    expect(screen.getByText(/1 Jan 2026/i)).toBeInTheDocument();
    expect(screen.queryByText(/2024/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/2025/i)).not.toBeInTheDocument();

    // Clicking 'Max' button reveals the full dataset starting back in 2024
    const maxBtn = screen.getByRole("tab", { name: "Max" });
    fireEvent.click(maxBtn);
    expect(screen.getByText(/1 Jun 2024/i)).toBeInTheDocument();
  });
});
