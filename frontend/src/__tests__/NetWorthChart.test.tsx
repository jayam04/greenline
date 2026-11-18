import { describe, it, expect } from "vitest";
import React from "react";
import { render, screen } from "@testing-library/react";
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
});
