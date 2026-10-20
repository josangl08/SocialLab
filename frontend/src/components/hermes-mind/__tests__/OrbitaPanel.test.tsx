import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import { OrbitaPanel } from '../orbita/OrbitaPanel';
import type { DecisionSummary, ContextGraphResponse } from '../shared/types';

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
  campaign_id: 'camp-1',
  related_post_id: 44184,
};

const graph: ContextGraphResponse = {
  nodes: [
    { id: 'account-7', type: 'account', data: { label: 'cuenta' } },
    {
      id: 'strategy-7',
      type: 'strategy',
      data: { tone: 'cercano y coloquial', target_audience: 'padres jóvenes', style_guide: 'sin tecnicismos' },
    },
    {
      id: 'campaign-1',
      type: 'campaign',
      data: {
        title: 'Deporte en Foco',
        description: 'Arco del mes',
        strategy_mode: 'personal_storyline',
        weekly_focus: { '1': 'Reto inicial', '2': 'En ruta', '3': 'Competición', '4': 'Reflexión' },
        milestones: [{ date: '2026-09-27', event: 'Día del Turismo' }],
        status: 'pending_approval',
      },
    },
    {
      id: 'rule-5',
      type: 'rule',
      data: { rule_type: 'format', rule_text: 'Storytelling largo', conflicts_with: { id: 4, rule_text: 'Captions cortas' } },
    },
  ],
  edges: [],
};

beforeEach(() => {
  vi.mocked(apiClient.get).mockImplementation((url: string) => {
    if (url.includes('/audit-trail')) {
      return Promise.resolve({ decision, applied_rules: [], source_corrections: [] } as never);
    }
    return Promise.resolve({
      decision: { ...decision, applied_rule_ids: [4, 5] },
      applied_rules: [
        { id: 4, rule_type: 'format', rule_text: 'Captions cortas', conflicts_with_id: null, source_correction_id: null },
        { id: 5, rule_type: 'format', rule_text: 'Storytelling largo', conflicts_with_id: 4, source_correction_id: 9 },
      ],
      post: { id: 44184, post_type: 'post', scheduled_at: null, content: 'Hay rutas…', media_url: 'https://x/p.jpg', status: 'draft', drive_file_id: null },
      proposal: null,
    } as never);
  });
  vi.mocked(apiClient.post).mockResolvedValue({} as never);
});

describe('OrbitaPanel', () => {
  test('empty state without a decision', () => {
    render(<OrbitaPanel decision={null} graph={null} token={null} onChanged={() => {}} />);
    expect(screen.getByText(/Selecciona una decisión/)).toBeInTheDocument();
  });

  test('shows the verb, rationale and the post preview image', async () => {
    render(<OrbitaPanel decision={decision} graph={graph} token={null} onChanged={() => {}} />);
    expect(screen.getByText('Creó un post')).toBeInTheDocument();
    expect(screen.getByText('Post de mayor recorrido narrativo.')).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole('img')).toHaveAttribute('src', 'https://x/p.jpg'));
  });

  test('"Corregir" reveals a textarea and posts the override', async () => {
    render(<OrbitaPanel decision={decision} graph={graph} token={null} onChanged={() => {}} />);
    fireEvent.click(screen.getByText(/Corregir esta decisión/));
    const box = await screen.findByPlaceholderText(/Explica qué debería cambiar/);
    fireEvent.change(box, { target: { value: 'menos formal' } });
    fireEvent.click(screen.getByText('Registrar corrección'));
    await waitFor(() =>
      expect(apiClient.post).toHaveBeenCalledWith('/api/agent/decisions/3/override', { user_message: 'menos formal' }),
    );
  });

  test('click on "Estrategia" shows tone and audience from the graph', async () => {
    render(<OrbitaPanel decision={decision} graph={graph} token={null} onChanged={() => {}} />);
    fireEvent.click(screen.getByRole('button', { name: /Estrategia/ }));
    expect(await screen.findByText(/cercano y coloquial/)).toBeInTheDocument();
    expect(screen.getByText(/padres jóvenes/)).toBeInTheDocument();
  });

  test('click on "Campaña" shows the weekly focus and pending badge', async () => {
    render(<OrbitaPanel decision={decision} graph={graph} token={null} onChanged={() => {}} />);
    fireEvent.click(screen.getByRole('button', { name: /Campaña/ }));
    expect(await screen.findByText(/Reto inicial/)).toBeInTheDocument();
    expect(screen.getByText('pendiente')).toBeInTheDocument();
  });

  test('two rules of the same type render one chip and name the rule in tension', async () => {
    render(<OrbitaPanel decision={decision} graph={graph} token={null} onChanged={() => {}} />);
    await waitFor(() =>
      expect(screen.getAllByRole('button', { name: /Formato/ })).toHaveLength(1),
    );
    fireEvent.click(screen.getByRole('button', { name: /Formato/ }));
    expect(await screen.findByText(/En tensión con/)).toHaveTextContent('Captions cortas');
  });
});
