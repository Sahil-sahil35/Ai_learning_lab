"""
Structured logging system for consistent, searchable logs with correlation tracking.
Provides JSON-based logging with proper filtering and security considerations.
"""

import logging
import json
import uuid
import time
import threading
from datetime import datetime
from typing import Dict, Any, Optional
from pythonjsonlogger import jsonlogger
import os

class StructuredLogger:
    """Structured logger with JSON output and correlation tracking."""

    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self._setup_logger()

    def _setup_logger(self):
        """Configure the logger with JSON formatter."""
        # Remove existing handlers
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)

        # Create JSON formatter
        formatter = StructuredJSONFormatter(
            '%(asctime)s %(name)s %(levelname)s %(message)s'
        )

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

        # File handler (if configured)
        log_file = os.getenv('LOG_FILE')
        if log_file:
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

        # Set log level
        log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
        self.logger.setLevel(getattr(logging, log_level, logging.INFO))

    def _sanitize_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Remove sensitive data from log entries."""
        sensitive_keys = [
            'password', 'secret', 'token', 'key', 'authorization',
            'cookie', 'session', 'csrf', 'jwt', 'api_key',
            'private_key', 'credit_card', 'ssn', 'social_security'
        ]

        sanitized = {}
        for key, value in data.items():
            key_lower = key.lower()
            if any(sensitive in key_lower for sensitive in sensitive_keys):
                sanitized[key] = '[REDACTED]'
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_data(value)
            elif isinstance(value, (list, tuple)):
                sanitized[key] = [
                    self._sanitize_data(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                sanitized[key] = value

        return sanitized

    def _log(self, level: str, message: str, **kwargs):
        """Internal logging method with structured data."""
        # Get correlation ID from thread local storage
        correlation_id = getattr(_request_context, 'correlation_id', None)
        if not correlation_id:
            correlation_id = str(uuid.uuid4())

        # Get user ID if available
        user_id = getattr(_request_context, 'user_id', None)

        # Get request info if available
        request_info = getattr(_request_context, 'request_info', {})

        # Prepare log data
        log_data = {
            'level': level,
            'message': message,
            'timestamp': datetime.utcnow().isoformat(),
            'correlation_id': correlation_id,
            'thread_id': threading.current_thread().ident,
            'process_id': os.getpid(),
        }

        # Add user context
        if user_id:
            log_data['user_id'] = user_id

        # Add request context
        if request_info:
            log_data.update(request_info)

        # Add custom fields
        log_data.update(kwargs)

        # Sanitize sensitive data
        log_data = self._sanitize_data(log_data)

        # Log the message
        getattr(self.logger, level.lower())(json.dumps(log_data))

    def debug(self, message: str, **kwargs):
        """Log debug message."""
        self._log('DEBUG', message, **kwargs)

    def info(self, message: str, **kwargs):
        """Log info message."""
        self._log('INFO', message, **kwargs)

    def warning(self, message: str, **kwargs):
        """Log warning message."""
        self._log('WARNING', message, **kwargs)

    def error(self, message: str, **kwargs):
        """Log error message."""
        self._log('ERROR', message, **kwargs)

    def critical(self, message: str, **kwargs):
        """Log critical message."""
        self._log('CRITICAL', message, **kwargs)

    def security(self, message: str, **kwargs):
        """Log security event."""
        self._log('SECURITY', message, security_event=True, **kwargs)

    def api_request(self, method: str, path: str, status_code: int,
                   duration: float, user_id: Optional[str] = None, **kwargs):
        """Log API request."""
        self._log('INFO', f"API {method} {path}",
                 event_type='api_request',
                 method=method,
                 path=path,
                 status_code=status_code,
                 duration=duration,
                 user_id=user_id,
                 **kwargs)

    def training_job(self, job_id: str, status: str, **kwargs):
        """Log training job event."""
        self._log('INFO', f"Training job {job_id}: {status}",
                 event_type='training_job',
                 job_id=job_id,
                 status=status,
                 **kwargs)

    def database_query(self, query_type: str, table: str, duration: float,
                      affected_rows: Optional[int] = None, **kwargs):
        """Log database query."""
        self._log('DEBUG', f"DB {query_type} on {table}",
                 event_type='database_query',
                 query_type=query_type,
                 table=table,
                 duration=duration,
                 affected_rows=affected_rows,
                 **kwargs)

    def external_service(self, service: str, operation: str, status: str,
                        duration: float, **kwargs):
        """Log external service interaction."""
        self._log('INFO', f"External service {service}: {operation} - {status}",
                 event_type='external_service',
                 service=service,
                 operation=operation,
                 status=status,
                 duration=duration,
                 **kwargs)


class StructuredJSONFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with additional fields."""

    def add_fields(self, log_record, record, message_dict):
        """Add custom fields to log record."""
        super().add_fields(log_record, record, message_dict)

        # Add timestamp if not present
        if not log_record.get('timestamp'):
            log_record['timestamp'] = datetime.utcnow().isoformat()

        # Add hostname
        log_record['hostname'] = os.getenv('HOSTNAME', os.uname().nodename)

        # Add application name
        log_record['application'] = os.getenv('APP_NAME', 'ai-learning-lab')

        # Add environment
        log_record['environment'] = os.getenv('FLASK_CONFIG', 'development')

        # Add version if available
        log_record['version'] = os.getenv('APP_VERSION', 'unknown')


