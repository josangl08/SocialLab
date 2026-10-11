import { render, screen, fireEvent } from '@testing-library/react';
import { describe, test, expect, vi } from 'vitest';
import { HermesMind } from '../HermesMind';

vi.mock('../../../context/AuthContext', () => ({
  useAuth: () => ({ token: 'tok' }),
}));

vi.mock('../../../api/client', () => ({
  apiClient: {
    get: vi.fn((url: string) =>
      Promise.resolve(
        url.startsWith('/api/agent/decisions')
          ? { data: [], meta: { total: 0, page: 1, per_page: 50 } }
          : url.startsWith('/api/agent/proposals')
          ? []
          : { nodes: [], edges: [] }
      )
    ),
  },
}));

vi.mock('../../studio/SwipeFile', () => ({
  SwipeFile: ({ accountId }: { accountId: number }) => <div>Swipe File de la cuenta {accountId}</div>,
}));

describe('HermesMind — pestaña Swipe File', () => {
  test('cambia de Decisiones a Swipe File', async () => {
    render(<HermesMind accountId={7} />);

    expect(screen.getByRole('tab', { name: 'Decisiones' })).toHaveAttribute('aria-selected', 'true');
    expect(screen.queryByText('Swipe File de la cuenta 7')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('tab', { name: 'Swipe File' }));

    expect(await screen.findByText('Swipe File de la cuenta 7')).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Swipe File' })).toHaveAttribute('aria-selected', 'true');
  });
});
