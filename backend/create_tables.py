import os
import sys
from pathlib import Path
# Add the app directory to Python path
sys.path.insert(0, str(Path(__file__).parent))
from app import create_app, db
def create_tables():
    """Create all database tables."""
    app = create_app()
    with app.app_context():
        print("Creating database tables...")
        # Import models after app context is created to avoid circular imports
        from app.models import User, Task, ModelRun
        # Create all tables
        db.create_all()
        print("✅ Database tables created successfully!")
        # Verify tables were created
        inspector = db.inspect(db.engine)
        tables = inspector.get_table_names()
        print(f"Created {len(tables)} tables:")
        for table in sorted(tables):
            print(f"  - {table}")
        # Check if users table has the correct structure
        if 'users' in tables:
            columns = inspector.get_columns('users')
            print(f"\nUsers table structure:")
            for col in columns:
                print(f"  - {col['name']}: {col['type']}")
        print("\n🎉 Database initialization complete!")
if __name__ == "__main__":
    try:
        create_tables()
    except Exception as e:
        print(f"❌ Error creating tables: {e}")
        sys.exit(1)