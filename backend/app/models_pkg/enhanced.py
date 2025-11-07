"""
Enhanced database models for admin functionality, custom models,
export jobs, and system metrics.
"""

import datetime
import uuid
from enum import Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy import Index, CheckConstraint
from .. import db

class UserRole(Enum):
    """User roles for role-based access control."""
    STUDENT = 'student'
    ADMIN = 'admin'
    SUPER_ADMIN = 'super_admin'

class ExportStatus(Enum):
    """Export job statuses."""
    PENDING = 'pending'
    PROCESSING = 'processing'
    COMPLETED = 'completed'
    FAILED = 'failed'
    EXPIRED = 'expired'

class CustomModelStatus(Enum):
    """Custom model project statuses."""
    DRAFT = 'draft'
    VALIDATING = 'validating'
    VALIDATED = 'validated'
    TRAINING = 'training'
    TRAINED = 'trained'
    DEPLOYED = 'deployed'
    FAILED = 'failed'

class SecurityEventSeverity(Enum):
    """Security event severity levels."""
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'
    CRITICAL = 'critical'

class AdminLog(db.Model):
    """Audit trail for admin actions."""
    __tablename__ = 'admin_logs'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    admin_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=False)
    action = db.Column(db.String(100), nullable=False)  # Action performed
    resource_type = db.Column(db.String(50), nullable=False)  # Type of resource (user, task, etc.)
    resource_id = db.Column(UUID(as_uuid=True), nullable=True)  # ID of resource if applicable
    details = db.Column(JSONB, nullable=True)  # Additional details about the action
    ip_address = db.Column(db.String(45), nullable=True)  # IP address of admin
    user_agent = db.Column(db.Text, nullable=True)  # User agent string
    timestamp = db.Column(db.DateTime, default=db.func.now())

    # Relationships
    admin = db.relationship('User', backref='admin_actions')

    # Indexes for performance
    __table_args__ = (
        Index('idx_admin_logs_admin_timestamp', 'admin_id', 'timestamp'),
        Index('idx_admin_logs_action', 'action'),
        Index('idx_admin_logs_timestamp', 'timestamp'),
    )

    def __repr__(self):
        return f'<AdminLog {self.admin.username} - {self.action}>'

class SystemMetrics(db.Model):
    """Platform metrics for monitoring and analytics."""
    __tablename__ = 'system_metrics'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    metric_name = db.Column(db.String(100), nullable=False)  # e.g., 'active_users', 'training_jobs'
    metric_value = db.Column(db.Float, nullable=False)
    metric_unit = db.Column(db.String(20), nullable=True)  # e.g., 'count', 'percentage', 'seconds'
    tags = db.Column(JSONB, nullable=True)  # Additional tags for categorization
    timestamp = db.Column(db.DateTime, default=db.func.now())

    # Indexes for time-series queries
    __table_args__ = (
        Index('idx_system_metrics_name_timestamp', 'metric_name', 'timestamp'),
        Index('idx_system_metrics_timestamp', 'timestamp'),
    )

    def __repr__(self):
        return f'<SystemMetrics {self.metric_name}: {self.metric_value}>'

class UserSession(db.Model):
    """Active user session tracking."""
    __tablename__ = 'user_sessions'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=False)
    session_token = db.Column(db.String(255), unique=True, nullable=False)
    ip_address = db.Column(db.String(45), nullable=False)
    user_agent = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    last_activity = db.Column(db.DateTime, default=db.func.now())
    created_at = db.Column(db.DateTime, default=db.func.now())
    expires_at = db.Column(db.DateTime, nullable=False)

    # Relationships
    user = db.relationship('User', backref='sessions')

    # Constraints
    __table_args__ = (
        CheckConstraint('expires_at > created_at', name='check_session_expiry'),
        Index('idx_user_sessions_user', 'user_id'),
        Index('idx_user_sessions_token', 'session_token'),
        Index('idx_user_sessions_activity', 'last_activity'),
    )

    def is_expired(self):
        """Check if session has expired."""
        return datetime.datetime.utcnow() > self.expires_at

    def __repr__(self):
        return f'<UserSession {self.user.username} - {self.ip_address}>'

