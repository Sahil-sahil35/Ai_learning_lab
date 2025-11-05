"""
Security middleware for input validation, XSS protection,
SQL injection prevention, and security monitoring.
"""

import re
import html
import hashlib
import hmac
import uuid
import time
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from flask import request, jsonify, g, current_app
from werkzeug.utils import secure_filename
import magic
from PIL import Image
import io

logger = logging.getLogger(__name__)

class SecurityConfig:
    """Security configuration settings."""

    # Allowed file extensions and their max sizes
    ALLOWED_EXTENSIONS = {
        'csv': 100 * 1024 * 1024,  # 100MB
        'json': 10 * 1024 * 1024,   # 10MB
        'txt': 5 * 1024 * 1024,     # 5MB
        'xlsx': 50 * 1024 * 1024,   # 50MB
        'xls': 50 * 1024 * 1024,    # 50MB
        'png': 10 * 1024 * 1024,    # 10MB
        'jpg': 10 * 1024 * 1024,    # 10MB
        'jpeg': 10 * 1024 * 1024,   # 10MB
        'gif': 10 * 1024 * 1024,    # 10MB
        'pkl': 50 * 1024 * 1024,    # 50MB for models
        'h5': 100 * 1024 * 1024,    # 100MB for models
        'onnx': 100 * 1024 * 1024,  # 100MB for models
    }

    # Dangerous patterns to detect in inputs
    DANGEROUS_PATTERNS = [
        r'<script[^>]*>.*?</script>',
        r'javascript:',
        r'on\w+\s*=',
        r'eval\s*\(',
        r'document\.',
        r'window\.',
        r'alert\s*\(',
        r'prompt\s*\(',
        r'confirm\s*\(',
        r'setTimeout\s*\(',
        r'setInterval\s*\(',
    ]

    # SQL injection patterns
    SQL_INJECTION_PATTERNS = [
        r'(\bUNION\b.*\bSELECT\b)',
        r'(\bSELECT\b.*\bFROM\b)',
        r'(\bINSERT\b.*\bINTO\b)',
        r'(\bUPDATE\b.*\bSET\b)',
        r'(\bDELETE\b.*\bFROM\b)',
        r'(\bDROP\b.*\bTABLE\b)',
        r'(\bCREATE\b.*\bTABLE\b)',
        r'(\bALTER\b.*\bTABLE\b)',
        r"('.*'|\".*\"|;\s*--)",
        r'(\bOR\b.*=.*\bOR\b)',
        r'(\bAND\b.*=.*\bAND\b)',
    ]

class InputValidator:
    """Validates and sanitizes user inputs."""

    @staticmethod
    def sanitize_string(value: str, max_length: int = 1000) -> str:
        """Sanitize string input to prevent XSS."""
        if not isinstance(value, str):
            return str(value)

        # HTML escape
        sanitized = html.escape(value)

        # Remove dangerous patterns
        for pattern in SecurityConfig.DANGEROUS_PATTERNS:
            sanitized = re.sub(pattern, '', sanitized, flags=re.IGNORECASE | re.DOTALL)

        # Limit length
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length]

        return sanitized.strip()

    @staticmethod
    def validate_email(email: str) -> bool:
        """Validate email format."""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None

    @staticmethod
    def validate_password_strength(password: str) -> tuple[bool, str]:
        """Validate password strength."""
        if len(password) < 8:
            return False, "Password must be at least 8 characters long"

        if not re.search(r'[a-z]', password):
            return False, "Password must contain at least one lowercase letter"

        if not re.search(r'[A-Z]', password):
            return False, "Password must contain at least one uppercase letter"

        if not re.search(r'\d', password):
            return False, "Password must contain at least one digit"

        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            return False, "Password must contain at least one special character"

        return True, "Password is valid"

    @staticmethod
    def detect_sql_injection(value: str) -> bool:
        """Detect potential SQL injection attempts."""
        if not isinstance(value, str):
            return False

        for pattern in SecurityConfig.SQL_INJECTION_PATTERNS:
            if re.search(pattern, value, flags=re.IGNORECASE):
                return True

        return False

    @staticmethod
    def validate_json_input(data: dict, required_fields: List[str] = None,
                          max_depth: int = 10) -> tuple[bool, str]:
        """Validate JSON input structure and content."""
        if not isinstance(data, dict):
            return False, "Invalid JSON format"

        # Check for required fields
        if required_fields:
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                return False, f"Missing required fields: {', '.join(missing_fields)}"

        # Validate nested structure depth
        def check_depth(obj, current_depth=0):
            if current_depth > max_depth:
                return False
            if isinstance(obj, dict):
                for value in obj.values():
                    if not check_depth(value, current_depth + 1):
                        return False
            elif isinstance(obj, list):
                for item in obj:
                    if not check_depth(item, current_depth + 1):
                        return False
            return True

        if not check_depth(data):
            return False, "JSON structure too deeply nested"

        return True, "Valid JSON input"

