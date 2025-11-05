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
from config import config
import logging # Import logging

# Initialize Extensions
db = SQLAlchemy()
migrate = Migrate()
bcrypt = Bcrypt()
jwt = JWTManager()
cors = CORS()
ma = Marshmallow()
# Initialize SocketIO with async_mode='eventlet' for production
# Added engineio_logger=True, logger=True for debugging websockets
socketio = SocketIO(
    async_mode='eventlet', 
    cors_allowed_origins="*", 
    engineio_logger=True, 
    logger=True, 
    message_queue='redis://broker:6379/0'
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

    # --- Configure Logging ---
    # Ensure logs are visible in Docker
    gunicorn_logger = logging.getLogger('gunicorn.error')
    app.logger.handlers = gunicorn_logger.handlers
    app.logger.setLevel(gunicorn_logger.level)
    app.logger.info(f"Flask app created with config: {config_name}")


    # --- Initialize Extensions with App ---
    db.init_app(app)
    migrate.init_app(app, db)
    bcrypt.init_app(app)
    jwt.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": "*"}})
    ma.init_app(app)
    socketio.init_app(app)
    app.logger.info("Flask extensions initialized.")

    # --- Create Application Directories ---
    # Ensure instance folder exists
    try:
        os.makedirs(app.instance_path, exist_ok=True) # Added exist_ok=True
    except OSError as e:
         app.logger.error(f"Could not create instance path: {e}")

    # Ensure upload folder exists
    try:
        # Check if USER_UPLOADS_DIR is set
        uploads_dir = app.config.get('USER_UPLOADS_DIR')
        if uploads_dir:
            os.makedirs(uploads_dir, exist_ok=True)
            app.logger.info(f"Uploads directory ensured at: {uploads_dir}")
        else:
            app.logger.error("USER_UPLOADS_DIR is not configured!")
    except OSError as e:
        app.logger.error(f"Could not create uploads directory: {e}")
    except Exception as e:
         app.logger.error(f"Error checking uploads directory: {e}")


    # --- Register Blueprints (API Routes) ---
    with app.app_context():
        # MOVE IMPORTS INSIDE app_context
        from .routes import auth, tasks, models, training, admin, custom_models, exports
        app.logger.info("Registering blueprints...")
        app.register_blueprint(auth.auth_bp, url_prefix='/api/auth')
        app.register_blueprint(tasks.tasks_bp, url_prefix='/api/tasks')
        app.register_blueprint(models.models_bp, url_prefix='/api/models')
        app.register_blueprint(training.training_bp, url_prefix='/api/training')
        app.register_blueprint(admin.admin_bp, url_prefix='/api/admin')
        app.register_blueprint(custom_models.custom_models_bp, url_prefix='/api/custom-models')
        app.register_blueprint(exports.exports_bp, url_prefix='/api/exports')
        app.logger.info("Blueprints registered successfully.")

    app.logger.info("Flask app creation complete.")
    return app