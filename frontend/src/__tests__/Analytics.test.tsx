import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, test, expect, vi } from 'vitest';
import KPIStrip from '../components/analytics/cards/KPIStrip';
import AnalyticsPostDetailModal from '../components/analytics/panels/AnalyticsPostDetailModal';
import DemographicsChart from '../components/analytics/charts/DemographicsChart';

// Mock Recharts to prevent jsdom layout issues
vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: any) => <div data-testid="responsive-container">{children}</div>,
  LineChart: ({ children }: any) => <div data-testid="line-chart">{children}</div>,
  Line: () => <div />,
  BarChart: ({ children }: any) => <div data-testid="bar-chart">{children}</div>,
  Bar: () => <div />,
  XAxis: () => <div />,
  YAxis: () => <div />,
  CartesianGrid: () => <div />,
  Tooltip: () => <div />,
  Legend: () => <div />,
  RadarChart: ({ children }: any) => <div data-testid="radar-chart">{children}</div>,
  Radar: () => <div />,
  PolarGrid: () => <div />,
  PolarAngleAxis: () => <div />,
  PolarRadiusAxis: () => <div />
}));

describe('KPIStrip Component', () => {
  test('renders 6 KPI cards correctly', () => {
    const mockCards = [
      { title: 'Seguidores', value: '1.2K', icon: 'people' },
      { title: 'Alcance', value: '8.5K', icon: 'graph-up' },
      { title: 'Visualizaciones', value: '12K', icon: 'eye' },
      { title: 'Engagement', value: '3.5%', icon: 'activity' },
      { title: 'Interacciones', value: '150', icon: 'heart' },
      { title: 'Guardados', value: '45', icon: 'bookmark' },
    ];

    render(<KPIStrip cards={mockCards} />);

    expect(screen.getByText('Seguidores')).toBeInTheDocument();
    expect(screen.getByText('Alcance')).toBeInTheDocument();
    expect(screen.getByText('Visualizaciones')).toBeInTheDocument();
    expect(screen.getByText('Engagement')).toBeInTheDocument();
    expect(screen.getByText('Interacciones')).toBeInTheDocument();
    expect(screen.getByText('Guardados')).toBeInTheDocument();

    expect(screen.getByText('1.2K')).toBeInTheDocument();
    expect(screen.getByText('8.5K')).toBeInTheDocument();
    expect(screen.getByText('12K')).toBeInTheDocument();
    expect(screen.getByText('3.5%')).toBeInTheDocument();
    expect(screen.getByText('150')).toBeInTheDocument();
    expect(screen.getByText('45')).toBeInTheDocument();
  });
});

describe('AnalyticsPostDetailModal Component', () => {
  test('does not render when closed', () => {
    const { container } = render(
      <AnalyticsPostDetailModal isOpen={false} onClose={vi.fn()} post={null} />
    );
    expect(container.firstChild).toBeNull();
  });

  test('renders post details, metrics, and radar chart when open', () => {
    const mockPost = {
      id: 'post-123',
      caption: 'Un caption increíble de prueba #insta',
      media_url: 'https://images.unsplash.com/photo-1531482615713-2afd69097998',
      permalink: 'https://instagram.com/p/post-123',
      post_type: 'reel',
      likes: 120,
      comments: 34,
      saved: 12,
      views: 1200,
      avg_watch_time_ms: 8500,
      total_watch_time_ms: 102000
    };

    const handleClose = vi.fn();

    render(
      <AnalyticsPostDetailModal isOpen={true} onClose={handleClose} post={mockPost} />
    );

    // Verify caption and numerical metrics
    expect(screen.getByText('Un caption increíble de prueba #insta')).toBeInTheDocument();
    expect(screen.getByText('120')).toBeInTheDocument();
    expect(screen.getByText('34')).toBeInTheDocument();
    expect(screen.getByText('12')).toBeInTheDocument();
    expect(screen.getByText('1200')).toBeInTheDocument();

    // Verify Reel watch times are formatted
    expect(screen.getByText('8.5s')).toBeInTheDocument();
    expect(screen.getByText('1m 42s')).toBeInTheDocument();

    // Verify radar chart container exists
    expect(screen.getByTestId('radar-chart')).toBeInTheDocument();

    // Verify close button behaves correctly
    const closeButton = screen.getByRole('button', { name: /close/i });
    fireEvent.click(closeButton);
    expect(handleClose).toHaveBeenCalledTimes(1);
  });
});

describe('DemographicsChart Toggle', () => {
  test('renders empty state correctly if no data', () => {
    render(<DemographicsChart data={null} />);
    expect(screen.getByText('No hay datos demográficos disponibles')).toBeInTheDocument();
  });
});
