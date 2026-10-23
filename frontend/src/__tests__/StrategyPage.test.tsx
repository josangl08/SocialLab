import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { describe, test, expect, beforeEach } from 'vitest';
import StrategyPage from '../components/strategy/StrategyPage';
import { mockFetch, type RecordedCall } from './helpers/mockFetch';

const CONFIG = {
  account_type: 'personal', sector: 'Cocina', purpose: 'Inspirar', target_audience: 'Cocineros',
  style_guide: '', default_tone: 'casual', default_language: 'es', best_times: ['20:00'],
  content_pillars: ['recetas'], hashtag_strategy: 'moderate', caption_voice: null, reference_accounts: [],
  posts_per_week: 3, scheduling_mode: 'flexible', preferred_days: [],
  content_type_mix: { post: 1, reel: 1, carousel: 1, story: 0 }, humanizer_enabled: true, banned_phrases: [],
  strategy_wizard_answers: null,
};

const ACCOUNTS = [{ id: 7, username: 'chef' }, { id: 9, username: 'viajes' }];

function LocationProbe() {
  const loc = useLocation();
  return <span data-testid="location">{loc.pathname}{loc.search}</span>;
}

const renderAt = (url: string) => render(
  <MemoryRouter initialEntries={[url]}>
    <Routes>
      <Route path="/strategy" element={<><StrategyPage /><LocationProbe /></>} />
      <Route path="/planner" element={<LocationProbe />} />
    </Routes>
  </MemoryRouter>
);

let calls: RecordedCall[];

beforeEach(() => {
  calls = mockFetch([
    { url: '/instagram/accounts', response: ACCOUNTS },
    { url: /\/api\/agent\/config\/\d+$/, response: CONFIG },
    { method: 'PATCH', url: '/api/agent/config/7', response: (body: unknown) => ({ ...CONFIG, ...(body as object) }) },
    { url: '/api/agent/decisions', response: { data: [], meta: { total: 0 } } },
    { url: '/diagnostics', response: { issues: [], context_preview: 'Tipo de cuenta: personal.', profile_audit: { score: 50, items: [] } } },
  ]);
});

describe('StrategyPage', () => {
  test('opens the account and tab from the query string', async () => {
    renderAt('/strategy?account=9&tab=publicacion');
    expect(await screen.findByRole('heading', { name: '@viajes' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /Publicación/ })).toHaveAttribute('aria-selected', 'true');
    await waitFor(() => expect(calls.some(c => c.url.endsWith('/api/agent/config/9'))).toBe(true));
  });

  test('without account or with unknown tab falls back to first account and Marca', async () => {
    renderAt('/strategy?tab=nope');
    expect(await screen.findByRole('heading', { name: '@chef' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /Marca/ })).toHaveAttribute('aria-selected', 'true');
    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('/strategy?account=7&tab=marca'));
  });

  test('saving Publicación sends only its fields', async () => {
    renderAt('/strategy?account=7&tab=marca');
    fireEvent.change(await screen.findByLabelText('Sector / Nicho'), { target: { value: 'Cocina casera' } });
    // Descartar la edición de Marca para pasar a Publicación
    fireEvent.click(screen.getByRole('tab', { name: /Publicación/ }));
    fireEvent.click(await screen.findByRole('button', { name: 'Descartar cambios' }));

    fireEvent.click(await screen.findByRole('button', { name: 'Más Reel' }));
    fireEvent.click(screen.getByRole('button', { name: 'Guardar' }));

    await waitFor(() => expect(calls.find(c => c.method === 'PATCH')).toBeTruthy());
    const patch = calls.find(c => c.method === 'PATCH')!.body as Record<string, unknown>;
    expect(Object.keys(patch).sort()).toEqual(
      ['best_times', 'content_type_mix', 'hashtag_strategy', 'preferred_days', 'scheduling_mode'],
    );
    expect(patch.content_type_mix).toEqual({ post: 1, reel: 2, carousel: 1, story: 0 });
    expect(await screen.findByText('Guardado')).toBeInTheDocument();
  });

  test('switching tab with unsaved changes asks and keeps them on cancel', async () => {
    renderAt('/strategy?account=7&tab=marca');
    const sector = await screen.findByLabelText('Sector / Nicho');
    fireEvent.change(sector, { target: { value: 'Viajes' } });

    fireEvent.click(screen.getByRole('tab', { name: /Diagnóstico/ }));
    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByText(/¿Quieres descartarlos?/)).toBeInTheDocument();
    fireEvent.click(within(dialog).getByRole('button', { name: 'Seguir editando' }));

    expect(screen.getByRole('tab', { name: /Marca/ })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByLabelText('Sector / Nicho')).toHaveValue('Viajes');
  });

  test('switching account with unsaved changes asks for confirmation', async () => {
    renderAt('/strategy?account=7&tab=marca');
    fireEvent.change(await screen.findByLabelText('Sector / Nicho'), { target: { value: 'x' } });
    fireEvent.change(screen.getByLabelText('Cuenta'), { target: { value: '9' } });
    expect(await screen.findByRole('dialog')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Descartar cambios' }));
    expect(await screen.findByRole('heading', { name: '@viajes' })).toBeInTheDocument();
  });

  test('beforeunload is blocked only while there are unsaved changes', async () => {
    renderAt('/strategy?account=7&tab=marca');
    const sector = await screen.findByLabelText('Sector / Nicho');

    const clean = new Event('beforeunload', { cancelable: true });
    window.dispatchEvent(clean);
    expect(clean.defaultPrevented).toBe(false);

    fireEvent.change(sector, { target: { value: 'x' } });
    const dirty = new Event('beforeunload', { cancelable: true });
    window.dispatchEvent(dirty);
    expect(dirty.defaultPrevented).toBe(true);
  });

  test('campaign link guards unsaved changes and goes to the planner', async () => {
    renderAt('/strategy?account=7&tab=marca');
    fireEvent.change(await screen.findByLabelText('Sector / Nicho'), { target: { value: 'x' } });
    fireEvent.click(screen.getByRole('button', { name: /Campaña del mes/ }));
    fireEvent.click(await screen.findByRole('button', { name: 'Descartar cambios' }));
    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('/planner'));
  });
});
