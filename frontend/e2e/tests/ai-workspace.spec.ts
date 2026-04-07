import { test, expect, loginAsDev, clearAuth } from '../fixtures/test-fixtures';

test.describe('AI Workspace', () => {
  test.beforeEach(async ({ page }) => {
    await clearAuth(page);
    await loginAsDev(page);
  });

  test('should navigate to AI Workspace', async ({ page }) => {
    await page.click('a:has-text("AI Workspace"), a:has-text("Workspace"), [data-testid="nav-ai-workspace"]');
    await expect(page).toHaveURL(/.*ai-workspace|.*workspace/, { timeout: 10000 });
  });

  test('should show AI Workspace page content', async ({ page }) => {
    await page.goto('/ai-workspace');
    await expect(page.locator('h1, h2, [data-testid="page-title"]').first()).toBeVisible({ timeout: 10000 });
  });

  test('should show chat input', async ({ page }) => {
    await page.goto('/ai-workspace');
    await expect(page.locator('textarea, input[type="text"], [data-testid="chat-input"]').first()).toBeVisible({ timeout: 10000 });
  });

  test('should show send button', async ({ page }) => {
    await page.goto('/ai-workspace');
    await expect(page.locator('button:has-text("Send"), [data-testid="send-button"], button[type="submit"]').first()).toBeVisible({ timeout: 10000 });
  });

  test('should show file upload area', async ({ page }) => {
    await page.goto('/ai-workspace');
    const uploadArea = page.locator('[data-testid="file-upload"], input[type="file"], .file-drop-zone, [class*="drop"]').first();
    await expect(uploadArea).toBeVisible({ timeout: 10000 });
  });

  test('should allow typing in chat input', async ({ page }) => {
    await page.goto('/ai-workspace');
    const chatInput = page.locator('textarea, input[type="text"]').first();
    await chatInput.fill('Test message');
    await expect(chatInput).toHaveValue('Test message');
  });
});
