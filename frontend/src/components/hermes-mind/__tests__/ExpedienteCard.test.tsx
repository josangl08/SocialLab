import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, test, expect, vi } from 'vitest';
import { ExpedienteCard } from '../expedientes/ExpedienteCard';
import type { DecisionSummary, Source } from '../shared/types';

const decision: DecisionSummary = {
  id: 7,
  decision_type: 'supabase_create_post',
  confidence_score: 0.87,
  applied_rule_labels: ['Tono'],
  rationale: 'Programado en el pico de engagement.',
  status: 'active',
  created_at: '2026-08-24T12:00:00Z',
  target_label: 'Story · 2026-09-11',
  campaign_label: 'Deporte en Foco',
  related_post_id: 44182,
  media_url: 'https://x/img.jpg',
  post_type: 'story',
};

const sources: Source[] = [
  { key: 'strategy', label: 'Estrategia', kind: 'strategy', count: 0 },
  { key: 'rule:Tono', label: 'Tono', kind: 'rule', count: 0 },
];

describe('ExpedienteCard', () => {
  test('shows verb, rationale, meta and the post image', () => {
    render(<ExpedienteCard decision={decision} sources={sources} token={null} selected={false} onSelect={() => {}} />);
    expect(screen.getByText('Creó un post')).toBeInTheDocument();
    expect(screen.getByText('Programado en el pico de engagement.')).toBeInTheDocument();
    expect(screen.getByText(/Story · 2026-09-11/)).toBeInTheDocument();
    expect(screen.getByRole('img')).toHaveAttribute('src', 'https://x/img.jpg');
  });

  test('collapsed when selected: hint shown, rationale hidden', () => {
    render(<ExpedienteCard decision={decision} sources={sources} token={null} selected onSelect={() => {}} />);
    expect(screen.getByText(/Detalle en la Órbita/)).toBeInTheDocument();
    expect(screen.queryByText('Programado en el pico de engagement.')).not.toBeInTheDocument();
  });

  test('clicking the card selects it', () => {
    const onSelect = vi.fn();
    render(<ExpedienteCard decision={decision} sources={sources} token={null} selected={false} onSelect={onSelect} />);
    fireEvent.click(screen.getByRole('button'));
    expect(onSelect).toHaveBeenCalledWith(7);
  });
});
