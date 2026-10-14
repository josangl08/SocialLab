import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import Dashboard from '../components/dashboard/Dashboard';

// Mock mutable connected state
let mockIsInstagramConnected = true;

// Mock context hook
vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({
    isInstagramConnected: mockIsInstagramConnected,
    setInstagramConnected: vi.fn(),
    isSyncing: false,
    setSyncing: vi.fn(),
    lastSync: null,
    setLastSync: vi.fn(),
    setSyncCompleted: vi.fn(),
  }),
}));

// Mock routing hook
vi.mock('react-router-dom', () => ({
  useLocation: () => ({ search: '' }),
}));

// Mock subcomponents
vi.mock('../../features/agent/AgentStatusCard', () => ({
  AgentStatusCard: ({ accountId }: { accountId: number }) => (
    <div data-testid="agent-status-card">AgentStatusCard Account: {accountId}</div>
  )
}));

vi.mock('../../features/agent/CalendarProposalView', () => ({
  CalendarProposalView: ({ accountId }: { accountId: number }) => (
    <div data-testid="calendar-proposal-view">CalendarProposalView Account: {accountId}</div>
  )
}));

// Mock Recharts
vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: any) => <div data-testid="responsive-container">{children}</div>,
  LineChart: ({ children }: any) => <div data-testid="line-chart">{children}</div>,
  Line: () => <div />
}));

describe('Dashboard Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockIsInstagramConnected = true;

    // Mock localStorage
    const store: Record<string, string> = {
      authToken: 'mock-token-xyz'
    };
    const mockLocalStorage = {
      getItem: (key: string) => store[key] || null,
      setItem: (key: string, value: string) => { store[key] = value; },
      removeItem: (key: string) => { delete store[key]; },
      clear: () => { for (const k in store) delete store[k]; }
    };
    Object.defineProperty(window, 'localStorage', {
      value: mockLocalStorage,
      writable: true
    });

    // Mock window.alert
    window.alert = vi.fn();

    // Mock fetch
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/instagram/status')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve([
            {
              id: 1,
              username: 'test_username',
              account_name: 'Test Account Name',
              profile_picture_url: 'http://example.com/pic.jpg',
              connected: true,
              expired: false
            }
          ]),
        });
      }
      if (url.includes('/api/analytics/overview')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            success: true,
            last_sync_at: '2026-06-25T20:00:00Z',
            data: {
              overview: {
                follower_count: 12000,
                profile_views: 150,
                reach: 8500,
                impressions: 20000,
                avg_interactions_per_post: 45,
                engagement_rate: 3.5,
                total_posts: 40
              },
              top_posts: [
                {
                  id: 'post1',
                  caption: 'Destacado post',
                  media_url: 'http://img/post1.png',
                  permalink: 'https://instagram.com/p/post1',
                  timestamp: '2026-06-25T00:00:00Z',
                  likes: 500,
                  comments: 20,
                  engagement: 5.2,
                  impressions: 1000
                }
              ],
              engagement_trend: [
                { date: '2026-06-19', likes: 5, comments: 2, engagement: 1.2 },
                { date: '2026-06-20', likes: 7, comments: 3, engagement: 1.5 }
              ],
              best_posting_times: [
                { hour: '18:00', avg_engagement: 4.5, posts_count: 10 }
              ],
              timezone: 'Asia/Kuching'
            }
          }),
        });
      }
      if (url.includes('/posts')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve([
            {
              id: 10,
              content: 'Scheduled Post Content',
              post_type: 'image',
              scheduled_at: '2026-06-27T18:00:00Z',
              status: 'scheduled'
            }
          ]),
        });
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({}),
      });
    });
  });

  test('renders KPI cards with correct titles when connected', async () => {
    render(<Dashboard />);

    // Wait for loading to finish
    await waitFor(() => {
      expect(screen.queryByText('Cargando datos de Instagram...')).not.toBeInTheDocument();
    });

    // Check KPI Cards titles
    expect(screen.getByText('Seguidores')).toBeInTheDocument();
    expect(screen.getByText('Alcance')).toBeInTheDocument();
    expect(screen.getByText('Engagement')).toBeInTheDocument();
    expect(screen.getByText('Interacciones')).toBeInTheDocument();

    // Check values
    expect(screen.getByText('12.0K')).toBeInTheDocument(); // follower_count formatted
    expect(screen.getByText('8.5K')).toBeInTheDocument(); // reach formatted
    expect(screen.getByText('3.5%')).toBeInTheDocument(); // engagement_rate
    expect(screen.getByText('1.8K')).toBeInTheDocument(); // 45 * 40 = 1800 formatted
  });

  test('mejores horarios indican la zona de la cuenta, no una fija', async () => {
    render(<Dashboard />);

    await waitFor(() => {
      expect(screen.queryByText('Cargando datos de Instagram...')).not.toBeInTheDocument();
    });

    expect(screen.getByText('Hora de Kuching')).toBeInTheDocument();
    expect(screen.queryByText('España (Madrid)')).not.toBeInTheDocument();
  });

  test('profile banner shows when connected', async () => {
    render(<Dashboard />);

    await waitFor(() => {
      expect(screen.queryByText('Cargando datos de Instagram...')).not.toBeInTheDocument();
    });

    // Profile details
    expect(screen.getByText('@test_username')).toBeInTheDocument();
    expect(screen.getByText('Test Account Name')).toBeInTheDocument();
    expect(screen.getByText('Conectado')).toBeInTheDocument();
    
    // Check avatar image
    const avatarImg = screen.getByAltText('avatar') as HTMLImageElement;
    expect(avatarImg).toBeInTheDocument();
    expect(avatarImg.src).toBe('http://example.com/pic.jpg');
  });

  test('empty state shows when not connected', async () => {
    mockIsInstagramConnected = false;
    const { container } = render(<Dashboard />);

    // Wait for initial fetch loading to settle
    await waitFor(() => {
      expect(container.querySelector('.kpi-skeleton')).not.toBeInTheDocument();
    });

    // Empty state connect button and text
    expect(screen.getByText('Conectar Instagram')).toBeInTheDocument();
    expect(screen.getByText('Conecta tu cuenta para ver analytics y programar contenido')).toBeInTheDocument();
    
    // Check components requiring connection are NOT in the document
    expect(screen.queryByText('@test_username')).not.toBeInTheDocument();
    expect(screen.queryByTestId('agent-status-card')).not.toBeInTheDocument();
    expect(screen.queryByTestId('calendar-proposal-view')).not.toBeInTheDocument();
  });
});
