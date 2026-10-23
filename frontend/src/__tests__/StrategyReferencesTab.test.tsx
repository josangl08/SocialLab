import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import { StrategyReferencesTab } from '../components/strategy/StrategyReferencesTab';
import { DEFAULT_CONFIG } from '../components/strategy/strategyOptions';
import type { AgentStrategyConfig } from '../types';
import { mockFetch, type RecordedCall } from './helpers/mockFetch';

const ANALYSIS = {
  refreshed: false,
  summary: '',
  references: [
    {
      username: 'chef_pro', status: 'ok', followers: 12500, posts_per_week: 4.5,
      format_mix: { REELS: 60, CAROUSEL_ALBUM: 20, IMAGE: 20 }, hook_formulas: ['Curiosidad'],
      top_posts: [{ caption_first_line: 'Nadie te cuenta esto', media_type: 'REELS', engagement_rate: 8.2,
                    permalink: 'https://instagram.com/p/abc' }],
    },
    { username: 'amiga', status: 'not_professional', error_message: 'x' },
  ],
};

const SUGGESTION = {
  id: 40, decision_type: 'suggest_pillars_change', status: 'suggested', created_at: '2026-10-20',
  rationale: 'Tus referentes hablan de fermentación',
  tool_args: { source: 'reference_accounts', suggested_content_pillars: ['recetas', 'fermentación'] },
};

let calls: RecordedCall[];

beforeEach(() => {
  calls = mockFetch([
    { url: '/api/agent/reference-accounts/7', response: ANALYSIS },
    { url: '/api/agent/decisions?account_id=7', response: { data: [SUGGESTION] } },
  ]);
});

const DRAFT: AgentStrategyConfig = { ...DEFAULT_CONFIG, reference_accounts: ['chef_pro', 'amiga'] };

const renderTab = (draft = DRAFT, onChange = vi.fn()) => {
  render(
    <StrategyReferencesTab accountId={7} draft={draft} savedReferences={['chef_pro', 'amiga']}
      onChange={onChange} onSuggestionAccepted={vi.fn()} />
  );
  return onChange;
};

describe('StrategyReferencesTab', () => {
  test('shows the analysis of each reference with links', async () => {
    renderTab();
    expect(await screen.findByText('12.500 seguidores')).toBeInTheDocument();
    expect(screen.getByText('4.5 posts/semana')).toBeInTheDocument();
    expect(screen.getByText('Reels 60% · Carruseles 20% · Fotos 20%')).toBeInTheDocument();
    expect(screen.getByText('Curiosidad')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Nadie te cuenta esto' })).toHaveAttribute('href', 'https://instagram.com/p/abc');
  });

  test('warns about a non professional reference without hiding the rest', async () => {
    renderTab();
    expect(await screen.findByText(/No es una cuenta profesional/)).toBeInTheDocument();
    expect(screen.getByTestId('reference-chef_pro')).toBeInTheDocument();
  });

  test('"Actualizar" asks for a refresh', async () => {
    renderTab();
    fireEvent.click(await screen.findByRole('button', { name: /Actualizar/ }));
    await waitFor(() => expect(calls.some(c => c.url.includes('refresh=true'))).toBe(true));
  });

  test('shows suggestions derived from references', async () => {
    renderTab();
    expect(await screen.findByText('Tus referentes hablan de fermentación')).toBeInTheDocument();
    expect(screen.getByText('Referentes')).toBeInTheDocument();
  });

  test('does not allow more than 5 references', async () => {
    renderTab({ ...DRAFT, reference_accounts: ['a', 'b', 'c', 'd', 'e'] });
    expect(screen.getByText('5/5')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Máximo 5')).toBeDisabled();
  });
});