class RequestContext:
    """Thread-local context for request-specific data."""

    def __init__(self):
        self.correlation_id = None
        self.user_id = None
        self.request_info = {}
        self.start_time = None

    def set_correlation_id(self, correlation_id: str):
        """Set correlation ID for the current request."""
        self.correlation_id = correlation_id

    def set_user_id(self, user_id: str):
        """Set user ID for the current request."""
        self.user_id = user_id

    def set_request_info(self, info: Dict[str, Any]):
        """Set request information."""
        self.request_info = info

    def set_start_time(self):
        """Set request start time."""
        self.start_time = time.time()

    def get_duration(self) -> Optional[float]:
        """Get request duration in seconds."""
        if self.start_time:
            return time.time() - self.start_time
        return None

    def clear(self):
        """Clear all context data."""
        self.correlation_id = None
        self.user_id = None
        self.request_info = {}
        self.start_time = None


# Thread-local storage for request context
_request_context = threading.local()


def get_logger(name: str) -> StructuredLogger:
    """Get a structured logger instance."""
    return StructuredLogger(name)


def init_request_context():
    """Initialize request context for a new request."""
    context = RequestContext()
    context.set_correlation_id(str(uuid.uuid4()))
    context.set_start_time()
    _request_context.__dict__.update(context.__dict__)
    return context


def get_request_context() -> RequestContext:
    """Get current request context."""
    if not hasattr(_request_context, 'correlation_id'):
        init_request_context()
    return _request_context


def clear_request_context():
    """Clear current request context."""
    if hasattr(_request_context, 'clear'):
        _request_context.clear()


def log_api_request(logger: StructuredLogger, method: str, path: str,
                   status_code: int, user_id: Optional[str] = None, **kwargs):
    """Log API request with structured data."""
    context = get_request_context()
    duration = context.get_duration()

    logger.api_request(
        method=method,
        path=path,
        status_code=status_code,
        duration=duration or 0,
        user_id=user_id,
        **kwargs
    )


def log_security_event(logger: StructuredLogger, event_type: str, message: str,
                      user_id: Optional[str] = None, **kwargs):
    """Log security event with enhanced context."""
    context = get_request_context()

    # Add request info to security events
    request_info = context.request_info if hasattr(context, 'request_info') else {}

    logger.security(
        f"{event_type}: {message}",
        event_type=event_type,
        user_id=user_id,
        **{**request_info, **kwargs}
    )


def setup_logging(app):
    """Setup structured logging for the Flask application."""
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create structured formatter
    formatter = StructuredJSONFormatter(
        '%(asctime)s %(name)s %(levelname)s %(message)s'
    )

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler (if configured)
    log_file = os.getenv('LOG_FILE')
    if log_file:
        # Ensure log directory exists
        log_dir = os.path.dirname(log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)

        file_handler = logging.StreamHandler(open(log_file, 'a'))
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    # Set log level
    log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
    root_logger.setLevel(getattr(logging, log_level, logging.INFO))

    # Configure specific loggers
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('docker').setLevel(logging.WARNING)

    app.logger.info("Structured logging initialized", extra={
        'log_level': log_level,
        'log_file': log_file,
        'hostname': os.getenv('HOSTNAME', os.uname().nodename)
    })


# Global logger instance
app_logger = get_logger('app')