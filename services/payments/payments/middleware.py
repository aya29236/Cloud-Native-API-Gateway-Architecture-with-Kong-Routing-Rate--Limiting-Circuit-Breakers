"""Gateway header and logging middleware for Payments (V2.1).

Kong's JWT plugin authenticates the request and forwards X-Consumer-Username.
This middleware echoes the correlation/consumer headers and records which
container served the request, then writes one structured log line per request.
V2.3 will additionally persist the consumer on each Payment.
"""

import logging
import socket
import uuid

from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger("payments.gateway")


class GatewayHeadersMiddleware(MiddlewareMixin):
    def process_request(self, request):
        request.kong_request_id = request.headers.get("Kong-Request-ID", "")
        request.kong_consumer = request.headers.get("X-Consumer-Username", "")
        request.local_request_id = request.kong_request_id or uuid.uuid4().hex
        return None

    def process_response(self, request, response):
        served_by = socket.gethostname()
        response["X-Served-By"] = served_by

        request_id = getattr(request, "kong_request_id", "")
        if request_id:
            response["Kong-Request-ID"] = request_id

        consumer = getattr(request, "kong_consumer", "")
        if consumer:
            response["X-Consumer-Username"] = consumer

        logger.info(
            "method=%s path=%s status=%s served_by=%s request_id=%s consumer=%s",
            request.method,
            request.path,
            response.status_code,
            served_by,
            getattr(request, "local_request_id", "-"),
            consumer or "-",
        )
        return response
