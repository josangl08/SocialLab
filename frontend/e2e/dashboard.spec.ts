/**
 * E2E Tests - Dashboard
 */

import { test, expect } from '@playwright/test';
import { setupAuthenticatedState } from './utils/auth-helpers';

test.describe('Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    // Setup authenticated state
    await setupAuthenticatedState(page);
  });

  test('should display dashboard stats', async ({ page }) => {
    test.skip(true, 'Requires backend setup and mocked Instagram data');

    await page.goto('/dashboard');

    // Check for stats cards
    await expect(page.locator('text=/seguidores|followers/i')).toBeVisible();
    await expect(page.locator('text=/alcance|reach/i')).toBeVisible();
    await expect(page.locator('text=/engagement/i')).toBeVisible();
  });

  test('should show connect Instagram button when not connected', async ({ page }) => {
    await page.goto('/dashboard');

    // Should show connect button
    const connectButton = page.locator('button:has-text("Conectar Instagram")');
    await expect(connectButton).toBeVisible();
  });

  test('should navigate to create post', async ({ page }) => {
    test.skip(true, 'Requires backend setup');

    await page.goto('/dashboard');

    // Click create post button
    await page.click('button:has-text("Crear Post")');

    // Should navigate to create post page
    await expect(page).toHaveURL(/\/create-post/);
  });

  test('should navigate to analytics', async ({ page }) => {
    test.skip(true, 'Requires backend setup');

    await page.goto('/dashboard');

    // Click analytics button
    await page.click('button:has-text("Analytics")');

    // Should navigate to analytics page
    await expect(page).toHaveURL(/\/analytics/);
  });

  test('should be accessible', async ({ page }) => {
    const { injectAxe, checkA11y } = await import('@axe-core/playwright');

    await page.goto('/dashboard');

    // Inject axe-core
    await injectAxe(page);

    // Run accessibility checks
    await checkA11y(page, undefined, {
      detailedReport: true,
      detailedReportOptions: {
        html: true
      }
    });
  });
});
