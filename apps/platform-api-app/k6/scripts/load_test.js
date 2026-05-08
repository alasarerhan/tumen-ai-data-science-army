import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';

const errorRate = new Rate('errors');
const latencyP99 = new Trend('latency_p99');
const requestsPerSecond = new Counter('requests_per_second');

export const options = {
  scenarios: {
    smoke: {
      executor: 'constant-vus',
      vus: 5,
      duration: '30s',
      tags: { test_type: 'smoke' },
    },
    load: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '30s', target: 20 },
        { duration: '1m', target: 50 },
        { duration: '30s', target: 100 },
        { duration: '1m', target: 100 },
        { duration: '30s', target: 0 },
      ],
      tags: { test_type: 'load' },
    },
    spike: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '10s', target: 100 },
        { duration: '30s', target: 100 },
        { duration: '10s', target: 10 },
        { duration: '30s', target: 10 },
      ],
      tags: { test_type: 'spike' },
    },
  },
  thresholds: {
    http_req_duration: ['p(99)<500', 'p(95)<250'],
    http_req_failed: ['rate<0.01'],
    errors: ['rate<0.01'],
  },
};

const BASE_URL = __ENV.API_URL || 'http://localhost:8000';
const WORKSPACE_ID = __ENV.WORKSPACE_ID || '00000000-0000-0000-0000-000000000001';

export function setup() {
  console.log(`Running load tests against ${BASE_URL}`);
  return { baseUrl: BASE_URL, workspaceId: WORKSPACE_ID };
}

export default function (data) {
  const { baseUrl, workspaceId } = data;

  group('Health Check', () => {
    const res = http.get(`${baseUrl}/healthz`);
    check(res, {
      'healthz status is 200': (r) => r.status === 200,
      'healthz response time < 100ms': (r) => r.timings.duration < 100,
    });
    errorRate.add(res.status !== 200);
    latencyP99.add(res.timings.duration);
  });

  sleep(0.5);

  group('List Workflows', () => {
    const res = http.get(`${baseUrl}/v1/workflows?workspace_id=${workspaceId}`);
    check(res, {
      'workflows status is 200': (r) => r.status === 200,
      'workflows response has items': (r) => {
        try {
          const body = JSON.parse(r.body);
          return Array.isArray(body.items);
        } catch {
          return false;
        }
      },
      'workflows p99 < 500ms': (r) => r.timings.duration < 500,
    });
    errorRate.add(res.status !== 200);
    latencyP99.add(res.timings.duration);
    requestsPerSecond.add(1);
  });

  sleep(0.5);

  group('List Runs', () => {
    const res = http.get(`${baseUrl}/v1/runs?workspace_id=${workspaceId}`);
    check(res, {
      'runs status is 200': (r) => r.status === 200,
      'runs response has items': (r) => {
        try {
          const body = JSON.parse(r.body);
          return Array.isArray(body.items);
        } catch {
          return false;
        }
      },
      'runs p99 < 500ms': (r) => r.timings.duration < 500,
    });
    errorRate.add(res.status !== 200);
    latencyP99.add(res.timings.duration);
    requestsPerSecond.add(1);
  });

  sleep(0.5);

  group('Metrics Endpoint', () => {
    const res = http.get(`${baseUrl}/metrics`);
    check(res, {
      'metrics status is 200': (r) => r.status === 200,
      'metrics has prometheus format': (r) => r.body.includes('platform_api_http_requests_total'),
    });
  });

  sleep(1);
}

export function teardown(data) {
  console.log('Load test completed');
}
