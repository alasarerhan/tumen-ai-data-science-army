import { http, HttpResponse, delay } from 'msw';

const mockSignals = [
  {
    id: 'sig-1',
    run_id: 'run-1',
    type: 'approval',
    status: 'pending',
    message: 'Please approve this action',
    created_at: '2026-01-01T00:00:00Z',
  },
  {
    id: 'sig-2',
    run_id: 'run-1',
    type: 'input',
    status: 'completed',
    message: 'Input provided',
    created_at: '2026-01-01T00:01:00Z',
  },
];

export const signalsHandlers = [
  http.get('/v1/signals', async () => {
    await delay(100);
    return HttpResponse.json({
      items: mockSignals,
      total: mockSignals.length,
    });
  }),

  http.get('/v1/signals/:id', async ({ params }) => {
    await delay(100);
    const signal = mockSignals.find((s) => s.id === params.id);
    if (!signal) {
      return new HttpResponse(null, { status: 404 });
    }
    return HttpResponse.json(signal);
  }),

  http.post('/v1/signals/:id/respond', async ({ params, request }) => {
    await delay(100);
    const signal = mockSignals.find((s) => s.id === params.id);
    if (!signal) {
      return new HttpResponse(null, { status: 404 });
    }
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json({
      ...signal,
      status: 'completed',
      response: body.response || 'Approved',
      updated_at: new Date().toISOString(),
    });
  }),
];
