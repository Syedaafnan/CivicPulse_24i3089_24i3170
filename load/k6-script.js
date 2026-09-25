// Load generator for the HPA scale-out demo and the zero-downtime rollout demo.
//   k6 run -e BASE_URL=http://civicpulse.local load/k6-script.js                 # ramp (HPA)
//   k6 run -e BASE_URL=http://civicpulse.local -e MODE=steady load/k6-script.js  # rollout demo
// Reads only (list + stats + one complaint): POSTs are rate-limited per IP by design,
// so a single load generator would mostly measure 429s, not capacity.
import http from "k6/http";
import { check, sleep } from "k6";

const BASE = __ENV.BASE_URL || "http://civicpulse.local";
const MODE = __ENV.MODE || "ramp";

export const options =
  MODE === "steady"
    ? {
        scenarios: { steady: { executor: "constant-arrival-rate", rate: 20, timeUnit: "1s", duration: "3m", preAllocatedVUs: 20 } },
        thresholds: { http_req_failed: ["rate==0"] }, // zero failed requests during `kubectl set image`
      }
    : {
        stages: [
          { duration: "30s", target: 10 },
          { duration: "1m", target: 60 },
          { duration: "3m", target: 60 },
          { duration: "1m", target: 0 },
        ],
        thresholds: { http_req_duration: ["p(95)<2000"], http_req_failed: ["rate<0.01"] },
      };

export default function () {
  const page = 1 + Math.floor(Math.random() * 3);
  const list = http.get(`${BASE}/api/complaints?page=${page}&page_size=100`, { tags: { name: "list" } });
  check(list, { "list 200": (r) => r.status === 200 });

  const stats = http.get(`${BASE}/api/stats`, { tags: { name: "stats" } });
  check(stats, { "stats 200": (r) => r.status === 200 });

  if (list.status === 200) {
    const items = list.json("items");
    if (items && items.length) {
      const one = http.get(`${BASE}/api/complaints/${items[0].id}`, { tags: { name: "get" } });
      check(one, { "get 200": (r) => r.status === 200 });
    }
  }
  sleep(MODE === "steady" ? 0 : 0.2);
}
