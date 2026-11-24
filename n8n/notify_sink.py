"""Demo notification channel for M3 (M3.1).

Mimics the subset of the Telegram Bot API that the workflows use
(``POST /bot<token>/sendMessage``) so the fake-alert tests produce a visible,
reproducible channel message without real credentials. The URL is configurable
via ``TELEGRAM_API_BASE`` in n8n, so pointing it at the real Telegram API is a
one-variable change.

Runs on the stdlib only; logs each message to stdout (``docker compose logs
notify-sink``) which is the evidence artifact for evidence 14 at Layer 4.
"""

import json
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length).decode("utf-8", "replace")
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            body = {"raw": raw}

        text = body.get("text", "")
        stamp = datetime.now(timezone.utc).isoformat()
        print(
            f"[{stamp}] NOTIFICATION path={self.path} "
            f"chat_id={body.get('chat_id')!r} text={text!r}",
            flush=True,
        )

        out = json.dumps({"ok": True, "result": {"message_id": 1}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, fmt, *args):
        """Keep the log focused on notification payloads."""


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
