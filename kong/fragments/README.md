# Kong configuration fragments

These are additions for the later merge into `kong/kong.yml`; they intentionally
do not modify the active declarative config. The project currently uses
`kong:3.9.1`, DB-less mode, proxy port `8000`, and the `mock-route` route at
`/mock` (which strips that prefix before forwarding to `mock-upstream`).

## G3: consumer rate limits

`20-ratelimit.yml` attaches Kong's OSS `rate-limiting` plugin to the existing
`fintech-free` and `fintech-premium` consumers by their username references
only. G2 owns those
consumer entities and credentials; this fragment does not define either.
Requests are limited to **10/minute** for `fintech-free` and **100/minute** for
`fintech-premium`, with `limit_by: consumer`. `policy: local` keeps counters
locally on each Kong node rather than coordinating them across nodes.

The Kong 3.9.1 rate-limiting plugin counts requests that reach its access phase
within each configured window for the selected identifier; its handler does not
filter by the eventual upstream response status. Once the limit is exhausted,
it rejects further requests with 429 and returns `Retry-After`. With
`hide_client_headers: false`, the plugin also emits its `X-RateLimit-*` and
standard `RateLimit-*` headers. These descriptions were checked against the
[Kong 3.9.1 plugin schema](https://github.com/Kong/kong/blob/3.9.1/kong/plugins/rate-limiting/schema.lua)
and [handler](https://github.com/Kong/kong/blob/3.9.1/kong/plugins/rate-limiting/handler.lua);
they have **not** been confirmed on a running container in this environment.

## G6: request/response behavior

`30-transform.yml` applies to `mock-route`:

- `correlation-id` generates and echoes `Kong-Request-ID`.
- `request-transformer` adds `X-Gateway: fintech-api-gateway` and removes the
  incoming `X-Debug` header.
- `cors` allows `http://localhost:3000`, handles preflight without proxying the
  `OPTIONS` request upstream, and exposes the correlation ID, rate-limit, and
  retry headers.
- `request-size-limiting` rejects request bodies larger than 1 megabyte with
  HTTP 413.

## Validation status

The configured options below are **UNVERIFIED on kong:3.9.1** because the Docker
CLI is installed here but its daemon is unavailable. The fragment tests check
the YAML structure and intended options; they do not prove Kong accepts or
executes them. Use `scripts/kong_parse_fragments.ps1` or
`scripts/kong_parse_fragments.sh` to parse both temporary merged configs with
the image in `.env.example`.

| Fragment/plugin | Configured options | Status |
|---|---|---|
| `rate-limiting` | `consumer` username reference, `minute`, `limit_by`, `policy`, `hide_client_headers` | **UNVERIFIED on kong:3.9.1** |
| `correlation-id` | `route.name`, `header_name`, `generator`, `echo_downstream` | **UNVERIFIED on kong:3.9.1** |
| `request-transformer` | `route.name`, `add.headers`, `remove.headers` | **UNVERIFIED on kong:3.9.1** |
| `cors` | `route.name`, `origins`, `methods`, `headers`, `exposed_headers`, `preflight_continue` | **UNVERIFIED on kong:3.9.1** |
| `request-size-limiting` | `route.name`, `allowed_payload_size`, `size_unit` | **UNVERIFIED on kong:3.9.1** |

No live burst, correlation, transformation, CORS, or oversized-request checks
were run here. `loadtests/README.md` documents the local mock-upstream fallback
for T1a.

## Integration confirmations

- Confirm with G2 that the consumer usernames are exactly `fintech-free` and
  `fintech-premium`.
- Confirm with I3 that `mock-route` is the intended route reference for G6.
- Confirm the browser origin (currently the local-development value
  `http://localhost:3000`) and the API-key header name. The Locust scenario
  accepts the API-key header name and secret only through environment variables.
