import { test as base, expect, type Page } from '@playwright/test';

export interface TestUser {
  id: string;
  sub: string;
  email: string;
  tenant_memberships: Array<{ tenant_id: string; role: string }>;
  workspace_memberships: Array<{ workspace_id: string; role: string }>;
  claims: Record<string, unknown>;
}

export interface TestWorkspace {
  id: string;
  name: string;
  tenant_id: string;
}

export const mockUser: TestUser = {
  id: 'test-user-1',
  sub: 'test-user',
  email: 'test@example.com',
  tenant_memberships: [{ tenant_id: 'tenant-1', role: 'admin' }],
  workspace_memberships: [{ workspace_id: 'ws-1', role: 'admin' }],
  claims: {},
};

export const mockWorkspace: TestWorkspace = {
  id: 'ws-1',
  name: 'Test Workspace',
  tenant_id: 'tenant-1',
};

export const mockWorkflows = [
  {
    id: 'wf-1',
    name: 'Test Workflow',
    description: 'A test workflow',
    status: 'active',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
];

export const mockRuns = [
  {
    id: 'run-1',
    workflow_id: 'wf-1',
    status: 'completed',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
];

export async function loginAsDev(page: Page) {
  await page.goto('/');
  await page.fill('input[name="token"]', 'dev');
  await page.click('button[type="submit"]');
  await page.waitForURL('**/dashboard', { timeout: 10000 });
}

export async function clearAuth(page: Page) {
  await page.evaluate(() => {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('workspace_id');
  });
}

export const test = base.extend<{
  authenticatedPage: Page;
}>({
  authenticatedPage: async ({ page }, use) => {
    await loginAsDev(page);
    await use(page);
  },
});

export { expect };
