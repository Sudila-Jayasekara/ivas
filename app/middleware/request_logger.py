import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("ivas.request")


class RequestLoggerMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        start = time.perf_counter()
        response: Response = await call_next(request)
        latency_ms = (time.perf_counter() - start) * 1000

        response.headers["X-Request-ID"] = request_id

        status = response.status_code
        log_data = {
            "request_id": request_id,
            "method": request.method,
            "path": str(request.url.path),
            "query": str(request.url.query),
            "status": status,
            "latency_ms": round(latency_ms, 2),
            "client_ip": request.client.host if request.client else "",
        }

        if status >= 500:
            logger.error("Server error %s", log_data)
        elif status >= 400:
            logger.warning("Client error %s", log_data)
        else:
            logger.info("Request completed %s", log_data)

        return response
