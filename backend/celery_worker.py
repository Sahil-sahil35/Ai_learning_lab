# backend/celery_worker.py
# import eventlet
# eventlet.monkey_patch()
from celery import Celery
import os
import logging
from app import create_app
from app import db # Keep this import for the ContextTask

# Define the Celery app instance directly
# It gets configuration from the Flask app context later via ContextTask
celery = Celery(
    'tasks', # Default name, can be anything
    broker=os.environ.get('CELERY_BROKER_URL'),
    backend=os.environ.get('CELERY_RESULT_BACKEND'),
    # --- START FIX [Issue #1] ---
    include=[
        'tasks.analyze_data_task',
        'tasks.clean_data_task', # Add the new cleaning task
        'tasks.train_model_task'
    ]
    # --- END FIX [Issue #1] ---
)

# Optional: Configure Celery directly if needed,
# though ContextTask will load Flask config later.
# celery.conf.update(
#     result_expires=3600,
#     task_serializer='json',
#     result_serializer='json',
#     accept_content=['json']
# )

class ContextTask(celery.Task):
    """
    A custom Celery Task base class that ensures tasks
    run within a Flask application context.
    This gives tasks access to the database (db)
    and app configuration.
    """
    abstract = True
    _flask_app = None # Class variable to hold the app instance

    @property
    def flask_app(self):
        """Lazy load Flask app instance."""
        if ContextTask._flask_app is None:
             ContextTask._flask_app = create_app(os.getenv('FLASK_CONFIG') or 'default')
             # Configure logging for Celery tasks (use Flask's logger)
             celery_log = logging.getLogger('celery')
             celery_log.handlers = ContextTask._flask_app.logger.handlers
             celery_log.setLevel(ContextTask._flask_app.logger.level)
             ContextTask._flask_app.logger.info("Flask app created within Celery Task context.")
        return ContextTask._flask_app

    def __call__(self, *args, **kwargs):
        with self.flask_app.app_context():
            # Added logging
            self.flask_app.logger.info(f"Celery task {self.name} called with args: {args}, kwargs: {kwargs}")
            try:
                result = super().__call__(*args, **kwargs) # Use super() to call the actual task run method
                self.flask_app.logger.info(f"Celery task {self.name} finished successfully.")
                return result
            except Exception as e:
                self.flask_app.logger.error(f"Celery task {self.name} failed: {e}", exc_info=True)
                raise # Re-raise the exception so Celery knows it failed
            finally:
                db.session.remove()
# Apply the custom task class globally
celery.Task = ContextTask

# Logging to confirm celery worker setup
log = logging.getLogger(__name__)
log.info("Celery app instance defined.")

# Note: No autodiscover_tasks here, tasks are included explicitly above.