import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, test, expect, vi, beforeEach, afterEach } from 'vitest';
import { MonthlyCampaignPanel } from '../components/planner/MonthlyCampaignPanel';
import { mockFetch, type RecordedCall } from './helpers/mockFetch';

vi.mock('../features/agent/CampaignChatBox', () => ({
  CampaignChatBox: ({ campaignId }: { campaignId: string }) => <div data-testid="chat">chat {campaignId}</div>,
}));

const PENDING = {
  id: 'c1', account_id: 7, month_date: '2026-11-01', strategy_mode: 'commercial_campaign',
  title: 'Black Friday', description: 'Ofertas', milestones: [], weekly_focus: { '1': 'Teaser' },
  status: 'pending_approval', generated_by: 'hermes',
};

const DATE = new Date('2026-11-10T12:00:00');
let calls: RecordedCall[];

describe('MonthlyCampaignPanel', () => {
  afterEach(() => vi.useRealTimers());

  describe('with a pending draft', () => {
    beforeEach(() => {
      calls = mockFetch([
        { url: '/api/agent/campaign?account_id=7&month_date=2026-11-01', response: PENDING },
        { method: 'POST', url: '/api/agent/campaign/c1/approve', response: { status: 'approved' } },
        { method: 'POST', url: /\/api\/agent\/campaign$/, response: (body: unknown) => body },
      ]);
    });

    test('approves the draft from the planner', async () => {
      const onChanged = vi.fn();
      render(<MonthlyCampaignPanel accountId={7} currentDate={DATE} onCampaignChanged={onChanged} />);
      expect(await screen.findByTestId('campaign-pending')).toBeInTheDocument();
      fireEvent.click(screen.getByRole('button', { name: /Aprobar/ }));
      await waitFor(() => expect(onChanged).toHaveBeenCalled());
      expect(screen.queryByTestId('campaign-pending')).not.toBeInTheDocument();
    });

    test('edits and saves without creating a duplicate', async () => {
      render(<MonthlyCampaignPanel accountId={7} currentDate={DATE} onCampaignChanged={vi.fn()} />);
      fireEvent.click(await screen.findByRole('button', { name: /Editar campaña del mes/ }));
      expect(screen.getByLabelText('Título')).toHaveValue('Black Friday');
      fireEvent.change(screen.getByLabelText('Foco semana 2'), { target: { value: 'Lanzamiento' } });
      fireEvent.click(screen.getByRole('button', { name: 'Guardar campaña' }));
      await waitFor(() => expect(calls.some(c => c.method === 'POST' && c.url.endsWith('/api/agent/campaign'))).toBe(true));
      const body = calls.find(c => c.method === 'POST' && c.url.endsWith('/api/agent/campaign'))!.body as Record<string, unknown>;
      expect(body).toMatchObject({ id: 'c1', weekly_focus: { '1': 'Teaser', '2': 'Lanzamiento' } });
    });

    test('opens the Hermes chat', async () => {
      render(<MonthlyCampaignPanel accountId={7} currentDate={DATE} onCampaignChanged={vi.fn()} />);
      fireEvent.click(await screen.findByRole('button', { name: /Chat con Hermes/ }));
      expect(screen.getByTestId('chat')).toHaveTextContent('chat c1');
    });
  });

  test('without campaign offers to generate it and reports a timeout', async () => {
    calls = mockFetch([
      { url: '/api/agent/campaign?account_id=7', response: null },
      { method: 'POST', url: '/api/agent/campaign/trigger', response: { triggered: true } },
    ]);
    render(<MonthlyCampaignPanel accountId={7} currentDate={DATE} onCampaignChanged={vi.fn()} />);
    const generate = await screen.findByRole('button', { name: /Generar con Hermes/ });

    vi.useFakeTimers();
    await act(async () => { fireEvent.click(generate); });
    expect(calls.find(c => c.url.includes('/trigger'))!.body).toEqual({ account_id: 7, month_date: '2026-11-01' });
    await act(async () => { vi.advanceTimersByTime(46000); });
    expect(screen.getByText(/Hermes no respondió a tiempo/)).toBeInTheDocument();
  });
});
