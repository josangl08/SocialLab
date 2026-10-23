/**
 * E2E - Página de estrategia del agente y campaña mensual en el planner
 * (agent-strategy-redesign). La API está simulada por completo.
 */

import { test, expect, type Page, type Route } from '@playwright/test';

const API = 'http://localhost:8000';
const TZ = 'Europe/Madrid';

const ACCOUNT = { id: 7, username: 'chef', sector: 'Cocina', primary_timezone: TZ, detected_timezone: TZ };

const BASE_CONFIG = {
  account_type: 'personal', sector: 'Cocina', purpose: 'Inspirar', target_audience: 'Cocineros caseros',
  style_guide: '', default_tone: 'casual', default_language: 'es', best_times: ['20:00'],
  content_pillars: ['recetas'], hashtag_strategy: 'moderate', caption_voice: null, reference_accounts: [],
  posts_per_week: 2, scheduling_mode: 'fixed', preferred_days: ['Tuesday', 'Thursday'],
  content_type_mix: { post: 1, reel: 1, carousel: 0, story: 0 }, humanizer_enabled: true, banned_phrases: [],
  strategy_wizard_answers: null,
};

interface MockState { config: typeof BASE_CONFIG; patches: unknown[]; campaign: Record<string, unknown> | null }

/** Diagnóstico mínimo calculado sobre la config simulada (MIX_EXCEEDS_DAYS). */
function diagnostics(config: typeof BASE_CONFIG) {
  const total = Object.values(config.content_type_mix).reduce((s, n) => s + n, 0);
  const issues = config.scheduling_mode === 'fixed' && total > config.preferred_days.length
    ? [{ code: 'MIX_EXCEEDS_DAYS', severity: 'warning', field: 'content_type_mix', tab: 'publicacion',
         message: `El mix suma ${total} publicaciones por semana pero solo has elegido ${config.preferred_days.length} días.` }]
    : [];
  return { issues, context_preview: `Tipo de cuenta: personal. Publicaciones por semana objetivo: ${total}.`,
           profile_audit: { score: 70, items: [] } };
}

async function mockApi(page: Page): Promise<MockState> {
  const state: MockState = { config: structuredClone(BASE_CONFIG), patches: [], campaign: null };
  await page.route(`${API}/**`, async (route: Route) => {
    const req = route.request();
    const path = new URL(req.url()).pathname;
    const method = req.method();

    if (path === '/instagram/accounts') return route.fulfill({ json: [ACCOUNT] });
    if (path === '/api/agent/config/7' && method === 'GET') return route.fulfill({ json: state.config });
    if (path === '/api/agent/config/7' && method === 'PATCH') {
      const patch = req.postDataJSON();
      state.patches.push(patch);
      state.config = { ...state.config, ...patch };
      return route.fulfill({ json: state.config });
    }
    if (path === '/api/agent/strategy/7/diagnostics') return route.fulfill({ json: diagnostics(state.config) });
    if (path === '/api/agent/reference-accounts/7') {
      return route.fulfill({ json: {
        refreshed: false, summary: '',
        references: state.config.reference_accounts.map(u => (u === 'amiga'
          ? { username: u, status: 'not_professional', error_message: 'x' }
          : { username: u, status: 'ok', followers: 12500, posts_per_week: 4.5,
              format_mix: { REELS: 60, CAROUSEL_ALBUM: 20, IMAGE: 20 }, hook_formulas: ['Curiosidad'],
              top_posts: [{ caption_first_line: 'Nadie te cuenta esto', media_type: 'REELS', engagement_rate: 8.2,
                            permalink: 'https://instagram.com/p/abc' }] })),
      } });
    }
    if (path === '/api/agent/decisions') return route.fulfill({ json: { data: [], meta: { total: 0 } } });

    if (path === '/api/agent/campaign' && method === 'GET') {
      return state.campaign ? route.fulfill({ json: state.campaign }) : route.fulfill({ json: null });
    }
    if (path === '/api/agent/campaign/trigger') {
      state.campaign = {
        id: 'c1', account_id: 7, month_date: '2026-10-01', strategy_mode: 'personal_storyline',
        title: 'Otoño en la cocina', description: 'Recetas de temporada', milestones: [],
        weekly_focus: { '1': 'Setas', '2': 'Calabaza', '3': 'Castañas', '4': 'Guisos' },
        status: 'pending_approval', generated_by: 'hermes',
      };
      return route.fulfill({ json: { triggered: true } });
    }
    if (path === '/api/agent/campaign/c1/approve') {
      state.campaign = { ...state.campaign, status: 'approved' };
      return route.fulfill({ json: state.campaign });
    }

    if (method === 'GET') return route.fulfill({ json: [] });
    return route.fulfill({ json: {} });
  });
  return state;
}

