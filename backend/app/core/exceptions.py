from fastapi import HTTPException, status


class CrowdOSException(HTTPException):
    def __init__(self, detail: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        super().__init__(status_code=status_code, detail=detail)


class DatabaseConnectionError(CrowdOSException):
    def __init__(self, detail: str = "Database connection failed"):
        super().__init__(detail=detail, status_code=status.HTTP_503_SERVICE_UNAVAILABLE)


class NotFoundException(CrowdOSException):
    def __init__(self, detail: str = "Requested resource not found"):
        super().__init__(detail=detail, status_code=status.HTTP_404_NOT_FOUND)


class ConflictException(CrowdOSException):
    def __init__(self, detail: str = "State transition conflict"):
        super().__init__(detail=detail, status_code=status.HTTP_409_CONFLICT)


class ValidationException(CrowdOSException):
    def __init__(self, detail: str = "Validation error"):
        super().__init__(detail=detail, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)


class EngineUnavailableException(CrowdOSException):
    def __init__(self, detail: str = "AI Engine is unavailable or uninitialized"):
        super().__init__(detail=detail, status_code=status.HTTP_503_SERVICE_UNAVAILABLE)


class AuthenticationException(CrowdOSException):
    def __init__(self, detail: str = "Authentication failed"):
        super().__init__(detail=detail, status_code=status.HTTP_401_UNAUTHORIZED)


class AuthorizationException(CrowdOSException):
    def __init__(self, detail: str = "Forbidden: Insufficient privileges"):
        super().__init__(detail=detail, status_code=status.HTTP_403_FORBIDDEN)


class RateLimitException(CrowdOSException):
    def __init__(self, detail: str = "Too many requests. Please try again later."):
        super().__init__(detail=detail, status_code=status.HTTP_429_TOO_MANY_REQUESTS)
