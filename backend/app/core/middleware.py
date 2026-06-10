import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import get_logger, new_request_id, request_id_ctx, user_id_ctx

logger = get_logger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attaches a request id to every request/response and emits a structured access log."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-ID", new_request_id())
        request_id_token = request_id_ctx.set(request_id)
        user_id_token = user_id_ctx.set("-")

        start = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            request_id_ctx.reset(request_id_token)
            user_id_ctx.reset(user_id_token)

        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request_completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        return response
