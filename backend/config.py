import os
import secrets
import sys
from dotenv import load_dotenv

# Load environment variables from .env file
basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '..', '.env'))

def validate_config():
    """Validate configuration to ensure security requirements are met."""
    errors = []

    # Check if running with default secrets in production
    if os.getenv('FLASK_CONFIG') == 'production':
        secret_key = os.getenv('SECRET_KEY')
        jwt_secret_key = os.getenv('JWT_SECRET_KEY')

        if secret_key == 'a_very_hard_to_guess_secret_key':
            errors.append("CRITICAL: Default SECRET_KEY detected in production!")
        if jwt_secret_key == 'another_secret_key_for_jwt':
            errors.append("CRITICAL: Default JWT_SECRET_KEY detected in production!")

        if len(secret_key or '') < 32:
            errors.append("CRITICAL: SECRET_KEY must be at least 32 characters in production!")
        if len(jwt_secret_key or '') < 32:
            errors.append("CRITICAL: JWT_SECRET_KEY must be at least 32 characters in production!")

    if errors:
        print("CRITICAL SECURITY CONFIGURATION ERRORS:")
        for error in errors:
            print(f"  - {error}")
        print("\nPlease set proper environment variables before starting in production.")
        sys.exit(1)

class Config:
    """Base configuration."""
    # Generate secure keys if not provided (for development only)
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_urlsafe(32)
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or secrets.token_urlsafe(32)
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # JWT Configuration
    JWT_ACCESS_TOKEN_EXPIRES = os.environ.get('JWT_ACCESS_TOKEN_EXPIRES', 28800)  # 8 hours default

    # Celery Configuration
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL') or 'redis://broker:6379/0'
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND') or 'redis://broker:6379/0'
    REDIS_URL = os.environ.get('REDIS_URL') or 'redis://broker:6379/0'

    # App-specific paths
    USER_UPLOADS_DIR = os.environ.get('USER_UPLOADS_DIR') or '/app/uploads'
    MODELS_DIR = os.environ.get('MODELS_DIR') or '/app/models'

    # CORS Configuration
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '*').split(',')

    # Socket.IO Configuration
    SOCKETIO_MESSAGE_QUEUE = os.environ.get('SOCKETIO_MESSAGE_QUEUE', 'redis://broker:6379/0')

    # Security Settings
    RATE_LIMIT_ENABLED = os.environ.get('RATE_LIMIT_ENABLED', 'true').lower() == 'true'
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))  # 16MB default

class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'dev.db')

class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')

    def __init__(self):
        # Validate configuration when production config is instantiated
        validate_config()

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}