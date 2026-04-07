import { http, HttpResponse, delay } from 'msw';

export const authHandlers = [
  http.get('/v1/me', async () => {
    await delay(100);
    return HttpResponse.json({
      id: 'test-user-1',
      sub: 'test-user',
      email: 'test@example.com',
      tenant_memberships: [{ tenant_id: 'tenant-1', role: 'admin' }],
      workspace_memberships: [{ workspace_id: 'ws-1', role: 'admin' }],
      claims: {},
    });
  }),

  http.post('/v1/auth/refresh', async () => {
    await delay(100);
    return HttpResponse.json({
      access_token: 'new-test-token',
      token_type: 'bearer',
      expires_in: 3600,
    });
  }),
];
