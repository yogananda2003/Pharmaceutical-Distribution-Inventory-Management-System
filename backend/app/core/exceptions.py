class AppError(Exception):
    """Base class for application errors that map to a known HTTP status + message."""

    status_code: int = 400

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class NotFoundError(AppError):
    status_code = 404


class ValidationError(AppError):
    status_code = 422


class ConflictError(AppError):
    status_code = 409


class AuthenticationError(AppError):
    status_code = 401


class AuthorizationError(AppError):
    status_code = 403
