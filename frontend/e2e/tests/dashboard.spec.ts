import { test, expect, loginAsDev, clearAuth } from '../fixtures/test-fixtures';

test.describe('Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await clearAuth(page);
    await loginAsDev(page);
  });

  test('should load dashboard after login', async ({ page }) => {
    await expect(page).toHaveURL(/.*dashboard/, { timeout: 10000 });
    await expect(page.locator('h1, h2, [data-testid="dashboard-title"]').first()).toBeVisible({ timeout: 10000 });
  });

  test('should show navigation menu', async ({ page }) => {
    await expect(page.locator('nav, [data-testid="sidebar"], aside').first()).toBeVisible({ timeout: 10000 });
  });

  test('should show user menu', async ({ page }) => {
    await expect(page.locator('[data-testid="user-menu"], button:has-text("test"), [aria-label*="user"], [aria-label*="account"]').first()).toBeVisible({ timeout: 10000 });
  });

  test('should navigate to workflows', async ({ page }) => {
    await page.click('a:has-text("Workflow"), [data-testid="nav-workflows"], button:has-text("Workflow")');
    await expect(page).toHaveURL(/.*workflow/, { timeout: 10000 });
  });

  test('should navigate to runs', async ({ page }) => {
    await page.click('a:has-text("Run"), [data-testid="nav-runs"], button:has-text("Run")');
    await expect(page).toHaveURL(/.*run/, { timeout: 10000 });
  });

  test('should logout successfully', async ({ page }) => {
    const userMenu = page.locator('[data-testid="user-menu"], button:has-text("test"), [aria-label*="user"], [aria-label*="account"]').first();
    await userMenu.click();
    await page.click('button:has-text("Logout"), a:has-text("Logout"), [data-testid="logout"]');
    await expect(page).toHaveURL(/.*login|\/$/, { timeout: 10000 });
  });
});
