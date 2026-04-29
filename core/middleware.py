import time
import logging

logger = logging.getLogger("insighta.requests")


class RequestLoggingMiddleware:
    """Logs method, endpoint, status code, and response time for every request."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.monotonic()
        response = self.get_response(request)
        duration_ms = round((time.monotonic() - start) * 1000, 2)

        logger.info(
            "%s %s %s %.2fms",
            request.method,
            request.path,
            response.status_code,
            duration_ms,
        )
        return response
