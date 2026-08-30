import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import { OrbitaPanel } from '../orbita/OrbitaPanel';
import type { DecisionSummary } from '../shared/types';

vi.mock('../../../api/client', () => ({
  apiClient: { get: vi.fn(), post: vi.fn(), getUrl: (p: string) => `http://api${p}` },
}));
import { apiClient } from '../../../api/client';

// jsdom has no ResizeObserver
class RO {
  observe() {}
  unobserve() {}
  disconnect() {}
}
(globalThis as unknown as { ResizeObserver: typeof RO }).ResizeObserver = RO;

const decision: DecisionSummary = {
  id: 3,
  decision_type: 'supabase_create_post',
  confidence_score: 0.78,
  applied_rule_labels: ['Tono', 'Formato'],
  rationale: 'Post de mayor recorrido narrativo.',
  status: 'active',
  created_at: '2026-08-24T12:00:00Z',
  target_label: 'Post · 2026-09-07',
  campaign_label: 'Deporte en Foco',
  related_post_id: 44184,
};

beforeEach(() => {
  vi.mocked(apiClient.get).mockResolvedValue({
    decision: { ...decision, applied_rule_ids: [5] },
    applied_rules: [{ id: 5, rule_type: 'format', rule_text: 'Captions largas', conflicts_with_id: 4, source_correction_id: 9 }],
    post: { id: 44184, post_type: 'post', scheduled_at: null, content: 'Hay rutas…', media_url: 'https://x/p.jpg', status: 'draft', drive_file_id: null },
    proposal: null,
  } as never);
  vi.mocked(apiClient.post).mockResolvedValue({} as never);
});

describe('OrbitaPanel', () => {
  test('empty state without a decision', () => {
    render(<OrbitaPanel decision={null} token={null} onChanged={() => {}} />);
    expect(screen.getByText(/Selecciona una decisión/)).toBeInTheDocument();
  });

  test('shows the verb, rationale and the post preview image', async () => {
    render(<OrbitaPanel decision={decision} token={null} onChanged={() => {}} />);
    expect(screen.getByText('Creó un post')).toBeInTheDocument();
    expect(screen.getByText('Post de mayor recorrido narrativo.')).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole('img')).toHaveAttribute('src', 'https://x/p.jpg'));
  });

  test('"Corregir" reveals a textarea and posts the override', async () => {
    render(<OrbitaPanel decision={decision} token={null} onChanged={() => {}} />);
    fireEvent.click(screen.getByText(/Corregir esta decisión/));
    const box = await screen.findByPlaceholderText(/Explica qué debería cambiar/);
    fireEvent.change(box, { target: { value: 'menos formal' } });
    fireEvent.click(screen.getByText('Registrar corrección'));
    await waitFor(() =>
      expect(apiClient.post).toHaveBeenCalledWith('/api/agent/decisions/3/override', { user_message: 'menos formal' }),
    );
  });
});
