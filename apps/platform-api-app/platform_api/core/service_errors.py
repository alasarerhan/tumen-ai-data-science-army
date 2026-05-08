from __future__ import annotations

from fastapi import HTTPException


class ServiceError(HTTPException):
    """Base exception for service-layer failures."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(status_code=status_code, detail=detail)


class ValidationError(ServiceError):
    def __init__(self, detail: str) -> None:
        super().__init__(status_code=400, detail=detail)


class UnauthorizedError(ServiceError):
    def __init__(self, detail: str) -> None:
        super().__init__(status_code=401, detail=detail)


class ForbiddenError(ServiceError):
    def __init__(self, detail: str) -> None:
        super().__init__(status_code=403, detail=detail)


class NotFoundError(ServiceError):
    def __init__(self, detail: str) -> None:
        super().__init__(status_code=404, detail=detail)


class ConflictError(ServiceError):
    def __init__(self, detail: str) -> None:
        super().__init__(status_code=409, detail=detail)


class UnprocessableEntityError(ServiceError):
    def __init__(self, detail: str) -> None:
        super().__init__(status_code=422, detail=detail)


class RateLimitExceededError(ServiceError):
    def __init__(self, detail: str) -> None:
        super().__init__(status_code=429, detail=detail)


class UpstreamUnavailableError(ServiceError):
    def __init__(self, detail: str) -> None:
        super().__init__(status_code=502, detail=detail)
