import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import { StrategyPublishingTab } from '../components/strategy/StrategyPublishingTab';
import { DEFAULT_CONFIG } from '../components/strategy/strategyOptions';
import type { AgentStrategyConfig } from '../types';
import { mockFetch, type RecordedCall } from './helpers/mockFetch';

const DRAFT: AgentStrategyConfig = { ...DEFAULT_CONFIG, best_times: ['10:00'] };

const SUGGESTION = {
  id: 31, decision_type: 'suggest_schedule_change', status: 'suggested', created_at: '2026-10-20',
  rationale: 'Tu histórico rinde de noche', tool_args: { suggested_best_times: ['21:00'] },
};

let calls: RecordedCall[];

beforeEach(() => {
  calls = mockFetch([
    { url: '/api/agent/decisions?account_id=7', response: { data: [SUGGESTION] } },
    { method: 'POST', url: '/decisions/31/accept-suggestion', response: { accepted: true, config_column: 'best_times', applied_value: ['21:00'] } },
    { method: 'POST', url: '/decisions/31/dismiss-suggestion', response: { dismissed: true } },
  ]);
});

const renderTab = (draft = DRAFT, onChange = vi.fn(), onAccepted = vi.fn()) => {
  render(<StrategyPublishingTab accountId={7} draft={draft} onChange={onChange} onSuggestionAccepted={onAccepted} />);
  return { onChange, onAccepted };
};

describe('StrategyPublishingTab', () => {
  test('shows the agent hashtag ranges (1–2 / 3–4 / 5)', () => {
    renderTab();
    expect(screen.getByText('1–2')).toBeInTheDocument();
    expect(screen.getByText('3–4')).toBeInTheDocument();
    expect(screen.getByText('5')).toBeInTheDocument();
  });

  test('"Usar mis datos" empties best_times', () => {
    const { onChange } = renderTab();
    expect(screen.getByText('10:00')).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText(/Usar mis datos/));
    expect(onChange).toHaveBeenCalledWith({ best_times: [] });
  });

  test('with empty best_times the switch is on and times are hidden', () => {
    renderTab({ ...DRAFT, best_times: [] });
    expect(screen.getByLabelText(/Usar mis datos/)).toBeChecked();
    expect(screen.queryByText('Sugerir con IA')).not.toBeInTheDocument();
  });

  test('accepting a pending suggestion writes the value and removes it', async () => {
    const { onAccepted } = renderTab();
    expect(await screen.findByText('Tu histórico rinde de noche')).toBeInTheDocument();
    expect(screen.getByText('21:00')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Aceptar/ }));
    await waitFor(() => expect(onAccepted).toHaveBeenCalledWith('best_times', ['21:00']));
    expect(screen.queryByTestId('pending-suggestion')).not.toBeInTheDocument();
  });

  test('dismissing a suggestion does not touch the config', async () => {
    const { onAccepted } = renderTab();
    fireEvent.click(await screen.findByRole('button', { name: 'Descartar' }));
    await waitFor(() => expect(screen.queryByTestId('pending-suggestion')).not.toBeInTheDocument());
    expect(calls.some(c => c.url.includes('/dismiss-suggestion'))).toBe(true);
    expect(onAccepted).not.toHaveBeenCalled();
  });
});
