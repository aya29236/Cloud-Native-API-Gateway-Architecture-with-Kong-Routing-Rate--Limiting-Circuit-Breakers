#!/usr/bin/env python3
"""Parse each fragment by explicitly merging it into kong/kong.yml.

No YAML parser and no generated temp config are used. This script writes the
combined sections into the real declarative config, runs the real Kong 3.9.1
parser through `fragment_lab.py parse`, then restores the Layer 1 baseline.

Usage:
  python scripts/verify_fragments.py                         # parse every scenario
  python scripts/verify_fragments.py kong/fragments/10-auth.yml  # write one explicit merge
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "tests" / "fragments" / "base-mock.yml"
CONFIG = ROOT / "kong" / "kong.yml"
FRAGMENT_DIR = ROOT / "kong" / "fragments"
SCALAR_KEYS = {"_format_version", "_transform"}


def sections(text: str) -> dict[str, list[str]]:
    """Split a Kong YAML file into top-level sections without a YAML library."""
    result: dict[str, list[str]] = {}
    current: str | None = None
    for line in text.splitlines():
        if line and not line[0].isspace() and not line.lstrip().startswith("#"):
            key = line.split(":", 1)[0].strip()
            if key and ":" in line:
                current = key
                result.setdefault(current, [])
                result[current].append(line)
                continue
        if current is not None:
            result[current].append(line)
    return result


def explicit_merge(fragments: list[Path]) -> str:
    """Return base-mock plus the selected fragments under one header per key."""
    merged = sections(BASE.read_text(encoding="utf-8"))
    for path in fragments:
        for key, lines in sections(path.read_text(encoding="utf-8")).items():
            if key in merged and key not in SCALAR_KEYS:
                merged[key].append("")
                merged[key].extend(lines[1:])
            elif key not in merged:
                merged[key] = lines
    rendered: list[str] = []
    for lines in merged.values():
        rendered.extend(lines)
        rendered.append("")
    return "\n".join(rendered).rstrip() + "\n"


def parse_current_config(label: str) -> int:
    print(f"\nexplicit merge into kong/kong.yml: {label}", flush=True)
    result = subprocess.run(
        [sys.executable, "scripts/fragment_lab.py", "parse"],
        cwd=ROOT,
        text=True,
    )
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "fragments",
        nargs="*",
        help="write these fragments explicitly into kong/kong.yml instead of parsing all scenarios",
    )
    args = parser.parse_args()

    if args.fragments:
        selected: list[Path] = []
        for raw in args.fragments:
            path = Path(raw)
            if not path.is_absolute():
                path = ROOT / path
            if not path.is_file():
                print(f"missing fragment: {path}", file=sys.stderr)
                return 1
            selected.append(path)
        CONFIG.write_text(explicit_merge(selected), encoding="utf-8")
        print(f"wrote explicit merge into {CONFIG}: {', '.join(args.fragments)}")
        print("restore the Layer 1 baseline with: git checkout -- kong/kong.yml")
        return 0

    original = CONFIG.read_bytes()
    fragments = sorted(FRAGMENT_DIR.glob("*.yml"))
    if not fragments:
        print("no fragments found", file=sys.stderr)
        return 1

    by_name = {path.name: path for path in fragments}
    required = [
        "10-auth.yml",
        "20-ratelimit.yml",
        "25-tokenbucket.yml",
        "30-transform.yml",
        "40-telemetry.yml",
        "50-tls.yml",
    ]
    missing = [name for name in required if name not in by_name]
    if missing:
        print(f"missing fragments: {', '.join(missing)}", file=sys.stderr)
        return 1
    auth = by_name["10-auth.yml"]

    failures = 0
    try:
        scenarios: list[tuple[str, list[Path]]] = [
            ("10-auth.yml", [auth]),
            ("10-auth.yml + 20-ratelimit.yml", [auth, by_name["20-ratelimit.yml"]]),
            ("10-auth.yml + 25-tokenbucket.yml", [auth, by_name["25-tokenbucket.yml"]]),
            ("10-auth.yml + 30-transform.yml", [auth, by_name["30-transform.yml"]]),
            ("40-telemetry.yml", [by_name["40-telemetry.yml"]]),
            ("50-tls.yml", [by_name["50-tls.yml"]]),
            ("ALL fragments combined", fragments),
        ]

        for label, selected in scenarios:
            CONFIG.write_text(explicit_merge(selected), encoding="utf-8")
            if parse_current_config(label) != 0:
                failures += 1
    finally:
        CONFIG.write_bytes(original)

    if failures:
        print(f"\n{failures} explicit-merge parse scenario(s) failed", file=sys.stderr)
        return 1
    print(f"\n{len(scenarios)} explicit-merge parse scenarios passed; kong.yml restored")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
