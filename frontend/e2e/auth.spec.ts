/**
 * E2E Tests - Authentication Flow
 */

import { test, expect } from '@playwright/test';
import { TEST_USERS } from './fixtures/test-users';
import { login, logout } from './utils/auth-helpers';

test.describe('Authentication', () => {
  test.beforeEach(async ({ page }) => {
    // Clear storage before each test
    await page.context().clearCookies();
    await page.evaluate(() => localStorage.clear());
  });

  test('should display login page', async ({ page }) => {
    await page.goto('/login');

    // Check page title
    await expect(page).toHaveTitle(/SocialLab/i);

    // Check login form elements
    await expect(page.locator('input[type="email"]')).toBeVisible();
    await expect(page.locator('input[type="password"]')).toBeVisible();
    await expect(page.locator('button[type="submit"]')).toBeVisible();
  });

  test('should show error with invalid credentials', async ({ page }) => {
    await page.goto('/login');

    const { email, password } = TEST_USERS.invalidUser;

    await page.fill('input[type="email"]', email);
    await page.fill('input[type="password"]', password);
    await page.click('button[type="submit"]');

    // Should show error message
    await expect(page.locator('text=/error|inválid|incorrecto/i')).toBeVisible({
      timeout: 5000
    });

    // Should stay on login page
    await expect(page).toHaveURL(/\/login/);
  });

  test('should login successfully with valid credentials', async ({ page }) => {
    // Note: This test requires a test user in the database
    // or mocked API responses
    test.skip(true, 'Requires backend setup with test user');

    await login(page);

    // Should redirect to dashboard
    await expect(page).toHaveURL(/\/dashboard/);

    // Should show user info
    await expect(page.locator('text=/dashboard/i')).toBeVisible();
  });

  test('should logout successfully', async ({ page }) => {
    test.skip(true, 'Requires backend setup with test user');

    // Login first
    await login(page);

    // Logout
    await logout(page);

    // Should redirect to login
    await expect(page).toHaveURL(/\/login/);

    // Should not have auth token
    const token = await page.evaluate(() => localStorage.getItem('authToken'));
    expect(token).toBeNull();
  });

  test('should redirect to login when accessing protected route without auth', async ({ page }) => {
    await page.goto('/dashboard');

    // Should redirect to login
    await expect(page).toHaveURL(/\/login/, { timeout: 5000 });
  });
});
