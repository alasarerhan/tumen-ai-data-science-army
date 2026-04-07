import { http, HttpResponse, delay } from 'msw';

const mockRuns = [
  {
    id: 'run-1',
    workflow_id: 'wf-1',
    status: 'completed',
    started_at: '2026-01-01T00:00:00Z',
    completed_at: '2026-01-01T00:01:00Z',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:01:00Z',
  },
  {
    id: 'run-2',
    workflow_id: 'wf-1',
    status: 'running',
    started_at: '2026-01-02T00:00:00Z',
    created_at: '2026-01-02T00:00:00Z',
    updated_at: '2026-01-02T00:00:00Z',
  },
  {
    id: 'run-3',
    workflow_id: 'wf-2',
    status: 'failed',
    started_at: '2026-01-03T00:00:00Z',
    completed_at: '2026-01-03T00:00:30Z',
    error_message: 'Test error',
    created_at: '2026-01-03T00:00:00Z',
    updated_at: '2026-01-03T00:00:30Z',
  },
];

export const runsHandlers = [
  http.get('/v1/runs', async () => {
    await delay(100);
    return HttpResponse.json({
      items: mockRuns,
      total: mockRuns.length,
    });
  }),

  http.get('/v1/runs/:id', async ({ params }) => {
    await delay(100);
    const run = mockRuns.find((r) => r.id === params.id);
    if (!run) {
      return new HttpResponse(null, { status: 404 });
    }
    return HttpResponse.json(run);
  }),

  http.post('/v1/runs', async ({ request }) => {
    await delay(200);
    const body = (await request.json()) as Record<string, unknown>;
    const newRun = {
      id: `run-${Date.now()}`,
      workflow_id: body.workflow_id || 'wf-1',
      status: 'pending',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    return HttpResponse.json(newRun, { status: 201 });
  }),

  http.post('/v1/runs/:id/cancel', async ({ params }) => {
    await delay(100);
    const run = mockRuns.find((r) => r.id === params.id);
    if (!run) {
      return new HttpResponse(null, { status: 404 });
    }
    return HttpResponse.json({
      ...run,
      status: 'cancelled',
      updated_at: new Date().toISOString(),
    });
  }),

  http.post('/v1/runs/:id/retry', async ({ params }) => {
    await delay(100);
    const run = mockRuns.find((r) => r.id === params.id);
    if (!run) {
      return new HttpResponse(null, { status: 404 });
    }
    return HttpResponse.json({
      id: `run-${Date.now()}`,
      workflow_id: run.workflow_id,
      status: 'pending',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });
  }),
];
