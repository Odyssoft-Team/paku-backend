from fastapi import status


class APIError(Exception):
    """Base API error class."""
    
    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    ):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class NotFoundError(APIError):
    """Resource not found error."""
    
    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, status.HTTP_404_NOT_FOUND)


class ValidationError(APIError):
    """Validation error."""
    
    def __init__(self, message: str = "Validation failed"):
        super().__init__(message, status.HTTP_400_BAD_REQUEST)


class UnauthorizedError(APIError):
    """Unauthorized access error."""
    
    def __init__(self, message: str = "Unauthorized"):
        super().__init__(message, status.HTTP_401_UNAUTHORIZED)


class ForbiddenError(APIError):
    """Forbidden access error."""
    
    def __init__(self, message: str = "Forbidden"):
        super().__init__(message, status.HTTP_403_FORBIDDEN)
