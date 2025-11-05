"""Enhanced schema for admin functionality, custom models, and advanced features.

Revision ID: enhanced_schema
Revises: b044a3b981e6
Create Date: 2025-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'enhanced_schema'
down_revision = 'b044a3b981e6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enum types
    op.execute("CREATE TYPE userrole AS ENUM ('student', 'admin', 'super_admin')")
    op.execute("CREATE TYPE exportstatus AS ENUM ('pending', 'processing', 'completed', 'failed', 'expired')")
    op.execute("CREATE TYPE custommodelstatus AS ENUM ('draft', 'validating', 'validated', 'training', 'trained', 'deployed', 'failed')")
    op.execute("CREATE TYPE securityeventseverity AS ENUM ('low', 'medium', 'high', 'critical')")

    # Add new columns to users table
    try:
        op.add_column('users', sa.Column('role', sa.Enum('student', 'admin', 'super_admin', name='userrole'), nullable=False, server_default='student'))
    except Exception as e:
        print(f"Role column addition failed (may already exist): {e}")

    try:
        op.add_column('users', sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'))
    except Exception as e:
        print(f"is_active column addition failed (may already exist): {e}")

    try:
        op.add_column('users', sa.Column('last_login', sa.DateTime(), nullable=True))
    except Exception as e:
        print(f"last_login column addition failed (may already exist): {e}")

    try:
        op.add_column('users', sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.text('now()')))
    except Exception as e:
        print(f"updated_at column addition failed (may already exist): {e}")

    # Update existing users to have default role if needed
    try:
        op.execute("UPDATE users SET role = 'student' WHERE role IS NULL")
        op.execute("UPDATE users SET is_active = true WHERE is_active IS NULL")
    except Exception as e:
        print(f"Update existing users failed: {e}")

    # Create admin_logs table
    op.create_table('admin_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('admin_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('resource_type', sa.String(length=50), nullable=False),
        sa.Column('resource_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['admin_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_admin_logs_admin_timestamp', 'admin_logs', ['admin_id', 'timestamp'])
    op.create_index('idx_admin_logs_action', 'admin_logs', ['action'])
    op.create_index('idx_admin_logs_timestamp', 'admin_logs', ['timestamp'])

    # Create system_metrics table
    op.create_table('system_metrics',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('metric_name', sa.String(length=100), nullable=False),
        sa.Column('metric_value', sa.Float(), nullable=False),
        sa.Column('metric_unit', sa.String(length=20), nullable=True),
        sa.Column('tags', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_system_metrics_name_timestamp', 'system_metrics', ['metric_name', 'timestamp'])
    op.create_index('idx_system_metrics_timestamp', 'system_metrics', ['timestamp'])

    # Create user_sessions table
    op.create_table('user_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('session_token', sa.String(length=255), nullable=False),
        sa.Column('ip_address', sa.String(length=45), nullable=False),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('last_activity', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('session_token')
    )
    op.create_index('idx_user_sessions_user', 'user_sessions', ['user_id'])
    op.create_index('idx_user_sessions_token', 'user_sessions', ['session_token'])
    op.create_index('idx_user_sessions_activity', 'user_sessions', ['last_activity'])

    # Create custom_models table
    op.create_table('custom_models',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('model_type', sa.String(length=50), nullable=False),
        sa.Column('status', sa.Enum('draft', 'validating', 'validated', 'training', 'trained', 'deployed', 'failed', name='custommodelstatus'), nullable=False),
        sa.Column('code_content', sa.Text(), nullable=True),
        sa.Column('requirements', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('config', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('training_data_path', sa.String(length=512), nullable=True),
        sa.Column('model_artifact_path', sa.String(length=512), nullable=True),
        sa.Column('training_metrics', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('template_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('is_public', sa.Boolean(), nullable=True),
        sa.Column('tags', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('trained_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['template_id'], ['custom_models.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_custom_models_user_status', 'custom_models', ['user_id', 'status'])
    op.create_index('idx_custom_models_type', 'custom_models', ['model_type'])
    op.create_index('idx_custom_models_public', 'custom_models', ['is_public'])

    # Create custom_model_versions table
    op.create_table('custom_model_versions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('custom_model_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('code_content', sa.Text(), nullable=False),
        sa.Column('config', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('commit_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(['custom_model_id'], ['custom_models.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_custom_model_versions_model_version', 'custom_model_versions', ['custom_model_id', 'version_number'])

    # Create export_jobs table
    op.create_table('export_jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('job_type', sa.String(length=50), nullable=False),
        sa.Column('status', sa.Enum('pending', 'processing', 'completed', 'failed', 'expired', name='exportstatus'), nullable=False),
        sa.Column('export_config', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('source_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('file_paths', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('download_url', sa.String(length=512), nullable=True),
        sa.Column('file_size_bytes', sa.BigInteger(), nullable=True),
        sa.Column('celery_task_id', sa.String(length=128), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('progress_percentage', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_export_jobs_user_status', 'export_jobs', ['user_id', 'status'])
    op.create_index('idx_export_jobs_type', 'export_jobs', ['job_type'])
    op.create_index('idx_export_jobs_expires', 'export_jobs', ['expires_at'])

    # Create data_quality_reports table
    op.create_table('data_quality_reports',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('task_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('file_path', sa.String(length=512), nullable=False),
        sa.Column('overall_score', sa.Float(), nullable=False),
        sa.Column('completeness_score', sa.Float(), nullable=False),
        sa.Column('consistency_score', sa.Float(), nullable=False),
        sa.Column('validity_score', sa.Float(), nullable=False),
        sa.Column('row_count', sa.Integer(), nullable=False),
        sa.Column('column_count', sa.Integer(), nullable=False),
        sa.Column('duplicate_count', sa.Integer(), nullable=True),
        sa.Column('missing_value_counts', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('data_types', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('outliers_detected', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('cleaning_recommendations', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('feature_engineering_suggestions', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('analysis_duration_seconds', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_data_quality_user_task', 'data_quality_reports', ['user_id', 'task_id'])
    op.create_index('idx_data_quality_score', 'data_quality_reports', ['overall_score'])

    # Create security_events table
    op.create_table('security_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('event_type', sa.String(length=100), nullable=False),
        sa.Column('severity', sa.Enum('low', 'medium', 'high', 'critical', name='securityeventseverity'), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('request_path', sa.String(length=512), nullable=True),
        sa.Column('request_method', sa.String(length=10), nullable=True),
        sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('resolved', sa.Boolean(), nullable=True),
        sa.Column('resolved_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['resolved_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_security_events_type_severity', 'security_events', ['event_type', 'severity'])
    op.create_index('idx_security_events_ip', 'security_events', ['ip_address'])
    op.create_index('idx_security_events_created', 'security_events', ['created_at'])
    op.create_index('idx_security_events_resolved', 'security_events', ['resolved'])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('security_events')
    op.drop_table('data_quality_reports')
    op.drop_table('export_jobs')
    op.drop_table('custom_model_versions')
    op.drop_table('custom_models')
    op.drop_table('user_sessions')
    op.drop_table('system_metrics')
    op.drop_table('admin_logs')

    # Drop columns from users table
    op.drop_column('users', 'updated_at')
    op.drop_column('users', 'last_login')
    op.drop_column('users', 'is_active')
    op.drop_column('users', 'role')

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS securityeventseverity")
    op.execute("DROP TYPE IF EXISTS custommodelstatus")
    op.execute("DROP TYPE IF EXISTS exportstatus")
    op.execute("DROP TYPE IF EXISTS userrole")