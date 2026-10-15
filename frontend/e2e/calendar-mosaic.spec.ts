/**
 * E2E - Mosaico de miniaturas del calendario (calendar-image-previews).
 * La API está simulada por completo: no toca el backend ni la base de datos.
 */

import { test, expect, type Locator, type Page, type Route } from '@playwright/test';

const API = 'http://localhost:8000';
const TZ = 'Europe/Madrid';
const NOW = new Date('2026-10-14T10:00:00+02:00');

type Status = 'draft' | 'scheduled' | 'published';

function post(id: number, day: number, hour: number, status: Status, extra: Record<string, unknown> = {}) {
  const hh = String(hour).padStart(2, '0');
  const dd = String(day).padStart(2, '0');
  return {
    id,
    user_id: 'u1',
    content: `Publicación ${id} del día ${day}`,
    media_url: `https://example.com/img-${id}.jpg`,
    post_type: 'post',
    content_format: 'post',
    status,
    scheduled_at: `2026-10-${dd}T${hh}:00:00+02:00`,
    created_at: '2026-10-01T10:00:00+02:00',
    instagram_account_id: 1,
    ...extra,
  };
}

// Días de octubre con 1, 2, 3, 4 y 6 publicaciones
const POSTS = [
  post(1, 20, 10, 'scheduled'),
  post(2, 21, 12, 'published'), post(3, 21, 9, 'draft'),
  post(4, 22, 9, 'scheduled'), post(5, 22, 10, 'draft', { is_ai_generated: true }), post(6, 22, 11, 'scheduled', { is_ai_generated: true }),
  post(7, 23, 9, 'scheduled'), post(8, 23, 10, 'scheduled'), post(9, 23, 11, 'scheduled'),
  post(10, 23, 12, 'draft', { media_url: null, content_format: 'reel', post_type: 'reel' }),
  ...[11, 12, 13, 14, 15, 16].map((id, i) => post(id, 24, 9 + i, 'scheduled')),
];

// Foto vertical 3:4 para comprobar que se ve completa (contain)
const PORTRAIT_SVG =
  '<svg xmlns="http://www.w3.org/2000/svg" width="120" height="160"><rect width="120" height="160" fill="#9a9a9a"/></svg>';

async function mockApi(page: Page, opts: { rescheduleStatus?: number; posts?: unknown[] } = {}) {
  const reschedules: { id: string; body: unknown }[] = [];
  await page.route(`${API}/**`, async (route: Route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    if (path === '/api/posts') return route.fulfill({ json: opts.posts ?? POSTS });
    if (/^\/api\/posts\/\d+\/thumbnail$/.test(path)) {
      return route.fulfill({ contentType: 'image/svg+xml', body: PORTRAIT_SVG });
    }
    if (path === '/instagram/accounts') {
      return route.fulfill({ json: [{ id: 1, username: 'demo', primary_timezone: TZ, detected_timezone: TZ }] });
    }
    const reschedule = path.match(/^\/api\/scheduler\/reschedule\/(\d+)$/);
    if (reschedule) {
      reschedules.push({ id: reschedule[1], body: route.request().postDataJSON() });
      const status = opts.rescheduleStatus ?? 200;
      return route.fulfill({ status, json: status === 200 ? { ok: true } : { detail: 'fallo simulado' } });
    }
    // Sin campaña mensual (el banner espera un objeto, no una lista)
    if (path === '/api/agent/campaign') return route.fulfill({ status: 404, json: { detail: 'sin campaña' } });
    if (route.request().method() === 'GET') return route.fulfill({ json: [] });
    return route.fulfill({ json: {} });
  });
  // Las imágenes originales del visor
  await page.route('https://example.com/**', route =>
    route.fulfill({ contentType: 'image/svg+xml', body: PORTRAIT_SVG }),
  );
  return reschedules;
}

async function openCalendar(page: Page) {
  await page.clock.install({ time: NOW });
  await page.addInitScript(() => localStorage.setItem('authToken', 'mock-jwt-token-for-testing'));
  await page.goto('/planner');
  await expect(page.getByTestId('day-mosaic').first()).toBeVisible();
}

/** Mosaico del día `day` de octubre (por la posición de su celda en el mes). */
async function dayIndex(page: Page, day: number): Promise<number> {
  const cells = page.locator('.rbc-month-view .rbc-date-cell');
  const count = await cells.count();
  for (let i = 0; i < count; i++) {
    const cell = cells.nth(i);
    const offRange = (await cell.getAttribute('class'))?.includes('rbc-off-range');
    if (!offRange && Number((await cell.innerText()).trim()) === day) return i;
  }
  throw new Error(`día ${day} no encontrado`);
}

