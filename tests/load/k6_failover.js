// Layer 3 / Step 3: concurrent Kong load for the replica-offline chaos test.
// Run with: docker compose --profile load run --rm k6
// A low rate keeps the premium key under the frozen 100/min G3 limit, so any
// 429/5xx observed during the test is a real failover problem, not a limit.

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Counter } from 'k6/metrics';

const servedBy = new Counter('served_by');

const BASE_URL = __ENV.BASE_URL || 'http://127.0.0.1:8000';
const APIKEY = __ENV.APIKEY || 'premium-demo-key';

export const options = {
  vus: Number(__ENV.VUS || 2),
  duration: __ENV.DURATION || '45s',
  thresholds: {
    http_req_failed: ['rate<0.01'],
    checks: ['rate>0.99'],
  },
};

export default function () {
  const response = http.get(`${BASE_URL}/api/accounts/health`, {
    headers: { apikey: APIKEY },
    tags: { chaos_test: 'accounts-replica-offline' },
  });

  check(response, {
    'accounts health is 200 during failover': (r) => r.status === 200,
    'served-by header is present': (r) =>
      Boolean(r.headers['X-Served-By'] || r.headers['x-served-by']),
  });

  const served =
    response.headers['X-Served-By'] || response.headers['x-served-by'] || 'none';
  servedBy.add(1, { served_by: served.toLowerCase() });

  sleep(1.5);
}
