#!/usr/bin/env python3
"""G4 (Student A): Python simulator of four throttling algorithms on one
traffic trace. The token-bucket accept pattern is compared with the live Kong
plugin by tests/fragments/verify_token_bucket.py.

Example:
  python scripts/token_bucket_sim.py --capacity 5 --refill 1 --count 12 --gap 0
  python scripts/token_bucket_sim.py --capacity 50 --refill 10 --count 60 --gap 0.05
"""

from __future__ import annotations

import argparse
import math


def fixed_window(limit: int, window: float, arrivals: list[float]) -> list[int]:
    seen: dict[int, int] = {}
    result = []
    for t in arrivals:
        bucket = math.floor(t / window)
        used = seen.get(bucket, 0)
        if used < limit:
            seen[bucket] = used + 1
            result.append(1)
        else:
            result.append(0)
    return result


def sliding_window(limit: int, window: float, arrivals: list[float]) -> list[int]:
    accepted: list[float] = []
    result = []
    for t in arrivals:
        accepted = [s for s in accepted if s > t - window]
        if len(accepted) < limit:
            accepted.append(t)
            result.append(1)
        else:
            result.append(0)
    return result


def token_bucket(capacity: float, refill_rate: float, arrivals: list[float]) -> list[int]:
    tokens = float(capacity)
    last = arrivals[0] if arrivals else 0.0
    result = []
    for t in arrivals:
        tokens = min(capacity, tokens + max(0.0, t - last) * refill_rate)
        last = t
        if tokens >= 1:
            tokens -= 1
            result.append(1)
        else:
            result.append(0)
    return result


def leaky_bucket(capacity: float, rate: float, arrivals: list[float]) -> list[int]:
    water = 0.0
    last = arrivals[0] if arrivals else 0.0
    result = []
    for t in arrivals:
        water = max(0.0, water - max(0.0, t - last) * rate)
        last = t
        if water < capacity:
            water += 1
            result.append(1)
        else:
            result.append(0)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capacity", type=float, default=5)
    parser.add_argument("--refill", type=float, default=1)
    parser.add_argument("--count", type=int, default=12)
    parser.add_argument("--gap", type=float, default=0.0)
    parser.add_argument("--window", type=float, default=60.0)
    parser.add_argument("--pattern", action="store_true", help="print only the token-bucket 0/1 pattern")
    args = parser.parse_args()

    arrivals = [i * args.gap for i in range(args.count)]
    token = token_bucket(args.capacity, args.refill, arrivals)

    if args.pattern:
        print("".join(map(str, token)))
        return 0

    print(f"trace: {args.count} requests, gap {args.gap}s, capacity {args.capacity}, refill {args.refill}/s")
    for name, values in [
        ("fixed window", fixed_window(int(args.capacity), args.window, arrivals)),
        ("sliding window", sliding_window(int(args.capacity), args.window, arrivals)),
        ("token bucket", token),
        ("leaky bucket", leaky_bucket(args.capacity, args.refill, arrivals)),
    ]:
        print(f"  {name:14s} accepted {sum(values):3d}/{args.count}  pattern={''.join(map(str, values))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
