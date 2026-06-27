import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, test, expect, vi } from 'vitest';
import KPICard from './KPICard';

// Mock Recharts to avoid layout issues in JSDOM
vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: any) => <div data-testid="responsive-container">{children}</div>,
  LineChart: ({ children }: any) => <div data-testid="line-chart">{children}</div>,
  Line: () => <div data-testid="line-element" />
}));

describe('KPICard Component', () => {
  const defaultProps = {
    title: 'Seguidores',
    value: '10K',
    change: '+5%',
    trend: 'up' as const,
    icon: 'people',
    color: 'primary' as const,
  };

  test('renders standard props correctly', () => {
    render(<KPICard {...defaultProps} />);
    expect(screen.getByText('Seguidores')).toBeInTheDocument();
    expect(screen.getByText('10K')).toBeInTheDocument();
    expect(screen.getByText('+5%')).toBeInTheDocument();
  });

  test('renders sparkline when sparklineData is provided', () => {
    const sparklineData = [100, 120, 115, 130, 140, 150, 160];
    const { container } = render(<KPICard {...defaultProps} sparklineData={sparklineData} />);
    
    // Sparkline container should be in the DOM
    const sparklineEl = container.querySelector('.kpi-sparkline');
    expect(sparklineEl).toBeInTheDocument();
    
    // Recharts mocked elements should render
    expect(screen.getByTestId('responsive-container')).toBeInTheDocument();
    expect(screen.getByTestId('line-chart')).toBeInTheDocument();
  });

  test('does not render sparkline when sparklineData is omitted', () => {
    const { container } = render(<KPICard {...defaultProps} />);
    
    const sparklineEl = container.querySelector('.kpi-sparkline');
    expect(sparklineEl).not.toBeInTheDocument();
  });

  test('renders loading skeleton when loading is true', () => {
    const { container } = render(<KPICard {...defaultProps} loading={true} />);
    
    expect(container.querySelector('.kpi-skeleton')).toBeInTheDocument();
    expect(screen.queryByText('Seguidores')).not.toBeInTheDocument();
  });
});
