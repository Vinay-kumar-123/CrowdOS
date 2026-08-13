import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.logger import logger


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log HTTP request execution duration and status codes.
    """
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        process_time = (time.time() - start_time) * 1000
        logger.info(
            f"{request.method} {request.url.path} - "
            f"Status: {response.status_code} - Duration: {process_time:.2f}ms"
        )
        return response
