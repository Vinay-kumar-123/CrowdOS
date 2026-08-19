import time
import uuid
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.logger import logger


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to generate/propagate X-Request-ID, measure request latency,
    and log structured request metrics.
    """
    async def dispatch(self, request: Request, call_next) -> Response:
        # Extract or generate request_id
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id

        start_time = time.perf_counter()
        try:
            response: Response = await call_next(request)
        except Exception as exc:
            process_time = (time.perf_counter() - start_time) * 1000.0
            logger.error(
                f"[{request_id}] {request.method} {request.url.path} - "
                f"FAILED with unhandled exception: {exc} - Duration: {process_time:.2f}ms"
            )
            raise exc

        process_time = (time.perf_counter() - start_time) * 1000.0
        response.headers["X-Request-ID"] = request_id

        logger.info(
            f"[{request_id}] {request.method} {request.url.path} - "
            f"Status: {response.status_code} - Duration: {process_time:.2f}ms"
        )
        return response
