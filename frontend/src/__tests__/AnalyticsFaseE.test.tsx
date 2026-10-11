import { render, screen, fireEvent } from '@testing-library/react';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import Analytics from '../components/analytics/Analytics';
import AccountGrowthChart from '../components/analytics/charts/AccountGrowthChart';
import { apiClient } from '../api/client';

vi.mock('recharts', () => {
  const Box = ({ children }: any) => <div>{children}</div>;
  const Empty = () => <div />;
  return {
    ResponsiveContainer: Box, LineChart: Box, BarChart: ({ children }: any) => <div data-testid="bar-chart">{children}</div>,
    RadarChart: Box, Line: Empty, Bar: Empty, XAxis: Empty, YAxis: Empty, CartesianGrid: Empty,
    Tooltip: Empty, Legend: Empty, Radar: Empty, PolarGrid: Empty, PolarAngleAxis: Empty, PolarRadiusAxis: Empty,
    Cell: Empty, PieChart: Box, Pie: Empty,
  };
});

vi.mock('../api/client', () => ({
  apiClient: { get: vi.fn() },
}));

const post = (id: string, caption: string, extra: Record<string, unknown>) => ({
  id, caption, media_url: '', permalink: '', post_type: 'IMAGE', likes: 10, comments: 1, saved: 0,
  impressions: 100, reach: 100, timestamp: '2026-10-01', ...extra,
});

const response = (overview: Record<string, unknown>) => ({
  success: true,
  data: {
    overview: {
      total_posts: 2, follower_count: 1000, reach: 5000, views: 3000, total_interactions: 20,
      total_likes: 20, total_comments: 2, total_saves: 0, engagement_rate: 1,
      avg_sends_per_reach: 0.02, median_views: 1000, contact_button_taps: 42,
      strategy_mode: 'personal_storyline',
      follower_growth: { series: [{ date: '2026-10-01', follows: 120, unfollows: 30, net: 90 }], follows: 120, unfollows: 30, net: 90 },
      ...overview,
    },
    top_posts: [post('a', 'Más engagement', { outlier_multiple: null, sends_per_reach: null })],
    top_posts_by_outlier: [post('b', 'Post viral', { outlier_multiple: 5.2, sends_per_reach: 0.02 })],
    engagement_trend: [],
    best_posting_times: [],
    audience: {
      follower_growth: [], demographics: {}, engaged_demographics: {}, online_hours: {},
      top_locations: { countries: [], cities: [] },
    },
  },
});

describe('Analytics — métricas de Fase E', () => {
  beforeEach(() => {
    localStorage.setItem('authToken', 'tok');
    vi.mocked(apiClient.get).mockReset();
  });

  test('muestra Sends / Reach y oculta Toques en contacto en cuentas personales', async () => {
    vi.mocked(apiClient.get).mockResolvedValue(response({}));
    render(<Analytics />);

    expect(await screen.findByText('Sends / Reach')).toBeInTheDocument();
    expect(screen.getByText('2,0 %')).toBeInTheDocument();
    expect(screen.queryByText('Toques en contacto')).not.toBeInTheDocument();
  });

  test('muestra Toques en contacto en cuentas commercial_campaign', async () => {
    vi.mocked(apiClient.get).mockResolvedValue(response({ strategy_mode: 'commercial_campaign' }));
    render(<Analytics />);

    expect(await screen.findByText('Toques en contacto')).toBeInTheDocument();
    expect(screen.getByText('42')).toBeInTheDocument();
  });

  test('Sends / Reach sin datos se muestra como —', async () => {
    vi.mocked(apiClient.get).mockResolvedValue(response({ avg_sends_per_reach: null }));
    render(<Analytics />);
    await screen.findByText('Sends / Reach');
    expect(screen.getAllByText('—').length).toBeGreaterThan(0);
  });

  test('muestra altas, bajas y neto del periodo', async () => {
    vi.mocked(apiClient.get).mockResolvedValue(response({}));
    render(<Analytics />);
    expect(await screen.findByText('Altas y Bajas de Seguidores')).toBeInTheDocument();
    expect(screen.getByText('+90')).toBeInTheDocument();
  });

  test('ordena los posts por Outlier Multiple', async () => {
    vi.mocked(apiClient.get).mockResolvedValue(response({}));
    render(<Analytics />);
    fireEvent.click(await screen.findByText('Contenido'));

    expect(screen.getByText('Más engagement')).toBeInTheDocument();
    expect(screen.getByText('Datos insuficientes')).toBeInTheDocument();

    fireEvent.click(screen.getByText('Outlier Multiple'));
    expect(screen.getByText('Post viral')).toBeInTheDocument();
    expect(screen.getByText('5,2×')).toBeInTheDocument();
    expect(screen.queryByText('Más engagement')).not.toBeInTheDocument();
  });
});

describe('AccountGrowthChart', () => {
  test('semana con 120 altas y 30 bajas -> neto +90', () => {
    render(
      <AccountGrowthChart
        growth={{ series: [{ date: '2026-10-01', follows: 120, unfollows: 30, net: 90 }], follows: 120, unfollows: 30, net: 90 }}
      />
    );
    expect(screen.getByText('120')).toBeInTheDocument();
    expect(screen.getByText('30')).toBeInTheDocument();
    expect(screen.getByText('+90')).toBeInTheDocument();
    expect(screen.getByTestId('bar-chart')).toBeInTheDocument();
  });

  test('sin serie muestra estado vacío', () => {
    render(<AccountGrowthChart growth={null} />);
    expect(screen.getByText(/Sin datos de altas y bajas/)).toBeInTheDocument();
  });
});
