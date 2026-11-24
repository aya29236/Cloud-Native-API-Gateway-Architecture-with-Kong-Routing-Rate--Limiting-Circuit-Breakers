-- G4 (Student A): custom Kong 3.9 token-bucket plugin.
-- State lives in a dedicated shared dict declared with
-- KONG_NGINX_HTTP_LUA_SHARED_DICT="token_bucket 1m".
-- PRIORITY 750 is below key-auth (1250) and jwt (1000), so unauthenticated
-- requests never consume tokens and the consumer id is available.

local kong = kong
local math = math

local TokenBucket = {
  VERSION = "0.1.0",
  PRIORITY = 750,
}

local DICT = "token_bucket"

function TokenBucket:access(config)
  local dict = ngx.shared[DICT]
  if not dict then
    kong.log.err("token-bucket: shared dict is missing; set KONG_NGINX_HTTP_LUA_SHARED_DICT=\"token_bucket 1m\"")
    return
  end

  local consumer = kong.client.get_consumer()
  local identity = (consumer and consumer.id) or kong.client.get_ip()
  local key = string.format("%s|%s|%s", identity, config.capacity, config.refill_rate)

  -- Nginx caches the current time per worker; different workers can report
  -- values seconds apart. Refresh it so refill uses the real wall clock.
  ngx.update_time()
  local now = ngx.now()
  local tokens, last
  -- ngx.shared.DICT:get() returns (value, flags), not an exptime, so the
  -- refill timestamp is stored inside the value as "tokens:last_seen".
  local raw = dict:get(key)
  if raw then
    local token_text, last_text = string.match(raw, "^([^:]+):(.+)$")
    tokens = tonumber(token_text) or config.capacity
    last = tonumber(last_text) or now
    local elapsed = math.max(0, now - last)
    tokens = math.min(config.capacity, tokens + elapsed * config.refill_rate)
  else
    tokens = config.capacity
  end

  if tokens < 1 then
    local retry = math.max(1, math.ceil((1 - tokens) / config.refill_rate))
    kong.response.set_header("X-Token-Bucket-Remaining", "0")
    kong.response.set_header("Retry-After", tostring(retry))
    return kong.response.exit(429, { message = "Token bucket exhausted" })
  end

  tokens = tokens - 1
  dict:set(key, string.format("%.6f:%.6f", tokens, now))
  kong.response.set_header("X-Token-Bucket-Remaining", tostring(math.floor(tokens)))
end

return TokenBucket
