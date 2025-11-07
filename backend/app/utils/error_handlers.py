"""
Centralized error handling system for consistent, secure error responses.
Provides structured error handling with proper logging and user-friendly messages.
"""

import logging
import traceback
from datetime import datetime
from typing import Dict, Any, Optional
from flask import jsonify, current_app
from werkzeug.exceptions import HTTPException

logger = logging.getLogger(__name__)

class APIError(Exception):
    """Base API error class with status code and message."""

    def __init__(self, message: str, status_code: int = 500, payload: Optional[Dict[str, Any]] = None):
        super().__init__()
        self.message = message
        self.status_code = status_code
        self.payload = payload
        self.timestamp = datetime.utcnow().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for JSON response."""
        response = {
            'error': True,
            'message': self.message,
            'status_code': self.status_code,
            'timestamp': self.timestamp
        }

        if self.payload:
            response.update(self.payload)

        return response

class ValidationError(APIError):
    """Validation error (400)."""

    def __init__(self, message: str, field: Optional[str] = None, value: Optional[Any] = None):
        payload = {}
        if field:
            payload['field'] = field
        if value is not None:
            payload['value'] = str(value)

        super().__init__(message, 400, payload)

class AuthenticationError(APIError):
    """Authentication error (401)."""

    def __init__(self, message: str = "Authentication required"):
        super().__init__(message, 401)

class AuthorizationError(APIError):
    """Authorization error (403)."""

    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(message, 403)

class NotFoundError(APIError):
    """Resource not found error (404)."""

    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, 404)

class ConflictError(APIError):
    """Conflict error (409)."""

    def __init__(self, message: str = "Resource conflict"):
        super().__init__(message, 409)

class RateLimitError(APIError):
    """Rate limiting error (429)."""

    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(message, 429)

class DatabaseError(APIError):
    """Database error (500)."""

    def __init__(self, message: str = "Database operation failed"):
        super().__init__(message, 500)

class ExternalServiceError(APIError):
    """External service error (502)."""

    def __init__(self, service: str, message: str = "External service unavailable"):
        super().__init__(f"{service}: {message}", 502, {'service': service})

class TrainingError(APIError):
    """Model training error (500)."""

    def __init__(self, message: str, job_id: Optional[str] = None):
        payload = {}
        if job_id:
            payload['job_id'] = job_id
        super().__init__(f"Training error: {message}", 500, payload)

def handle_api_error(error: APIError) -> tuple:
    """Handle custom API errors."""
    # Log the error with context
    logger.error(f"API Error: {error.message}", extra={
        'status_code': error.status_code,
        'payload': error.payload,
        'traceback': traceback.format_exc() if current_app.debug else None
    })

    return jsonify(error.to_dict()), error.status_code

def handle_validation_error(error: ValidationError) -> tuple:
    """Handle validation errors with detailed field information."""
    logger.warning(f"Validation Error: {error.message}", extra={
        'field': error.payload.get('field'),
        'value': error.payload.get('value'),
        'traceback': traceback.format_exc() if current_app.debug else None
    })

    return jsonify(error.to_dict()), error.status_code

def handle_auth_error(error: AuthenticationError) -> tuple:
    """Handle authentication errors with security logging."""
    logger.warning(f"Authentication Error: {error.message}", extra={
        'ip_address': getattr(error, 'ip_address', None),
        'user_agent': getattr(error, 'user_agent', None)
    })

    response = error.to_dict()
    # Don't expose detailed auth errors in production
    if not current_app.debug:
        response['message'] = "Authentication failed"

    return jsonify(response), error.status_code

def handle_server_error(error: Exception) -> tuple:
    """Handle unexpected server errors."""
    # Log the full error for debugging
    logger.error(f"Server Error: {str(error)}", extra={
        'traceback': traceback.format_exc(),
        'error_type': type(error).__name__
    })

    # Return generic error message to avoid information leakage
    if current_app.debug:
        # In development, return detailed error information
        return jsonify({
            'error': True,
            'message': str(error),
            'status_code': 500,
            'timestamp': datetime.utcnow().isoformat(),
            'traceback': traceback.format_exc(),
            'error_type': type(error).__name__
        }), 500
    else:
        # In production, return generic error message
        return jsonify({
            'error': True,
            'message': "An internal server error occurred",
            'status_code': 500,
            'timestamp': datetime.utcnow().isoformat(),
            'error_id': None  # Could be enhanced with error tracking ID
        }), 500

def handle_http_exception(error: HTTPException) -> tuple:
    """Handle standard HTTP exceptions."""
    logger.warning(f"HTTP Exception: {error.name}", extra={
        'status_code': error.code,
        'description': error.description
    })

    return jsonify({
        'error': True,
        'message': error.description,
        'status_code': error.code,
        'timestamp': datetime.utcnow().isoformat()
    }), error.code

def handle_database_error(error: Exception) -> tuple:
    """Handle database-specific errors."""
    logger.error(f"Database Error: {str(error)}", extra={
        'traceback': traceback.format_exc(),
        'error_type': type(error).__name__
    })

    # Don't expose database details in production
    if current_app.debug:
        return jsonify({
            'error': True,
            'message': f"Database error: {str(error)}",
            'status_code': 500,
            'timestamp': datetime.utcnow().isoformat()
        }), 500
    else:
        return jsonify({
            'error': True,
            'message': "A database error occurred",
            'status_code': 500,
            'timestamp': datetime.utcnow().isoformat()
        }), 500

def register_error_handlers(app):
    """Register all error handlers with the Flask app."""

    # Custom API errors
    app.register_error_handler(APIError, handle_api_error)
    app.register_error_handler(ValidationError, handle_validation_error)
    app.register_error_handler(AuthenticationError, handle_auth_error)
    app.register_error_handler(AuthorizationError, handle_api_error)
    app.register_error_handler(NotFoundError, handle_api_error)
    app.register_error_handler(ConflictError, handle_api_error)
    app.register_error_handler(RateLimitError, handle_api_error)
    app.register_error_handler(DatabaseError, handle_database_error)
    app.register_error_handler(ExternalServiceError, handle_api_error)
    app.register_error_handler(TrainingError, handle_api_error)

    # Standard HTTP exceptions
    app.register_error_handler(HTTPException, handle_http_exception)

    # General exceptions
    app.register_error_handler(Exception, handle_server_error)

    logger.info("Error handlers registered successfully")

def create_error_response(message: str, status_code: int = 400, **kwargs) -> tuple:
    """Create a standardized error response."""
    response = {
        'error': True,
        'message': message,
        'status_code': status_code,
        'timestamp': datetime.utcnow().isoformat()
    }

    # Add any additional data
    response.update(kwargs)

    return jsonify(response), status_code

def log_security_event(event_type: str, message: str, **context):
    """Log security-related events with context."""
    logger.warning(f"Security Event - {event_type}: {message}", extra={
        'event_type': event_type,
        'timestamp': datetime.utcnow().isoformat(),
        **context
    })

def sanitize_error_message(message: str, user_friendly: bool = True) -> str:
    """Sanitize error messages to prevent information leakage."""
    if not user_friendly:
        return message

    # List of patterns that might reveal sensitive information
    sensitive_patterns = [
        'password', 'secret', 'key', 'token', 'database',
        'connection', 'internal', 'stack trace', 'file path',
        'sql', 'query', 'table', 'column', 'row'
    ]

    message_lower = message.lower()
    for pattern in sensitive_patterns:
        if pattern in message_lower:
            return "An error occurred while processing your request"

    return message

class ErrorContext:
    """Context manager for consistent error handling."""

    def __init__(self, operation: str, user_id: Optional[str] = None, **context):
        self.operation = operation
        self.user_id = user_id
        self.context = context
        self.start_time = datetime.utcnow()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = (datetime.utcnow() - self.start_time).total_seconds()

        if exc_type is not None:
            logger.error(f"Operation failed: {self.operation}", extra={
                'operation': self.operation,
                'user_id': self.user_id,
                'duration': duration,
                'error_type': exc_type.__name__,
                'error_message': str(exc_val),
                **self.context
            })
        else:
            logger.info(f"Operation completed: {self.operation}", extra={
                'operation': self.operation,
                'user_id': self.user_id,
                'duration': duration,
                **self.context
            })

    def raise_error(self, error_class, message: str, **kwargs):
        """Raise a specific error type with context."""
        error = error_class(message, **kwargs)
        error.operation = self.operation
        error.user_id = self.user_id
        error.context = self.context
        raise error