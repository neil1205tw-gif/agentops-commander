from fastapi import HTTPException, status

INVALID_TOKEN_DETAIL = "Invalid or expired token"  # noqa: S105 - response text


class InvalidTokenError(Exception):
    """Token verification failed. `reason` is a short category that is safe to log."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=INVALID_TOKEN_DETAIL,
        headers={"WWW-Authenticate": "Bearer"},
    )
