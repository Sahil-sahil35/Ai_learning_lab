from flask import current_app
from . import db
def init_db():
    """Initializes the database, creating tables if they don't exist."""
    # The inspector is used to get schema information from a database
    inspector = db.inspect(db.engine)
    tables = inspector.get_table_names()
    # Check if the 'users' table exists. We assume if it does, all tables exist.
    if 'users' not in tables:
        print("Database tables not found. Creating them now...")
        # Import models here to avoid circular imports
        from .models import User, Task, ModelRun
        db.create_all()
        print("✅ Database tables created successfully!")
    else:
        print("Database tables already exist. Skipping creation.")
