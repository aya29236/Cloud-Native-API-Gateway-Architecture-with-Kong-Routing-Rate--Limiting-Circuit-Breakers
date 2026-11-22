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
and [handler](https://github.com/Kong/kong/blob/3.9.1/kong/plugins/rate-limiting/handler.lua),
and confirmed in the live test below: ten free-consumer requests returned 200,
the next returned 429 with `Retry-After: 3`, and a premium request returned
200 with a 100/minute limit header. A premium `/fail` request returned 500
with its remaining quota reduced on the following request, confirming that
upstream error responses still consume a request in the window.

## G6: request/response behavior

`30-transform.yml` applies to `mock-route`:

- `correlation-id` generates and echoes `Kong-Request-ID`.
- `request-transformer` adds `X-Gateway: fintech-api-gateway` and removes the
  incoming `X-Debug` header. The config parses, but the live behavior remains
  unverified because the existing mock's POST response echoes only
  `Content-Type` and `Kong-Request-ID`, not arbitrary request headers.
- `cors` allows `http://localhost:3000`, handles preflight without proxying the
  `OPTIONS` request upstream, and exposes the correlation ID, rate-limit, and
  retry headers.
- `request-size-limiting` rejected a 2,000,000-byte body with HTTP 413. A
  1,000,001-byte body reached the mock and returned 400, so the exact effective
  one-megabyte boundary was not established.

## Validation status

On **2026-11-22**, both temporary configs parsed successfully with the
`kong:3.9.1` image pinned in `.env.example`. The live checks used only Kong
3.9.1 and the existing mock-upstream, with temporary test keys that were not
committed. Status below is limited to observed behavior:

| Fragment/plugin | Configured options | Status |
|---|---|---|
| `rate-limiting` | `consumer` username reference, `minute`, `limit_by`, `policy`, `hide_client_headers` | **VERIFIED on kong:3.9.1 (2026-11-22)** |
| `correlation-id` | `route`, `header_name`, `generator`, `echo_downstream` | **VERIFIED on kong:3.9.1 (2026-11-22)** |
| `request-transformer` | `route`, `add.headers`, `remove.headers` | **UNVERIFIED on kong:3.9.1** |
| `cors` | `route`, `origins`, `methods`, `headers`, `exposed_headers`, `preflight_continue` | **VERIFIED on kong:3.9.1 (2026-11-22)** |
| `request-size-limiting` | `route`, `allowed_payload_size`, `size_unit` | **VERIFIED on kong:3.9.1 (2026-11-22), for a 2,000,000-byte request; exact boundary unverified** |

`scripts/kong_parse_fragments.ps1` parses both fragments in temporary DB-less
configs. The POSIX counterpart is provided for Unix-like environments.
`loadtests/README.md` records the live T1a run.

## Integration confirmations

- Confirm with G2 that the consumer usernames are exactly `fintech-free` and
  `fintech-premium`.
- Confirm with I3 that `mock-route` is the intended route reference for G6.
- Confirm the browser origin (currently the local-development value
  `http://localhost:3000`) and the API-key header name. The Locust scenario
  accepts the API-key header name and secret only through environment variables.
- Provide an upstream/header-echo test endpoint if the team needs live
  confirmation of `X-Gateway` insertion and `X-Debug` removal.