class CustomModel(db.Model):
    """Custom model projects created by users."""
    __tablename__ = 'custom_models'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    model_type = db.Column(db.String(50), nullable=False)  # classification, regression, etc.
    status = db.Column(db.Enum(CustomModelStatus), default=CustomModelStatus.DRAFT, nullable=False)

    # Code and configuration
    code_content = db.Column(db.Text, nullable=True)  # Main model code
    requirements = db.Column(JSONB, nullable=True)  # Python dependencies
    config = db.Column(JSONB, nullable=True)  # Model configuration

    # Training information
    training_data_path = db.Column(db.String(512), nullable=True)
    model_artifact_path = db.Column(db.String(512), nullable=True)
    training_metrics = db.Column(JSONB, nullable=True)

    # Metadata
    template_id = db.Column(UUID(as_uuid=True), nullable=True)  # If created from template
    is_public = db.Column(db.Boolean, default=False)  # Share with community
    tags = db.Column(JSONB, nullable=True)  # Searchable tags

    # Timestamps
    created_at = db.Column(db.DateTime, default=db.func.now())
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())
    trained_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    user = db.relationship('User', backref='custom_models')
    versions = db.relationship('CustomModelVersion', backref='custom_model', lazy=True, cascade="all, delete-orphan")

    # Constraints and indexes
    __table_args__ = (
        CheckConstraint('name IS NOT NULL AND length(name) >= 3', name='check_model_name'),
        Index('idx_custom_models_user_status', 'user_id', 'status'),
        Index('idx_custom_models_type', 'model_type'),
        Index('idx_custom_models_public', 'is_public'),
    )

    def __repr__(self):
        return f'<CustomModel {self.name} by {self.user.username}>'

class CustomModelVersion(db.Model):
    """Version history for custom models."""
    __tablename__ = 'custom_model_versions'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    custom_model_id = db.Column(UUID(as_uuid=True), db.ForeignKey('custom_models.id'), nullable=False)
    version_number = db.Column(db.Integer, nullable=False)
    code_content = db.Column(db.Text, nullable=False)
    config = db.Column(JSONB, nullable=True)
    commit_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.now())

    # Relationships
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=False)
    user = db.relationship('User', backref='model_versions')

    # Constraints
    __table_args__ = (
        CheckConstraint('version_number > 0', name='check_version_positive'),
        Index('idx_custom_model_versions_model_version', 'custom_model_id', 'version_number'),
    )

    def __repr__(self):
        return f'<CustomModelVersion v{self.version_number} of {self.custom_model.name}>'