async function box(locator: Locator) {
  const b = await locator.boundingBox();
  if (!b) throw new Error('elemento sin caja visible');
  return b;
}

function dayCell(page: Page, index: number) {
  return page.locator('.rbc-month-view .rbc-day-bg').nth(index);
}

function mosaicOf(page: Page, postId: number) {
  return page.getByTestId('day-mosaic').filter({ has: page.getByTestId(`mosaic-tile-${postId}`) });
}

test.use({ timezoneId: TZ, viewport: { width: 1440, height: 1000 } });

test.describe('Calendario: mosaico de miniaturas', () => {
  test('disposición por número de publicaciones, orden y estados', async ({ page }) => {
    await mockApi(page);
    await openCalendar(page);

    await expect(mosaicOf(page, 1)).toHaveClass(/sl-mosaic--1/);
    await expect(mosaicOf(page, 2)).toHaveClass(/sl-mosaic--2/);
    await expect(mosaicOf(page, 4)).toHaveClass(/sl-mosaic--4/);
    await expect(mosaicOf(page, 7)).toHaveClass(/sl-mosaic--4/);
    await expect(mosaicOf(page, 11)).toHaveClass(/sl-mosaic--4/);

    // 2 publicaciones: ordenadas por hora (la de las 9:00 primero)
    const tiles21 = mosaicOf(page, 2).locator('[data-post-id]');
    await expect(tiles21).toHaveCount(2);
    await expect(tiles21.nth(0)).toHaveAttribute('data-post-id', '3');

    // Estados en el borde
    await expect(page.getByTestId('mosaic-tile-2')).toHaveClass(/event-status-published/);
    await expect(page.getByTestId('mosaic-tile-3')).toHaveClass(/event-status-draft/);
    await expect(page.getByTestId('mosaic-tile-5')).toHaveClass(/event-proposal/);
    await expect(page.getByTestId('mosaic-tile-6')).toHaveClass(/event-ai-scheduled/);

    // Sin imagen → icono del formato, sin romper el 2×2
    await expect(page.getByTestId('mosaic-placeholder-10')).toBeVisible();
    await expect(mosaicOf(page, 7).locator('[data-post-id]')).toHaveCount(4);

    // 6 publicaciones → 3 miniaturas + "+3"
    await expect(mosaicOf(page, 11).locator('[data-post-id]')).toHaveCount(3);
    await expect(mosaicOf(page, 11).getByRole('button', { name: '+3' })).toBeVisible();

    // Las miniaturas caben en su celda y la foto se ve completa (no se recorta)
    for (const [id, day] of [[1, 20], [2, 21], [4, 22], [7, 23], [11, 24]]) {
      const mosaic = await box(mosaicOf(page, id));
      const cell = await box(dayCell(page, await dayIndex(page, day)));
      expect(mosaic.x).toBeGreaterThanOrEqual(cell.x - 1);
      expect(mosaic.x + mosaic.width).toBeLessThanOrEqual(cell.x + cell.width + 1);
      expect(mosaic.y + mosaic.height).toBeLessThanOrEqual(cell.y + cell.height + 1);
    }
    const fit = await page.getByTestId('mosaic-tile-1').locator('img').evaluate(img => getComputedStyle(img).objectFit);
    expect(fit).toBe('contain');

    await page.screenshot({ path: 'test-results/calendar-mosaic.png', fullPage: true });
  });

  test('clic abre el visor, navega, Ver detalles y Esc', async ({ page }) => {
    await mockApi(page);
    await openCalendar(page);

    await page.getByTestId('mosaic-tile-2').click();
    const lightbox = page.getByTestId('media-lightbox');
    await expect(lightbox).toBeVisible();
    await expect(lightbox.locator('.sl-lightbox-count')).toHaveText('2 / 2');
    await expect(lightbox.locator('img.sl-lightbox-img')).toHaveAttribute('src', 'https://example.com/img-2.jpg');
    await expect(lightbox).toContainText('Post');

    await page.keyboard.press('ArrowLeft');
    await expect(lightbox.locator('.sl-lightbox-count')).toHaveText('1 / 2');

    await page.keyboard.press('Escape');
    await expect(lightbox).toBeHidden();

    // "+N" abre todas las del día
    await mosaicOf(page, 11).getByRole('button', { name: '+3' }).click();
    await expect(lightbox.locator('.sl-lightbox-count')).toHaveText('4 / 6');
    await lightbox.getByLabel('Siguiente').click();
    await expect(lightbox.locator('.sl-lightbox-count')).toHaveText('5 / 6');

    // Clic fuera cierra
    await page.mouse.click(1430, 990);
    await expect(lightbox).toBeHidden();

    // Ver detalles abre el modal del post
    await page.getByTestId('mosaic-tile-1').click();
    await lightbox.getByRole('button', { name: 'Ver detalles' }).click();
    await expect(lightbox).toBeHidden();
    await expect(page.getByText('Publicación 1 del día 20').first()).toBeVisible();
  });

  test('arrastrar una miniatura a otro día la reprograma conservando la hora', async ({ page }) => {
    const reschedules = await mockApi(page);
    await openCalendar(page);

    const target = dayCell(page, await dayIndex(page, 27));
    await page.getByTestId('mosaic-tile-4').dragTo(target, { force: true });

    await expect.poll(() => reschedules.length).toBe(1);
    expect(reschedules[0].id).toBe('4');
    expect((reschedules[0].body as { new_scheduled_time: string }).new_scheduled_time)
      .toBe(new Date('2026-10-27T09:00:00+01:00').toISOString());
    // Se recompone: el 22 se queda con 2 y el 27 con 1
    await expect(mosaicOf(page, 5).locator('[data-post-id]')).toHaveCount(2);
    await expect(mosaicOf(page, 4)).toHaveClass(/sl-mosaic--1/);
  });

  test('si falla el backend, la miniatura vuelve a su día', async ({ page }) => {
    const reschedules = await mockApi(page, { rescheduleStatus: 500 });
    await openCalendar(page);

    const target = dayCell(page, await dayIndex(page, 27));
    await page.getByTestId('mosaic-tile-1').dragTo(target, { force: true });

    await expect.poll(() => reschedules.length).toBe(1);
    await expect(page.getByText('Could not reschedule the post.')).toBeVisible();
    await expect(mosaicOf(page, 1)).toHaveClass(/sl-mosaic--1/);
    const index20 = await dayIndex(page, 20);
    const tile = await box(page.getByTestId('mosaic-tile-1'));
    const cell = await box(dayCell(page, index20));
    expect(tile.x).toBeGreaterThanOrEqual(cell.x - 1);
    expect(tile.x).toBeLessThanOrEqual(cell.x + cell.width);
  });

  test('con miniatura guardada, la imagen sale de Storage sin pedir nada al backend', async ({ page }) => {
    const storage = 'https://p.supabase.test/storage/v1/object/public/thumbnails/u1';
    const stored = POSTS.map(p => (p.media_url ? { ...p, thumbnail_url_base: `${storage}/${p.id}/k${p.id}` } : p));
    await mockApi(page, { posts: stored });
    const storageRequests: string[] = [];
    await page.route(`${storage}/**`, route => {
      storageRequests.push(route.request().url());
      return route.fulfill({ contentType: 'image/svg+xml', body: PORTRAIT_SVG });
    });
    const backendThumbnails: string[] = [];
    page.on('request', request => {
      if (/\/api\/posts\/\d+\/thumbnail/.test(request.url())) backendThumbnails.push(request.url());
    });

    await openCalendar(page);

    await expect(page.getByTestId('mosaic-tile-1').locator('img')).toHaveAttribute('src', `${storage}/1/k1_160.webp`);
    await expect.poll(() => storageRequests.length).toBeGreaterThan(0);
    expect(backendThumbnails).toHaveLength(0);
  });

  test('un Reel de Instagram muestra su portada en vez del icono', async ({ page }) => {
    const reel = post(30, 20, 18, 'published', {
      media_url: null, media_thumbnail_url: 'https://cdn.test/cover.jpg', post_type: 'VIDEO', content_format: null,
    });
    await mockApi(page, { posts: [...POSTS, reel] });

    await openCalendar(page);

    const tile = page.getByTestId('mosaic-tile-30');
    await expect(tile.locator('img')).toHaveAttribute('src', /\/api\/posts\/30\/thumbnail\?size=160/);
    await expect(page.getByTestId('mosaic-placeholder-30')).toHaveCount(0);
  });

  test('soltar en un día pasado no la mueve', async ({ page }) => {
    const reschedules = await mockApi(page);
    await openCalendar(page);

    const target = dayCell(page, await dayIndex(page, 6));
    await page.getByTestId('mosaic-tile-1').dragTo(target, { force: true });

    await expect(page.getByText('Cannot schedule posts in the past.')).toBeVisible();
    expect(reschedules).toHaveLength(0);
  });
});
