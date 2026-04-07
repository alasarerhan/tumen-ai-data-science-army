import { setupWorker } from 'msw/browser';
import { authHandlers } from './handlers/auth';
import { workflowsHandlers } from './handlers/workflows';
import { runsHandlers } from './handlers/runs';
import { chatHandlers } from './handlers/chat';
import { signalsHandlers } from './handlers/signals';

export const handlers = [
  ...authHandlers,
  ...workflowsHandlers,
  ...runsHandlers,
  ...chatHandlers,
  ...signalsHandlers,
];

export const worker = setupWorker(...handlers);

export async function enableMocking() {
  if (import.meta.env.DEV) {
    const { worker } = await import('./browser');
    return worker.start({
      onUnhandledRequest: 'bypass',
    });
  }
}
