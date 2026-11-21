import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

PORT = int(os.getenv("PORT", "8080"))

class Handler(BaseHTTPRequestHandler):
    def _send(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Served-By", os.getenv("HOSTNAME", "mock-upstream"))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/health":
            return self._send(200, {"status": "healthy"})
        if path == "/fail":
            return self._send(500, {"error": "synthetic_failure"})
        if path == "/slow":
            time.sleep(3)
            return self._send(200, {"status": "slow_response", "delay_seconds": 3})
        if path == "/echo":
            return self._send(200, {"method": "GET", "path": path})
        return self._send(404, {"error": "not_found", "path": path})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b""
        try:
            payload = json.loads(raw.decode("utf-8")) if raw else None
        except (UnicodeDecodeError, json.JSONDecodeError):
            return self._send(400, {"error": "invalid_json"})
        return self._send(200, {
            "method": "POST",
            "path": urlparse(self.path).path,
            "received": payload,
            "headers": {
                "content_type": self.headers.get("Content-Type"),
                "kong_request_id": self.headers.get("Kong-Request-ID")
            }
        })

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args), flush=True)

if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"mock-upstream listening on {PORT}", flush=True)
    server.serve_forever()