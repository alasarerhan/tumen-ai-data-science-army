import http from 'k6/http';
import { check } from 'k6';
import { SharedArray } from 'k6/data';

const users = new SharedArray('users', function () {
  return Array.from({ length: 100 }, (_, i) => ({
    userId: `user-${i}`,
    workspaceId: '00000000-0000-0000-0000-000000000001',
  }));
});

export const options = {
  scenarios: {
    constant_request_rate: {
      executor: 'constant-arrival-rate',
      rate: 100,
      timeUnit: '1s',
      duration: '2m',
      preAllocatedVUs: 50,
      maxVUs: 200,
    },
  },
  thresholds: {
    http_req_duration: ['p(99)<500', 'p(95)<250'],
    http_req_failed: ['rate<0.01'],
  },
};

const BASE_URL = __ENV.API_URL || 'http://localhost:8000';

export default function () {
  const user = users[__VU % users.length];
  
  const res = http.get(`${BASE_URL}/v1/workflows?workspace_id=${user.workspaceId}`, {
    headers: {
      'X-User-Id': user.userId,
    },
  });

  check(res, {
    'status is 200': (r) => r.status === 200,
    'has rate limit headers': (r) => r.headers['X-RateLimit-Limit'] !== undefined,
    'response time < 500ms': (r) => r.timings.duration < 500,
  });
}
