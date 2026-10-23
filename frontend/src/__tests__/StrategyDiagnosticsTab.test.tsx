import { fireEvent, render, screen } from '@testing-library/react';
import { describe, test, expect, vi } from 'vitest';
import { StrategyDiagnosticsTab } from '../components/strategy/StrategyDiagnosticsTab';
import { mockFetch } from './helpers/mockFetch';

const diagnostics = (issues: unknown[]) => mockFetch([{
  url: '/api/agent/strategy/7/diagnostics',
  response: {
    issues,
    context_preview: 'Tipo de cuenta: profesional. Idioma de los captions: español.',
    profile_audit: { score: 60, items: [{ id: 'bio', label: 'Bio con CTA', passed: false, weight: 10, tip: 'Añade un CTA' }] },
  },
}]);

describe('StrategyDiagnosticsTab', () => {
  test('groups issues by severity and links to their tab', async () => {
    diagnostics([
      { code: 'FIXED_NO_DAYS', severity: 'error', field: 'preferred_days', tab: 'publicacion', message: 'Sin días elegidos.' },
      { code: 'NO_PILLARS', severity: 'warning', field: 'content_pillars', tab: 'marca', message: 'Sin pilares.' },
    ]);
    const onGoToTab = vi.fn();
    render(<StrategyDiagnosticsTab accountId={7} refreshKey={0} onGoToTab={onGoToTab} />);

    expect(await screen.findByText('Errores')).toBeInTheDocument();
    expect(screen.getByText('Avisos')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Ir a Publicación →' }));
    expect(onGoToTab).toHaveBeenCalledWith('publicacion');
  });

  test('clean strategy, Hermes context and audit', async () => {
    diagnostics([]);
    render(<StrategyDiagnosticsTab accountId={7} refreshKey={0} onGoToTab={vi.fn()} />);
    expect(await screen.findByText('No hay problemas en tu estrategia.')).toBeInTheDocument();
    expect(screen.getByTestId('context-preview')).toHaveTextContent('Tipo de cuenta: profesional.');
    expect(screen.getByText('60/100')).toBeInTheDocument();
    expect(screen.getByText(/Añade un CTA/)).toBeInTheDocument();
  });
});
