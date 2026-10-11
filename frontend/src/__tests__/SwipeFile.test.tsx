import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import { SwipeFile } from '../components/studio/SwipeFile';
import { contentApi } from '../api/content';

vi.mock('../api/content', () => ({
  contentApi: {
    getSwipeFile: vi.fn(),
  },
}));

describe('SwipeFile Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test('renders loading state initially', () => {
    (contentApi.getSwipeFile as any).mockReturnValue(new Promise(() => {}));
    render(<SwipeFile accountId={1} />);
    expect(screen.getByText('Cargando Swipe File...')).toBeInTheDocument();
  });

  test('renders empty state when no items', async () => {
    (contentApi.getSwipeFile as any).mockResolvedValue({
      items: [],
      by_formula: [],
    });

    render(<SwipeFile accountId={1} />);

    await waitFor(() => {
      expect(
        screen.getByText('No hay ganchos registrados en el Swipe File.')
      ).toBeInTheDocument();
    });
  });

  test('renders error state on API failure', async () => {
    (contentApi.getSwipeFile as any).mockRejectedValue(new Error('Network Error'));

    render(<SwipeFile accountId={1} />);

    await waitFor(() => {
      expect(screen.getByText('Network Error')).toBeInTheDocument();
    });
  });

  test('renders hooks with outlier multiple, formula, and sends/reach', async () => {
    (contentApi.getSwipeFile as any).mockResolvedValue({
      items: [
        {
          post_id: 101,
          hook_text: 'Perdí 18.000€ en un contrato con un cliente tóxico',
          formula_id: 3,
          formula_name: 'Pérdida cuantificada',
          outlier_multiple: 5.2,
          sends_per_reach: 0.042,
        },
        {
          post_id: 102,
          hook_text: '3 errores que cometes al presupuestar software',
          formula_id: 1,
          formula_name: 'Lista de errores',
          outlier_multiple: null,
          sends_per_reach: null,
        },
      ],
      by_formula: [
        {
          formula_id: 3,
          formula_name: 'Pérdida cuantificada',
          count: 4,
          avg_outlier: 3.8,
        },
      ],
    });

    render(<SwipeFile accountId={1} />);

    await waitFor(() => {
      expect(screen.getByTestId('swipe-file-panel')).toBeInTheDocument();
    });

    // Header and formula badge
    expect(screen.getByText('Swipe File')).toBeInTheDocument();
    expect(screen.getByText(/Pérdida cuantificada · 4 posts · 3.8×/)).toBeInTheDocument();

    // Hook 1: text, formula, outlier multiple, and sends per reach formatted (4.2%)
    expect(
      screen.getByText('Perdí 18.000€ en un contrato con un cliente tóxico')
    ).toBeInTheDocument();
    expect(screen.getByText('Pérdida cuantificada')).toBeInTheDocument();
    expect(screen.getByText('5.2×')).toBeInTheDocument();
    expect(screen.getByText('4.2%')).toBeInTheDocument();

    // Hook 2: null outlier -> 'Datos insuficientes', null sends/reach -> '—'
    expect(
      screen.getByText('3 errores que cometes al presupuestar software')
    ).toBeInTheDocument();
    expect(screen.getByText('Lista de errores')).toBeInTheDocument();
    expect(screen.getByText('Datos insuficientes')).toBeInTheDocument();
    expect(screen.getByText('—')).toBeInTheDocument();
  });

  test('marks Trial Reels with their 3-second skip rate', async () => {
    (contentApi.getSwipeFile as any).mockResolvedValue({
      items: [
        {
          post_id: 7,
          hook_text: 'Nadie te cuenta esto del onboarding',
          formula_id: 5,
          formula_name: 'Secreto',
          outlier_multiple: 1.4,
          sends_per_reach: 0.01,
          is_trial: true,
          reels_skip_rate: 38.5,
        },
      ],
      by_formula: [],
    });

    render(<SwipeFile accountId={1} />);

    expect(await screen.findByText(/Trial Reel · salto 3 s: 38.5%/)).toBeInTheDocument();
  });
});
