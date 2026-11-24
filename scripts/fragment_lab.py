#!/usr/bin/env python3
"""Independent-wave plugin fragment lab.

Builds a DB-less Kong declarative config by concatenating tests/fragments/
base-mock.yml with one or more kong/fragments/*.yml files, then either parses
it with the real Kong 3.9.1 binary or boots a throwaway Kong container that
proxies to the Gate 0 mock upstream. This keeps the live kong.yml untouched
until Layer 2 (I3) merges the fragments.

Examples (PowerShell):
  python scripts/fragment_lab.py parse kong/fragments/10-auth.yml
  python scripts/fragment_lab.py up   kong/fragments/10-auth.yml --name lab-auth
  python scripts/fragment_lab.py down lab-auth
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "tests" / "fragments" / "base-mock.yml"
WORK = Path(os.environ.get("TEMP", "/tmp")) / "opencode" / "fragment-lab"
NETWORK = "fintech-gateway"
IMAGE = os.environ.get("KONG_IMAGE", "kong:3.9.1")


SCALAR_KEYS = {"_format_version", "_transform"}


def _sections(text: str) -> dict[str, list[str]]:
    """Split a Kong declarative YAML file into its top-level sections.

    We only need top-level key merging; keeping the original text avoids a
    third-party YAML dependency and preserves Kong's certified field names.
    """
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in text.splitlines():
        if line and not line[0].isspace() and not line.lstrip().startswith("#"):
            key = line.split(":", 1)[0].strip()
            if key and ":" in line:
                current = key
                sections.setdefault(current, [])
                sections[current].append(line)
                continue
        if current is not None:
            sections[current].append(line)
    return sections


def build(fragments: list[str]) -> Path:
    """Merge base + fragments by top-level YAML key.

    Fragments legitimately share keys (e.g. `plugins`); plain concatenation
    would leave duplicate YAML keys and Kong would silently keep only the
    last one, dropping earlier plugins. This stdlib merger appends the bodies
    of repeated list sections under a single header, so every plugin survives.
    """
    WORK.mkdir(parents=True, exist_ok=True)
    merged: dict[str, list[str]] = _sections(BASE.read_text(encoding="utf-8"))
    sources = [
        (Path(raw) if Path(raw).is_absolute() else ROOT / raw) for raw in fragments
    ]
    for path in sources:
        for key, lines in _sections(path.read_text(encoding="utf-8")).items():
            if key in merged and key not in SCALAR_KEYS:
                merged[key].append("")
                merged[key].extend(lines[1:])
            elif key not in merged:
                merged[key] = lines

    rendered: list[str] = []
    for lines in merged.values():
        rendered.extend(lines)
        rendered.append("")
    target = WORK / "kong.yml"
    target.write_text("\n".join(rendered).rstrip() + "\n", encoding="utf-8")
    return target


def parse(fragments: list[str]) -> int:
    target = build(fragments)
    print(f"config: {target}")
    result = subprocess.run(
        [
            "docker", "run", "--rm",
            "-e", "KONG_DATABASE=off",
            "-e", "KONG_PLUGINS=bundled,token-bucket",
            "-v", f"{WORK}:/etc/kong:ro",
            "-v", f"{ROOT / 'kong' / 'plugins' / 'token-bucket'}:/usr/local/share/lua/5.1/kong/plugins/token-bucket:ro",
            IMAGE, "kong", "config", "parse", "/etc/kong/kong.yml",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    return result.returncode


def up(args: argparse.Namespace) -> int:
    target = build(args.fragment)
    cmd = [
        "docker", "run", "-d", "--rm",
        "--name", args.name,
        "--network", NETWORK,
        "-v", f"{WORK}:/etc/kong:ro",
        "-e", "KONG_DATABASE=off",
        "-e", "KONG_DECLARATIVE_CONFIG=/etc/kong/kong.yml",
        "-e", "KONG_PROXY_LISTEN=0.0.0.0:8000, 0.0.0.0:8443 ssl",
        "-e", "KONG_ADMIN_LISTEN=0.0.0.0:8001",
        "-e", "KONG_STATUS_LISTEN=0.0.0.0:8100",
        "-e", f"KONG_PLUGINS={args.plugins}",
        "-e", f"KONG_NGINX_HTTP_LUA_SHARED_DICT={args.shared_dict}",
        "-e", "KONG_LOG_LEVEL=notice",
    ]
    if args.plugin_mount:
        plugin_dir = Path(args.plugin_mount)
        if not plugin_dir.is_absolute():
            plugin_dir = ROOT / plugin_dir
        cmd += [
            "-v",
            f"{plugin_dir}:/usr/local/share/lua/5.1/kong/plugins/token-bucket:ro",
        ]
    if args.log_mount:
        log_dir = Path(args.log_mount)
        log_dir.mkdir(parents=True, exist_ok=True)
        cmd += ["-v", f"{log_dir}:/var/log/kong"]
    cmd += [
        "-p", f"{args.proxy}:8000",
        "-p", f"{args.admin}:8001",
        "-p", f"{args.status}:8100",
        "-p", f"{args.tls}:8443",
        IMAGE,
    ]
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        return result.returncode
    print(result.stdout.strip())
    url = f"http://127.0.0.1:{args.admin}/services"
    for _ in range(60):
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status == 200:
                    print(f"ready: proxy=127.0.0.1:{args.proxy} admin=127.0.0.1:{args.admin} tls=127.0.0.1:{args.tls}")
                    return 0
        except (urllib.error.URLError, TimeoutError, OSError):
            time.sleep(1)
    print("lab did not become ready in 60 s", file=sys.stderr)
    subprocess.run(["docker", "logs", args.name], cwd=ROOT)
    return 1


def down(name: str) -> int:
    return subprocess.run(["docker", "rm", "-f", name], cwd=ROOT).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)

    p_parse = sub.add_parser("parse", help="run kong config parse on base + fragments")
    p_parse.add_argument("fragment", nargs="+")

    p_up = sub.add_parser("up", help="boot a throwaway Kong with base + fragments")
    p_up.add_argument("fragment", nargs="+")
    p_up.add_argument("--name", default="fintech-fragment-lab")
    p_up.add_argument("--proxy", type=int, default=18000)
    p_up.add_argument("--admin", type=int, default=18001)
    p_up.add_argument("--status", type=int, default=18100)
    p_up.add_argument("--tls", type=int, default=18443)
    p_up.add_argument("--plugins", default="bundled")
    p_up.add_argument("--shared-dict", default="token_bucket 1m")
    p_up.add_argument(
        "--plugin-mount",
        default=None,
        help="host dir with schema.lua/handler.lua, mounted at the plugin path",
    )
    p_up.add_argument(
        "--log-mount",
        default=None,
        help="host dir mounted at /var/log/kong for file-log evidence",
    )

    p_down = sub.add_parser("down", help="remove a lab container")
    p_down.add_argument("name")

    args = parser.parse_args()
    if args.action == "parse":
        return parse(args.fragment)
    if args.action == "up":
        return up(args)
    if args.action == "down":
        return down(args.name)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