test.beforeEach(async ({ page }) => {
  await page.clock.install({ time: new Date('2026-10-14T10:00:00+02:00') });
  await page.addInitScript(() => localStorage.setItem('authToken', 'mock-jwt-token-for-testing'));
});

test('cuentas → Estrategia → editar Publicación → Diagnóstico refleja el cambio', async ({ page }) => {
  const state = await mockApi(page);
  await page.goto('/settings');

  await page.getByRole('link', { name: /Estrategia →/ }).click();
  await expect(page).toHaveURL(/\/strategy\?account=7&tab=marca/);
  await expect(page.getByRole('heading', { name: '@chef' })).toBeVisible();

  await page.getByRole('tab', { name: /Publicación/ }).click();
  await page.getByRole('button', { name: 'Más Reel' }).click();
  await page.getByRole('button', { name: 'Guardar' }).click();
  await expect(page.getByText('Guardado')).toBeVisible();
  expect(state.patches).toEqual([expect.objectContaining({ content_type_mix: { post: 1, reel: 2, carousel: 0, story: 0 } })]);

  await page.getByRole('tab', { name: /Diagnóstico/ }).click();
  await expect(page.getByText(/El mix suma 3 publicaciones por semana/)).toBeVisible();
  await expect(page.getByTestId('context-preview')).toContainText('Publicaciones por semana objetivo: 3.');
});

test('el planner genera y aprueba la campaña del mes', async ({ page }) => {
  await mockApi(page);
  await page.goto('/planner');

  await page.getByRole('button', { name: /Generar con Hermes/ }).click();
  await page.clock.runFor(5000);
  await expect(page.getByText('Hermes propone una campaña para este mes')).toBeVisible();

  await page.getByRole('button', { name: /Aprobar/ }).click();
  await expect(page.getByText('Hermes propone una campaña para este mes')).toBeHidden();
  await expect(page.getByText('Otoño en la cocina')).toBeVisible();
  await expect(page.getByRole('link', { name: 'Ver estrategia →' })).toHaveAttribute('href', '/strategy?account=7');
});

test('Referentes: añadir, guardar y ver el análisis con aviso para cuentas personales', async ({ page }) => {
  const state = await mockApi(page);
  await page.goto('/strategy?account=7&tab=referentes');

  const input = page.getByPlaceholder('cuenta_referente');
  for (const name of ['@chef_pro', 'amiga']) {
    await input.fill(name);
    await input.press('Enter');
  }
  await expect(page.getByText('Guarda los cambios para analizar la nueva lista.')).toBeVisible();
  await page.getByRole('button', { name: 'Guardar' }).click();
  expect(state.patches).toEqual([{ reference_accounts: ['chef_pro', 'amiga'] }]);

  await expect(page.getByText('12.500 seguidores')).toBeVisible();
  await expect(page.getByRole('link', { name: 'Nadie te cuenta esto' })).toHaveAttribute('href', 'https://instagram.com/p/abc');
  await expect(page.getByText(/No es una cuenta profesional/)).toBeVisible();
});

