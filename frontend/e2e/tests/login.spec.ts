import { test, expect, clearAuth, loginThroughDevForm } from '../fixtures/test-fixtures';

test.describe('Login', () => {
  test.beforeEach(async ({ page }) => {
    await clearAuth(page);
  });

  test('should render login form', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: /developer token/i }).click();
    await expect(page.locator('input[name="token"]')).toBeVisible();
    await expect(page.locator('button[type="submit"]')).toBeVisible();
  });

  test('should login with dev token', async ({ page }) => {
    await loginThroughDevForm(page);
    await expect(page).toHaveURL(/.*dashboard/, { timeout: 10000 });
  });

  test('should show error with invalid token', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: /developer token/i }).click();
    await page.fill('input[name="token"]', 'invalid-token-12345');
    await page.click('button[type="submit"]');
    await expect(page.locator('text=/error|failed|invalid/i')).toBeVisible({ timeout: 5000 });
  });

  test('should redirect to dashboard if already authenticated', async ({ page }) => {
    await loginThroughDevForm(page);
    await expect(page).toHaveURL(/.*dashboard/, { timeout: 10000 });
    
    await page.goto('/');
    await expect(page).toHaveURL(/.*dashboard/, { timeout: 5000 });
  });
});
