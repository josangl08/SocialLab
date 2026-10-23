import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, test, expect, vi, beforeEach } from 'vitest';
import { StrategyWizardModal } from '../components/strategy/StrategyWizardModal';
import { DEFAULT_CONFIG } from '../components/strategy/strategyOptions';
import type { AgentStrategyConfig } from '../types';
import { mockFetch, type RecordedCall } from './helpers/mockFetch';

const CURRENT: AgentStrategyConfig = {
  ...DEFAULT_CONFIG, default_tone: 'casual', content_pillars: ['recetas'], sector: 'Cocina',
};

let calls: RecordedCall[];

beforeEach(() => {
  calls = mockFetch([
    {
      method: 'POST', url: '/api/agent/generate-strategy',
      response: { default_tone: 'inspirational', content_pillars: ['recetas', 'técnica'], sector: 'Cocina', posts_per_week: 4 },
    },
  ]);
});

const renderModal = (onApply = vi.fn(), savedAnswers = { dedica: ['Gastronomía'], contenido: [], objetivo: [], referentes: [] }) => {
  render(
    <StrategyWizardModal show accountId={7} current={CURRENT} savedAnswers={savedAnswers}
      onClose={vi.fn()} onApply={onApply} onAnswersSaved={vi.fn()} />
  );
  return onApply;
};

describe('StrategyWizardModal', () => {
  test('prefills the saved answers and sends account_id', async () => {
    renderModal();
    expect(screen.getByRole('button', { name: /Gastronomía/ }).textContent).toContain('Gastronomía');
    fireEvent.click(screen.getByRole('button', { name: 'Generar propuesta' }));
    await screen.findByText('Propuesto');
    const call = calls.find(c => c.url.includes('generate-strategy'))!;
    expect(call.body).toMatchObject({ account_id: 7, dedica: ['Gastronomía'] });
  });

  test('shows a diff and applies only the checked fields', async () => {
    const onApply = renderModal();
    fireEvent.click(screen.getByRole('button', { name: 'Generar propuesta' }));
    await screen.findByText('Propuesto');

    // Solo los campos que cambian vienen marcados; el sector no cambia
    expect(screen.getByLabelText('Aplicar Tono')).toBeChecked();
    expect(screen.getByLabelText('Aplicar Pilares de contenido')).toBeChecked();
    expect(screen.getByLabelText('Aplicar Sector')).not.toBeChecked();
    expect(screen.queryByLabelText(/posts_per_week/)).not.toBeInTheDocument();

    fireEvent.click(screen.getByLabelText('Aplicar Tono'));
    fireEvent.click(screen.getByRole('button', { name: /Aplicar seleccionados/ }));
    expect(onApply).toHaveBeenCalledWith({ content_pillars: ['recetas', 'técnica'] });
  });

  test('requires at least one answer', async () => {
    renderModal(vi.fn(), { dedica: [], contenido: [], objetivo: [], referentes: [] });
    fireEvent.click(screen.getByRole('button', { name: 'Generar propuesta' }));
    await waitFor(() => expect(screen.getByText('Responde al menos una pregunta.')).toBeInTheDocument());
    expect(calls).toHaveLength(0);
  });
});
