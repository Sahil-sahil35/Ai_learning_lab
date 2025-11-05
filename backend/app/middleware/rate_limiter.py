"""
Rate limiting middleware using Flask-Limiter with Redis storage.
Implements tiered rate limits by endpoint type and user role.
"""

import time
import uuid
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify, current_app, g
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from redis import Redis
import logging

# Initialize limiter
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri="redis://broker:6379/1",
    storage_options={"socket_connect_timeout": 30},
    default_limits=["200 per day", "50 per hour"]
)

logger = logging.getLogger(__name__)

class RateLimitConfig:
    """Rate limit configurations by endpoint category."""

    LIMITS = {
        'auth': {
            'limits': ['5 per minute', '20 per hour'],
            'error_message': 'Too many authentication attempts. Please try again later.',
            'per_method': True
        },
        'api': {
            'limits': ['100 per minute', '1000 per hour'],
            'error_message': 'API rate limit exceeded. Please try again later.',
            'per_method': False
        },
        'upload': {
            'limits': ['10 per minute', '50 per hour'],
            'error_message': 'Upload rate limit exceeded. Please try again later.',
            'per_method': True
        },
        'training': {
            'limits': ['5 per hour', '20 per day'],
            'error_message': 'Training rate limit exceeded. Please try again later.',
            'per_method': True
        },
        'admin': {
            'limits': ['200 per minute', '2000 per hour'],
            'error_message': 'Admin API rate limit exceeded.',
            'per_method': False
        }
    }

class SuspiciousActivityDetector:
    """Detects and blocks suspicious activity patterns."""

    def __init__(self, redis_client: Redis):
        self.redis = redis_client
        self.window = 300  # 5 minutes

    def is_suspicious(self, ip: str) -> tuple[bool, str]:
        """Check if IP is showing suspicious patterns."""
        pipe = self.redis.pipeline()

        # Check for rapid requests
        rapid_key = f"suspicious:rapid:{ip}"
        rapid_count = self.redis.incr(rapid_key)
        if rapid_count == 1:
            self.redis.expire(rapid_key, self.window)

        if rapid_count > 100:  # More than 100 requests in 5 minutes
            return True, "Too many rapid requests"

        # Check for failed auth attempts
        failed_auth_key = f"suspicious:auth_fail:{ip}"
        failed_count = self.redis.get(failed_auth_key)
        if failed_count and int(failed_count) > 10:
            return True, "Too many failed authentication attempts"

        # Check for request pattern anomalies
        pattern_key = f"suspicious:pattern:{ip}"
        endpoints = self.redis.lrange(pattern_key, 0, -1)
        if len(endpoints) > 50:  # Accessing too many different endpoints
            unique_endpoints = set(endpoints)
            if len(unique_endpoints) > 20:
                return True, "Suspicious endpoint access pattern"

        return False, ""

def get_rate_limit_key():
    """Generate rate limit key based on user ID and IP if available."""
    # Try to get user ID from JWT token
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        try:
            # This will be validated by the JWT decorator
            from flask_jwt_extended import get_jwt_identity
            user_id = get_jwt_identity()
            if user_id:
                return f"user:{user_id}"
        except:
            pass

    # Fallback to IP-based limiting
    return f"ip:{get_remote_address()}"

def rate_limit(category: str, key_func=None):
    """Custom rate limit decorator with category-specific limits."""
    def decorator(f):
        config = RateLimitConfig.LIMITS.get(category, RateLimitConfig.LIMITS['api'])

        # Create limiter with specific configuration
        category_limiter = Limiter(
            key_func=key_func or get_rate_limit_key,
            storage_uri="redis://broker:6379/1",
            storage_options={"socket_connect_timeout": 30},
            default_limits=config['limits']
        )

        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Check for suspicious activity first
            redis_client = Redis.from_url("redis://broker:6379/1")
            detector = SuspiciousActivityDetector(redis_client)

            ip = get_remote_address()
            is_suspicious, reason = detector.is_suspicious(ip)

            if is_suspicious:
                logger.warning(f"Suspicious activity detected from {ip}: {reason}")
                return jsonify({
                    'error': 'Access denied due to suspicious activity',
                    'message': reason,
                    'retry_after': 3600
                }), 429

            # Track endpoint access for pattern analysis
            pattern_key = f"suspicious:pattern:{ip}"
            redis_client.lpush(pattern_key, request.endpoint)
            redis_client.expire(pattern_key, 300)
            redis_client.ltrim(pattern_key, 0, 99)  # Keep last 100 requests

            # Apply rate limiting
            try:
                # Create a dynamic limiter for this function
                dynamic_limiter = category_limiter.limit(config['limits'][0])(f)
                return dynamic_limiter(*args, **kwargs)
            except Exception as e:
                logger.error(f"Rate limiting error: {e}")
                # Fallback to allowing the request if rate limiting fails
                return f(*args, **kwargs)

        return decorated_function
    return decorator

def track_failed_auth(ip: str):
    """Track failed authentication attempts."""
    redis_client = Redis.from_url("redis://broker:6379/1")
    key = f"suspicious:auth_fail:{ip}"
    redis_client.incr(key)
    redis_client.expire(key, 3600)  # 1 hour expiry

def clear_failed_auth(ip: str):
    """Clear failed authentication attempts on successful login."""
    redis_client = Redis.from_url("redis://broker:6379/1")
    key = f"suspicious:auth_fail:{ip}"
    redis_client.delete(key)

class RequestSizeLimiter:
    """Middleware to limit request size and validate content."""

    def __init__(self, app=None):
        self.app = app
        if app:
            self.init_app(app)

    def init_app(self, app):
        app.before_request(self.validate_request)

    def validate_request(self):
        """Validate request size and content."""
        # Check content length
        content_length = request.content_length
        if content_length:
            max_sizes = {
                'application/json': 10 * 1024 * 1024,  # 10MB
                'text/csv': 100 * 1024 * 1024,  # 100MB
                'application/octet-stream': 500 * 1024 * 1024,  # 500MB
            }

            content_type = request.content_type or ''
            max_size = max_sizes.get(content_type.split(';')[0], 10 * 1024 * 1024)  # Default 10MB

            if content_length > max_size:
                return jsonify({
                    'error': 'Request entity too large',
                    'message': f'Maximum allowed size is {max_size // (1024*1024)}MB'
                }), 413

        # Add request ID for tracking
        g.request_id = str(uuid.uuid4())
        g.start_time = time.time()

# Initialize middleware
request_size_limiter = RequestSizeLimiter()