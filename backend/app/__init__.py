# import eventlet
# eventlet.monkey_patch()

import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_bcrypt import Bcrypt
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from flask_socketio import SocketIO
from flask_marshmallow import Marshmallow
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from config import config
import logging

# Import custom error handling and logging
from .utils.error_handlers import register_error_handlers, ErrorContext
from .utils.logger import setup_logging, get_request_context, clear_request_context, get_logger
from .utils.security import initialize_security

# Initialize Extensions
db = SQLAlchemy()
migrate = Migrate()
bcrypt = Bcrypt()
jwt = JWTManager()
cors = CORS()
ma = Marshmallow()
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)
# Initialize SocketIO with async_mode='eventlet' for production
# Added engineio_logger=True, logger=True for debugging websockets
# Get allowed origins from environment for security
allowed_origins = os.getenv('ALLOWED_ORIGINS', 'http://localhost:3000').split(',')
socketio = SocketIO(
    async_mode='eventlet',
    cors_allowed_origins=allowed_origins,
    engineio_logger=True,
    logger=True,
    message_queue='redis://broker:6379/0',
    cors_credentials=True
    )

def create_app(config_name=None):
    """
    Flask application factory.
    Initializes the app and all extensions.
    """
    if config_name is None:
        config_name = os.getenv('FLASK_CONFIG', 'default')

    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # --- Setup Structured Logging ---
    setup_logging(app)
    logger = get_logger('app')
    logger.info(f"Flask app created with config: {config_name}")

    # --- Register Error Handlers ---
    register_error_handlers(app)

    # --- Initialize Security Features ---
    initialize_security(app)


    # --- Initialize Extensions with App ---
    db.init_app(app)
    migrate.init_app(app, db)
    bcrypt.init_app(app)
    jwt.init_app(app)
    # Secure CORS configuration using environment-specific origins
    cors.init_app(app, resources={r"/api/*": {"origins": allowed_origins}}, supports_credentials=True)
    ma.init_app(app)
    limiter.init_app(app)
    socketio.init_app(app)
    logger.info("Flask extensions initialized.")

    # --- Create Application Directories ---
    # Ensure instance folder exists
    try:
        os.makedirs(app.instance_path, exist_ok=True) # Added exist_ok=True
    except OSError as e:
         logger.error(f"Could not create instance path: {e}", error=str(e))

    # Ensure upload folder exists
    try:
        # Check if USER_UPLOADS_DIR is set
        uploads_dir = app.config.get('USER_UPLOADS_DIR')
        if uploads_dir:
            os.makedirs(uploads_dir, exist_ok=True)
            logger.info(f"Uploads directory ensured at: {uploads_dir}")
        else:
            logger.error("USER_UPLOADS_DIR is not configured!")
    except OSError as e:
        logger.error(f"Could not create uploads directory: {e}", error=str(e))
    except Exception as e:
         logger.error(f"Error checking uploads directory: {e}", error=str(e))


    # --- Register Blueprints (API Routes) ---
    with app.app_context():
        # MOVE IMPORTS INSIDE app_context
        from .routes import auth, tasks, models, training, admin, custom_models, exports, health
        logger.info("Registering blueprints...")
        app.register_blueprint(auth.auth_bp, url_prefix='/api/auth')
        app.register_blueprint(tasks.tasks_bp, url_prefix='/api/tasks')
        app.register_blueprint(models.models_bp, url_prefix='/api/models')
        app.register_blueprint(training.training_bp, url_prefix='/api/training')
        app.register_blueprint(admin.admin_bp, url_prefix='/api/admin')
        app.register_blueprint(custom_models.custom_models_bp, url_prefix='/api/custom-models')
        app.register_blueprint(exports.exports_bp, url_prefix='/api/exports')
        app.register_blueprint(health.health_bp, url_prefix='/api')
        logger.info("Blueprints registered successfully.")

    logger.info("Flask app creation complete.")
    return app