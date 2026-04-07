import { http, HttpResponse, delay } from 'msw';

const mockWorkflows = [
  {
    id: 'wf-1',
    name: 'Test Workflow',
    description: 'A test workflow for E2E testing',
    status: 'active',
    version: 1,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
  {
    id: 'wf-2',
    name: 'Another Workflow',
    description: 'Another test workflow',
    status: 'draft',
    version: 1,
    created_at: '2026-01-02T00:00:00Z',
    updated_at: '2026-01-02T00:00:00Z',
  },
];

export const workflowsHandlers = [
  http.get('/v1/workflows', async () => {
    await delay(100);
    return HttpResponse.json({
      items: mockWorkflows,
      total: mockWorkflows.length,
    });
  }),

  http.get('/v1/workflows/:id', async ({ params }) => {
    await delay(100);
    const workflow = mockWorkflows.find((w) => w.id === params.id);
    if (!workflow) {
      return new HttpResponse(null, { status: 404 });
    }
    return HttpResponse.json(workflow);
  }),

  http.post('/v1/workflows', async ({ request }) => {
    await delay(200);
    const body = (await request.json()) as Record<string, unknown>;
    const newWorkflow = {
      id: `wf-${Date.now()}`,
      name: body.name || 'New Workflow',
      description: body.description || '',
      status: 'draft',
      version: 1,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    return HttpResponse.json(newWorkflow, { status: 201 });
  }),

  http.put('/v1/workflows/:id', async ({ params, request }) => {
    await delay(100);
    const body = (await request.json()) as Record<string, unknown>;
    const workflow = mockWorkflows.find((w) => w.id === params.id);
    if (!workflow) {
      return new HttpResponse(null, { status: 404 });
    }
    return HttpResponse.json({
      ...workflow,
      ...body,
      updated_at: new Date().toISOString(),
    });
  }),

  http.post('/v1/workflows/:id/publish', async ({ params }) => {
    await delay(200);
    const workflow = mockWorkflows.find((w) => w.id === params.id);
    if (!workflow) {
      return new HttpResponse(null, { status: 404 });
    }
    return HttpResponse.json({
      ...workflow,
      status: 'active',
      updated_at: new Date().toISOString(),
    });
  }),
];
