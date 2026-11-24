"""Gateway header middleware for the Advisor (V3.1).

Mirrors the Django services: identify the serving replica and echo Kong's
correlation/consumer headers so Kong, the service log and the response can be
correlated (evidence 08 at Layer 2).
"""

import socket
import uuid

from starlette.middleware.base import BaseHTTPMiddleware


class GatewayHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request_id = request.headers.get("kong-request-id", "")
        consumer = request.headers.get("x-consumer-username", "")

        request.state.kong_request_id = request_id or uuid.uuid4().hex
        request.state.kong_consumer = consumer

        response = await call_next(request)

        response.headers["X-Served-By"] = socket.gethostname()
        if request_id:
            response.headers["Kong-Request-ID"] = request_id
        if consumer:
            response.headers["X-Consumer-Username"] = consumer
        return response
