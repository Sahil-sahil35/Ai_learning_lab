"""
Security utilities for headers, HTTPS enforcement, and CSRF protection.
Implements comprehensive security headers and HTTPS enforcement.
"""

import os
from flask import Flask, request, redirect
from functools import wraps

def setup_security_headers(app: Flask):
    """Configure security headers for the Flask application."""

    @app.after_request
    def add_security_headers(response):
        """Add security headers to all responses."""

        # Force HTTPS in production
        if app.config.get('FORCE_HTTPS', False):
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains; preload'

        # Content Security Policy
        csp_directives = [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'",  # Required for React/Vite
            "style-src 'self' 'unsafe-inline'",  # Required for CSS-in-JS
            "img-src 'self' data: https:",
            "font-src 'self' data:",
            "connect-src 'self' ws: wss:",
            "frame-ancestors 'none'",
            "base-uri 'self'",
            "form-action 'self'"
        ]

        # Allow specific external domains in development
        if app.config.get('ENV') == 'development':
            csp_directives.extend([
                "connect-src 'self' ws: wss: http://localhost:*",
                "script-src 'self' 'unsafe-inline' 'unsafe-eval' http://localhost:*"
            ])

        response.headers['Content-Security-Policy'] = '; '.join(csp_directives)

        # Other security headers
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Permissions-Policy'] = (
            'geolocation=(), microphone=(), camera=(), '
            'payment=(), usb=(), magnetometer=(), gyroscope=(), '
            'speaker=(), vibrate=(), fullscreen=(self)'
        )

        # Remove server information
        response.headers['Server'] = 'AI Learning Lab'

        return response

def enforce_https(app: Flask):
    """Enforce HTTPS for all requests in production."""

    @app.before_request
    def https_redirect():
        """Redirect HTTP to HTTPS in production."""
        if (app.config.get('FORCE_HTTPS', False) and
            not request.is_secure and
            request.headers.get('X-Forwarded-Proto') != 'https'):

            # Build HTTPS URL
            url = request.url.replace('http://', 'https://', 1)
            return redirect(url, code=301)

    return app

def secure_cookies(app: Flask):
    """Configure secure cookie settings."""

    app.config.update(
        SESSION_COOKIE_SECURE=app.config.get('FORCE_HTTPS', False),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        PERMANENT_SESSION_LIFETIME=3600  # 1 hour
    )

    return app

def validate_file_upload(file, allowed_extensions=None, max_size_mb=16):
    """Validate uploaded files for security."""

    if file is None:
        return False, "No file provided"

    # Check file size
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)

    max_size_bytes = max_size_mb * 1024 * 1024
    if file_size > max_size_bytes:
        return False, f"File size exceeds {max_size_mb}MB limit"

    # Check file extension
    if allowed_extensions:
        filename = file.filename
        if not filename or '.' not in filename:
            return False, "Invalid filename"

        extension = filename.rsplit('.', 1)[1].lower()
        if extension not in allowed_extensions:
            return False, f"File type {extension} not allowed"

    # Check file content (basic)
    try:
        # Read first few bytes to check for malicious content
        file_header = file.read(1024)
        file.seek(0)

        # Check for executable signatures
        executable_signatures = [
            b'MZ',  # Windows PE
            b'\x7fELF',  # Linux ELF
            b'\xca\xfe\xba\xbe',  # Java class
            b'\xfe\xed\xfa',  # Mach-O binary
        ]

        for signature in executable_signatures:
            if file_header.startswith(signature):
                return False, "Executable files not allowed"

    except Exception as e:
        return False, f"Error reading file: {str(e)}"

    return True, "File validation passed"

def sanitize_input(text, max_length=1000):
    """Sanitize user input to prevent XSS and injection attacks."""

    if not isinstance(text, str):
        return ""

    # Truncate to maximum length
    if len(text) > max_length:
        text = text[:max_length]

    # Basic HTML tag removal
    import re
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Remove JavaScript event handlers
    text = re.sub(r'on\w+\s*=', '', text, flags=re.IGNORECASE)
    # Remove javascript: protocol
    text = re.sub(r'javascript:', '', text, flags=re.IGNORECASE)

    # Remove potentially dangerous characters
    dangerous_chars = ['<', '>', '"', "'", '&', '\x00']
    for char in dangerous_chars:
        text = text.replace(char, '')

    return text.strip()

def initialize_security(app: Flask):
    """Initialize all security features for the application."""

    # Setup security headers
    setup_security_headers(app)

    # Enforce HTTPS in production
    if os.getenv('FORCE_HTTPS', 'false').lower() == 'true':
        enforce_https(app)
        app.config['FORCE_HTTPS'] = True

    # Secure cookies
    secure_cookies(app)

    app.logger.info("Security features initialized", extra={
        'https_enforced': app.config.get('FORCE_HTTPS', False)
    })

    return app