import { describe, it, expect, vi } from 'vitest';
import React from 'react';
import { render, screen } from '@testing-library/react';
import { AllocationChart } from '@/components/AllocationChart';
import { ThemeProvider } from '@/components/ThemeProvider';

describe('AllocationChart Component (Task 5: Interactive Donut Hover)', () => {
  const mockAllocation = {
    AAPL: 15000,
    MSFT: 10000,
    NVDA: 5000,
  };

  it('renders center summary and hides bottom legend when showLegend is false', () => {
    render(
      <ThemeProvider>
        <AllocationChart
          allocation={mockAllocation}
          centerLabel="Portfolio Value"
          centerValue="$30,000"
          currency="USD"
          showLegend={false}
        />
      </ThemeProvider>
    );

    // Center text is present
    expect(screen.getByText('Portfolio Value')).toBeInTheDocument();
    expect(screen.getByText('$30,000')).toBeInTheDocument();

    // Legend list is not rendered
    expect(screen.queryByText('50.0%')).not.toBeInTheDocument();
  });

  it('renders bottom legend when showLegend is true', () => {
    render(
      <ThemeProvider>
        <AllocationChart
          allocation={mockAllocation}
          centerLabel="Portfolio Value"
          centerValue="$30,000"
          currency="USD"
          showLegend={true}
        />
      </ThemeProvider>
    );

    // Legend items should be rendered
    expect(screen.getByText('AAPL')).toBeInTheDocument();
    expect(screen.getByText('MSFT')).toBeInTheDocument();
    expect(screen.getByText('NVDA')).toBeInTheDocument();
    expect(screen.getByText('50.0%')).toBeInTheDocument();
    expect(screen.getByText('33.3%')).toBeInTheDocument();
    expect(screen.getByText('16.7%')).toBeInTheDocument();
  });
});