class ExportJob(db.Model):
    """Background jobs for exporting data and reports."""
    __tablename__ = 'export_jobs'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=False)
    job_type = db.Column(db.String(50), nullable=False)  # 'training_report', 'model_export', etc.
    status = db.Column(db.Enum(ExportStatus), default=ExportStatus.PENDING, nullable=False)

    # Export configuration
    export_config = db.Column(JSONB, nullable=False)  # Export parameters
    source_id = db.Column(UUID(as_uuid=True), nullable=True)  # Source resource ID

    # Results
    file_paths = db.Column(JSONB, nullable=True)  # Generated file paths
    download_url = db.Column(db.String(512), nullable=True)
    file_size_bytes = db.Column(db.BigInteger, nullable=True)

    # Processing
    celery_task_id = db.Column(db.String(128), nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    progress_percentage = db.Column(db.Integer, default=0)

    # Timestamps
    created_at = db.Column(db.DateTime, default=db.func.now())
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    user = db.relationship('User', backref='export_jobs')

    # Constraints and indexes
    __table_args__ = (
        CheckConstraint('progress_percentage >= 0 AND progress_percentage <= 100', name='check_progress_range'),
        Index('idx_export_jobs_user_status', 'user_id', 'status'),
        Index('idx_export_jobs_type', 'job_type'),
        Index('idx_export_jobs_expires', 'expires_at'),
    )

    def is_expired(self):
        """Check if export job has expired."""
        if not self.expires_at:
            return False
        return datetime.datetime.utcnow() > self.expires_at

    def __repr__(self):
        return f'<ExportJob {self.job_type} for {self.user.username}>'

class DataQualityReport(db.Model):
    """Data quality analysis reports."""
    __tablename__ = 'data_quality_reports'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=False)
    task_id = db.Column(UUID(as_uuid=True), db.ForeignKey('tasks.id'), nullable=True)
    file_path = db.Column(db.String(512), nullable=False)

    # Quality metrics
    overall_score = db.Column(db.Float, nullable=False)  # 0-100
    completeness_score = db.Column(db.Float, nullable=False)
    consistency_score = db.Column(db.Float, nullable=False)
    validity_score = db.Column(db.Float, nullable=False)

    # Detailed analysis
    row_count = db.Column(db.Integer, nullable=False)
    column_count = db.Column(db.Integer, nullable=False)
    duplicate_count = db.Column(db.Integer, default=0)
    missing_value_counts = db.Column(JSONB, nullable=True)
    data_types = db.Column(JSONB, nullable=True)
    outliers_detected = db.Column(JSONB, nullable=True)

    # Recommendations
    cleaning_recommendations = db.Column(JSONB, nullable=True)
    feature_engineering_suggestions = db.Column(JSONB, nullable=True)

    # Metadata
    created_at = db.Column(db.DateTime, default=db.func.now())
    analysis_duration_seconds = db.Column(db.Float, nullable=True)

    # Relationships
    user = db.relationship('User', backref='data_quality_reports')
    task = db.relationship('Task', backref='data_quality_reports')

    # Constraints
    __table_args__ = (
        CheckConstraint('overall_score >= 0 AND overall_score <= 100', name='check_overall_score_range'),
        CheckConstraint('completeness_score >= 0 AND completeness_score <= 100', name='check_completeness_score_range'),
        CheckConstraint('consistency_score >= 0 AND consistency_score <= 100', name='check_consistency_score_range'),
        CheckConstraint('validity_score >= 0 AND validity_score <= 100', name='check_validity_score_range'),
        Index('idx_data_quality_user_task', 'user_id', 'task_id'),
        Index('idx_data_quality_score', 'overall_score'),
    )

    def __repr__(self):
        return f'<DataQualityReport {self.overall_score}% for {self.file_path}>'

class SecurityEvent(db.Model):
    """Security events for monitoring and analysis."""
    __tablename__ = 'security_events'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type = db.Column(db.String(100), nullable=False)  # 'sql_injection', 'brute_force', etc.
    severity = db.Column(db.Enum(SecurityEventSeverity), nullable=False)

    # Event details
    description = db.Column(db.Text, nullable=False)
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.Text, nullable=True)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=True)

    # Additional context
    request_path = db.Column(db.String(512), nullable=True)
    request_method = db.Column(db.String(10), nullable=True)
    details = db.Column(JSONB, nullable=True)

    # Resolution
    resolved = db.Column(db.Boolean, default=False)
    resolved_by = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=True)
    resolution_notes = db.Column(db.Text, nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=db.func.now())
    resolved_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    user = db.relationship('User', backref='security_events', foreign_keys=[user_id])
    resolver = db.relationship('User', backref='resolved_events', foreign_keys=[resolved_by])

    # Indexes for security queries
    __table_args__ = (
        Index('idx_security_events_type_severity', 'event_type', 'severity'),
        Index('idx_security_events_ip', 'ip_address'),
        Index('idx_security_events_created', 'created_at'),
        Index('idx_security_events_resolved', 'resolved'),
    )

    def __repr__(self):
        return f'<SecurityEvent {self.event_type} - {self.severity.value}>'