class FileValidator:
    """Validates file uploads for security."""

    @staticmethod
    def allowed_file(filename: str) -> bool:
        """Check if file extension is allowed."""
        if not filename:
            return False

        ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
        return ext in SecurityConfig.ALLOWED_EXTENSIONS

    @staticmethod
    def validate_file_content(file_stream, filename: str) -> tuple[bool, str]:
        """Validate file content using magic bytes."""
        try:
            # Read file content
            content = file_stream.read(1024)  # Read first 1KB
            file_stream.seek(0)  # Reset file pointer

            # Use python-magic to detect file type
            file_type = magic.from_buffer(content, mime=True)

            # Get file extension
            ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''

            # Validate file type matches extension
            expected_types = {
                'csv': ['text/csv', 'text/plain'],
                'json': ['application/json', 'text/plain'],
                'txt': ['text/plain'],
                'xlsx': ['application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'],
                'xls': ['application/vnd.ms-excel'],
                'png': ['image/png'],
                'jpg': ['image/jpeg'],
                'jpeg': ['image/jpeg'],
                'gif': ['image/gif'],
            }

            if ext in expected_types and file_type not in expected_types[ext]:
                return False, f"File type {file_type} doesn't match extension {ext}"

            # Additional validation for image files
            if ext in ['png', 'jpg', 'jpeg', 'gif']:
                try:
                    # Try to open with PIL to ensure it's a valid image
                    img = Image.open(io.BytesIO(content))
                    img.verify()
                except Exception:
                    return False, "Invalid image file"

            return True, "File content is valid"

        except Exception as e:
            logger.error(f"File validation error: {e}")
            return False, "Failed to validate file content"

    @staticmethod
    def scan_for_malicious_content(file_stream) -> tuple[bool, str]:
        """Basic scan for potentially malicious content."""
        try:
            content = file_stream.read()
            file_stream.seek(0)

            # Convert to string for pattern matching
            content_str = content.decode('utf-8', errors='ignore').lower()

            # Check for suspicious patterns
            suspicious_patterns = [
                '<?php',
                '<%',
                '<script',
                'javascript:',
                'vbscript:',
                'onload=',
                'onerror=',
                'eval(',
                'document.write',
                'exec(',
                'system(',
            ]

            for pattern in suspicious_patterns:
                if pattern in content_str:
                    return False, f"Potentially malicious content detected: {pattern}"

            return True, "No malicious content detected"

        except Exception as e:
            logger.error(f"Malicious content scan error: {e}")
            return True, "Scan completed with warnings"  # Allow file if scan fails

class SecurityMonitor:
    """Monitors and logs security events."""

    def __init__(self):
        self.events = []

    def log_security_event(self, event_type: str, details: dict, severity: str = 'medium'):
        """Log security-related events."""
        event = {
            'id': str(uuid.uuid4()),
            'type': event_type,
            'severity': severity,
            'timestamp': datetime.utcnow().isoformat(),
            'ip': getattr(g, 'request_id', 'unknown'),
            'user_agent': request.headers.get('User-Agent', 'unknown'),
            'details': details
        }

        self.events.append(event)

        # Log based on severity
        if severity == 'high':
            logger.error(f"SECURITY EVENT: {event_type} - {details}")
        elif severity == 'medium':
            logger.warning(f"SECURITY EVENT: {event_type} - {details}")
        else:
            logger.info(f"SECURITY EVENT: {event_type} - {details}")

    def get_recent_events(self, hours: int = 24) -> List[dict]:
        """Get security events from the last N hours."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        return [
            event for event in self.events
            if datetime.fromisoformat(event['timestamp']) > cutoff
        ]

# Global security monitor instance
security_monitor = SecurityMonitor()

class SecurityMiddleware:
    """Main security middleware class."""

    def __init__(self, app=None):
        self.app = app
        if app:
            self.init_app(app)

    def init_app(self, app):
        """Initialize security middleware with Flask app."""
        app.before_request(self.before_request)
        app.after_request(self.after_request)

        # Add security headers
        @app.after_request
        def add_security_headers(response):
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['X-Frame-Options'] = 'DENY'
            response.headers['X-XSS-Protection'] = '1; mode=block'
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
            response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
            response.headers['Content-Security-Policy'] = "default-src 'self'"
            return response

    def before_request(self):
        """Security checks before processing request."""
        # Log request start
        g.request_id = str(uuid.uuid4())
        g.start_time = time.time()

        # Validate request size
        if request.content_length and request.content_length > 500 * 1024 * 1024:  # 500MB
            security_monitor.log_security_event('large_request', {
                'size': request.content_length,
                'endpoint': request.endpoint
            }, 'medium')
            return jsonify({'error': 'Request too large'}), 413

        # Check for SQL injection in query parameters
        for key, value in request.args.items():
            if InputValidator.detect_sql_injection(value):
                security_monitor.log_security_event('sql_injection_attempt', {
                    'param': key,
                    'value': value[:100]  # Truncate for logging
                }, 'high')
                return jsonify({'error': 'Invalid input detected'}), 400

    def after_request(self, response):
        """Security logging after request processing."""
        # Log request completion time
        if hasattr(g, 'start_time'):
            duration = time.time() - g.start_time
            if duration > 30:  # Log slow requests
                security_monitor.log_security_event('slow_request', {
                    'duration': duration,
                    'endpoint': request.endpoint
                }, 'low')

        return response

# Initialize security middleware
security_middleware = SecurityMiddleware()