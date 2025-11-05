# backend/app/models.py

from . import db, bcrypt # Import db and bcrypt from the app package root
import datetime
import uuid
from sqlalchemy.dialects.postgresql import UUID, JSONB # Use JSONB for Postgres
from sqlalchemy import Enum
from .models.enhanced import UserRole

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(Enum(UserRole), default=UserRole.STUDENT, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    last_login = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.now())
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())

    # Relationships
    tasks = db.relationship('Task', back_populates='owner', lazy=True, cascade="all, delete-orphan")
    model_runs = db.relationship('ModelRun', back_populates='user', lazy=True, cascade="all, delete-orphan")


    def __init__(self, username, email, password):
        self.username = username
        self.email = email
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'

class Task(db.Model):
    __tablename__ = 'tasks'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.now())
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=False)

    # Relationships
    owner = db.relationship('User', back_populates='tasks')
    model_runs = db.relationship('ModelRun', back_populates='task', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Task {self.name}>'

class ModelRun(db.Model):
    __tablename__ = 'model_runs'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_id_str = db.Column(db.String(80), nullable=False) # e.g., "classical_random_forest"
    status = db.Column(db.String(50), nullable=False, default='PENDING') # PENDING_UPLOAD, PENDING_ANALYSIS, ANALYZING, ANALYSIS_FAILED, SUCCESS (analysis done), PENDING_CLEANING, CLEANING, CLEANING_FAILED, CLEANING_SUCCESS, PENDING_CONFIG, STARTING, TRAINING, SUCCESS, FAILED
    created_at = db.Column(db.DateTime, default=db.func.now())
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)

    original_data_path = db.Column(db.String(512), nullable=True)
    run_output_dir = db.Column(db.String(512), nullable=True) # Directory for logs, models, etc.

    celery_task_id = db.Column(db.String(128), nullable=True) # To track the latest celery task

    # --- START FIX [Issue #1] ---
    cleaned_data_path = db.Column(db.String(512), nullable=True) # Path after cleaning step
    cleaning_report = db.Column(JSONB, nullable=True) # Store report from cleaning script
    # --- END FIX [Issue #1] ---

    # Store results directly in the DB for easier retrieval
    analysis_results = db.Column(JSONB, nullable=True) # Store output of analyze.py
    final_metrics = db.Column(JSONB, nullable=True) # Store final_metrics.json
    educational_summary = db.Column(JSONB, nullable=True) # Store educational_summary.json


    # Foreign Keys
    task_id = db.Column(UUID(as_uuid=True), db.ForeignKey('tasks.id'), nullable=False)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=False)

    # Relationships
    task = db.relationship('Task', back_populates='model_runs')
    user = db.relationship('User', back_populates='model_runs')


    def __repr__(self):
        return f'<ModelRun {self.id} - {self.model_id_str} ({self.status})>'