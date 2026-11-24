#!/usr/bin/env python3
"""Run Kong 3.9.1 against the current explicit contents of kong/kong.yml.

There is deliberately no YAML merge logic here. To test a fragment, put its
sections into kong/kong.yml explicitly first, run this tool, then restore the
Layer 1 baseline. `scripts/verify_fragments.py` performs that explicit
write/parse/restore cycle for CI without any YAML parser library.

Examples (PowerShell):
  python scripts/fragment_lab.py parse
  python scripts/fragment_lab.py up   --name lab-auth
  python scripts/fragment_lab.py down lab-auth
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "kong" / "kong.yml"
KONG_DIR = ROOT / "kong"
PLUGIN_DIR = ROOT / "kong" / "plugins" / "token-bucket"
NETWORK = "fintech-gateway"
IMAGE = "kong:3.9.1"


def parse() -> int:
    """Parse the explicitly merged kong/kong.yml with the real Kong binary."""
    if not CONFIG.is_file():
        print(f"missing declarative config: {CONFIG}", file=sys.stderr)
        return 1
    print(f"config: {CONFIG}")
    result = subprocess.run(
        [
            "docker", "run", "--rm",
            "-e", "KONG_DATABASE=off",
            "-e", "KONG_PLUGINS=bundled,token-bucket",
            "-v", f"{KONG_DIR}:/etc/kong:ro",
            "-v", f"{PLUGIN_DIR}:/usr/local/share/lua/5.1/kong/plugins/token-bucket:ro",
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
    """Boot a throwaway Kong using the current kong/kong.yml."""
    if not CONFIG.is_file():
        print(f"missing declarative config: {CONFIG}", file=sys.stderr)
        return 1
    cmd = [
        "docker", "run", "-d", "--rm",
        "--name", args.name,
        "--network", NETWORK,
        "-v", f"{KONG_DIR}:/etc/kong:ro",
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
                    print(
                        f"ready: proxy=127.0.0.1:{args.proxy} "
                        f"admin=127.0.0.1:{args.admin} tls=127.0.0.1:{args.tls}"
                    )
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

    sub.add_parser("parse", help="parse the current kong/kong.yml with Kong 3.9.1")

    p_up = sub.add_parser("up", help="boot Kong from the current kong/kong.yml")
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
        return parse()
    if args.action == "up":
        return up(args)
    if args.action == "down":
        return down(args.name)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
