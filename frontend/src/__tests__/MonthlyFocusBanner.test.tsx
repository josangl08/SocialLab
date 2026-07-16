import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import { MonthlyFocusBanner } from '../components/planner/MonthlyFocusBanner';
import { useAuth } from '../context/AuthContext';

// Mock useAuth
vi.mock('../context/AuthContext', () => ({
  useAuth: vi.fn(),
}));

describe('MonthlyFocusBanner Component', () => {
  const mockToken = 'mock-token-xyz';
  const mockCampaign = {
    id: 'campaign-123',
    account_id: 12,
    month_date: '2026-07-01',
    strategy_mode: 'commercial_campaign',
    title: 'Campaña de Verano',
    description: 'Foco en rebajas y nuevos lanzamientos',
    milestones: [],
    weekly_focus: {
      '1': 'Intro a la colección',
      '2': 'Ofertas especiales',
      '3': 'Último llamado',
      '4': 'Cierre de campaña'
    }
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (useAuth as any).mockReturnValue({ token: mockToken });
  });

  test('renders nothing when there is no campaign config', async () => {
    // Mock GET /api/agent/campaign returning null/None
    (global.fetch as any).mockImplementation(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve(null),
      })
    );

    const { container } = render(
      <MonthlyFocusBanner accountId={12} currentDate={new Date('2026-07-15')} />
    );

    // Wait a bit to verify it remains empty
    await new Promise(r => setTimeout(r, 50));
    expect(container.firstChild).toBeNull();
  });

  test('renders title, description and all four weekly focuses, highlighting the current week', async () => {
    // Mock GET /api/agent/campaign returning campaign data
    (global.fetch as any).mockImplementation(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve(mockCampaign),
      })
    );

    // currentDate is 2026-07-10 (Day 10 -> Week 2)
    render(
      <MonthlyFocusBanner accountId={12} currentDate={new Date('2026-07-10')} />
    );

    await waitFor(() => {
      expect(screen.getByText('Campaña de Verano')).toBeInTheDocument();
    });

    expect(screen.getByText('Foco en rebajas y nuevos lanzamientos')).toBeInTheDocument();
    expect(screen.getByText('💼 Comercial')).toBeInTheDocument();

    // All four weeks are visible, not just the current one
    expect(screen.getByText('Intro a la colección')).toBeInTheDocument();
    expect(screen.getByText('Ofertas especiales')).toBeInTheDocument();
    expect(screen.getByText('Último llamado')).toBeInTheDocument();
    expect(screen.getByText('Cierre de campaña')).toBeInTheDocument();

    // Only the current week (2) is marked active
    expect(screen.getByText('Foco Semana 2').closest('.banner-week-chip')).toHaveClass('active');
    expect(screen.getByText('Foco Semana 1').closest('.banner-week-chip')).not.toHaveClass('active');
    expect(screen.getByText('Foco Semana 4').closest('.banner-week-chip')).not.toHaveClass('active');
  });

  test('highlights week 4 as active when currentDate falls in week 4', async () => {
    (global.fetch as any).mockImplementation(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve(mockCampaign),
      })
    );

    // currentDate is 2026-07-28 (Day 28 -> Week 4)
    render(
      <MonthlyFocusBanner accountId={12} currentDate={new Date('2026-07-28')} />
    );

    await waitFor(() => {
      expect(screen.getByText('Cierre de campaña')).toBeInTheDocument();
    });

    expect(screen.getByText('Foco Semana 4').closest('.banner-week-chip')).toHaveClass('active');
    expect(screen.getByText('Foco Semana 2').closest('.banner-week-chip')).not.toHaveClass('active');
  });
});
