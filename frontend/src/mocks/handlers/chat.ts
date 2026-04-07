import { http, HttpResponse, delay } from 'msw';

const mockChatSessions = [
  {
    id: 'chat-1',
    title: 'Test Chat',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
];

const mockMessages = [
  {
    id: 'msg-1',
    session_id: 'chat-1',
    role: 'user',
    content: 'Hello, can you help me analyze my data?',
    created_at: '2026-01-01T00:00:00Z',
  },
  {
    id: 'msg-2',
    session_id: 'chat-1',
    role: 'assistant',
    content: 'Of course! I can help you with data analysis. What would you like to explore?',
    created_at: '2026-01-01T00:00:01Z',
  },
];

export const chatHandlers = [
  http.get('/v1/chat/sessions', async () => {
    await delay(100);
    return HttpResponse.json({
      items: mockChatSessions,
      total: mockChatSessions.length,
    });
  }),

  http.get('/v1/chat/sessions/:id', async ({ params }) => {
    await delay(100);
    const session = mockChatSessions.find((s) => s.id === params.id);
    if (!session) {
      return new HttpResponse(null, { status: 404 });
    }
    return HttpResponse.json(session);
  }),

  http.get('/v1/chat/sessions/:id/messages', async ({ params }) => {
    await delay(100);
    const messages = mockMessages.filter((m) => m.session_id === params.id);
    return HttpResponse.json({
      items: messages,
      total: messages.length,
    });
  }),

  http.post('/v1/chat/sessions', async ({ request }) => {
    await delay(200);
    const body = (await request.json()) as Record<string, unknown>;
    const newSession = {
      id: `chat-${Date.now()}`,
      title: body.title || 'New Chat',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    return HttpResponse.json(newSession, { status: 201 });
  }),

  http.post('/v1/chat/sessions/:id/messages', async ({ params, request }) => {
    await delay(300);
    const body = (await request.json()) as Record<string, unknown>;
    const userMessage = {
      id: `msg-${Date.now()}`,
      session_id: params.id,
      role: 'user',
      content: body.content || '',
      created_at: new Date().toISOString(),
    };
    const assistantMessage = {
      id: `msg-${Date.now() + 1}`,
      session_id: params.id,
      role: 'assistant',
      content: 'I understand your request. Let me analyze that for you...',
      created_at: new Date().toISOString(),
    };
    return HttpResponse.json({ user_message: userMessage, assistant_message: assistantMessage }, { status: 201 });
  }),
];
