import { test, expect, loginAsDev, clearAuth } from '../fixtures/test-fixtures';

test.describe('Workflow Create and Run', () => {
  test.beforeEach(async ({ page }) => {
    await clearAuth(page);
    await loginAsDev(page);
  });

  test('should navigate to workflows list', async ({ page }) => {
    await page.click('a:has-text("Workflow"), [data-testid="nav-workflows"]');
    await expect(page).toHaveURL(/.*workflow/, { timeout: 10000 });
  });

  test('should show workflows page content', async ({ page }) => {
    await page.goto('/workflows');
    await expect(page.locator('h1, h2, [data-testid="page-title"]').first()).toBeVisible({ timeout: 10000 });
  });

  test('should show create workflow button', async ({ page }) => {
    await page.goto('/workflows');
    await expect(page.locator('button:has-text("Create"), button:has-text("New"), a:has-text("Create")').first()).toBeVisible({ timeout: 10000 });
  });

  test('should navigate to workflow designer', async ({ page }) => {
    await page.goto('/workflows');
    const createBtn = page.locator('button:has-text("Create"), button:has-text("New"), a:has-text("Create")').first();
    await createBtn.click();
    await expect(page).toHaveURL(/.*designer|.*workflow.*new|.*create/, { timeout: 10000 });
  });

  test('should show workflow designer canvas', async ({ page }) => {
    await page.goto('/workflows/new');
    await expect(page.locator('[data-testid="designer-canvas"], .react-flow, [class*="react-flow"]').first()).toBeVisible({ timeout: 15000 });
  });

  test('should show YAML editor in designer', async ({ page }) => {
    await page.goto('/workflows/new');
    await expect(page.locator('[data-testid="yaml-editor"], .monaco-editor, [class*="monaco"]').first()).toBeVisible({ timeout: 15000 });
  });
});

test.describe('Runs List', () => {
  test.beforeEach(async ({ page }) => {
    await clearAuth(page);
    await loginAsDev(page);
  });

  test('should navigate to runs list', async ({ page }) => {
    await page.click('a:has-text("Run"), [data-testid="nav-runs"]');
    await expect(page).toHaveURL(/.*run/, { timeout: 10000 });
  });

  test('should show runs page content', async ({ page }) => {
    await page.goto('/runs');
    await expect(page.locator('h1, h2, [data-testid="page-title"], table, [data-testid="runs-list"]').first()).toBeVisible({ timeout: 10000 });
  });
});
