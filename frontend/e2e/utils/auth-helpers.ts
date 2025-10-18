/**
 * Authentication helper functions for E2E tests
 */

import { Page } from '@playwright/test';
import { TEST_USERS } from '../fixtures/test-users';

/**
 * Login helper - performs login and waits for redirect
 */
export async function login(page: Page, email?: string, password?: string) {
  const user = TEST_USERS.validUser;

  await page.goto('/login');
  await page.fill('input[type="email"]', email || user.email);
  await page.fill('input[type="password"]', password || user.password);
  await page.click('button[type="submit"]');

  // Wait for redirect to dashboard
  await page.waitForURL('/dashboard', { timeout: 10000 });
}

/**
 * Logout helper
 */
export async function logout(page: Page) {
  // Click logout button (adjust selector based on your UI)
  await page.click('button:has-text("Cerrar Sesión"), button:has-text("Logout")');

  // Wait for redirect to login
  await page.waitForURL('/login', { timeout: 5000 });
}

/**
 * Check if user is authenticated
 */
export async function isAuthenticated(page: Page): Promise<boolean> {
  const authToken = await page.evaluate(() => localStorage.getItem('authToken'));
  return authToken !== null;
}

/**
 * Setup authenticated state (for tests that don't need to test login flow)
 */
export async function setupAuthenticatedState(page: Page) {
  // Mock token in localStorage
  await page.addInitScript(() => {
    localStorage.setItem('authToken', 'mock-jwt-token-for-testing');
  });
}
