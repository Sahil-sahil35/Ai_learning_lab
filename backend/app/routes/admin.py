"""
Admin panel API routes for user management, platform monitoring,
and administrative operations.
"""

import datetime
import uuid
from functools import wraps
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from sqlalchemy import func, desc, or_, and_
from sqlalchemy.orm import joinedload

from .. import db
from ..models import User, Task, ModelRun
from ..models.enhanced import (
    AdminLog, SystemMetrics, UserSession, CustomModel, ExportJob,
    DataQualityReport, SecurityEvent, UserRole, ExportStatus
)
from ..middleware.security import security_monitor
from ..middleware.rate_limiter import rate_limit
from ..schemas import UserSchema, TaskSchema, ModelRunSchema

admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')

# Decorator for admin access
def admin_required(required_role=UserRole.ADMIN):
    """Decorator to require admin access."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get current user
            user_id = get_jwt_identity()
            user = User.query.get(user_id)

            if not user:
                return jsonify({'error': 'User not found'}), 404

            # Check if user has required role
            role_hierarchy = {
                UserRole.STUDENT: 0,
                UserRole.ADMIN: 1,
                UserRole.SUPER_ADMIN: 2
            }

            if role_hierarchy.get(user.role, 0) < role_hierarchy.get(required_role, 1):
                return jsonify({'error': 'Admin access required'}), 403

            # Log admin action
            admin_action = AdminLog(
                admin_id=user.id,
                action=f"accessed_{request.endpoint}",
                resource_type="admin_endpoint",
                details={'method': request.method, 'args': dict(request.args)},
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent')
            )
            db.session.add(admin_action)
            db.session.commit()

            return f(*args, **kwargs)
        return decorated_function
    return decorator

@admin_bp.route('/users', methods=['GET'])
@jwt_required()
@admin_required()
@rate_limit('admin')
def get_users():
    """Get paginated list of all users with filtering options."""
    try:
        # Pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)

        # Filters
        role_filter = request.args.get('role')
        status_filter = request.args.get('status')  # 'active', 'inactive'
        search = request.args.get('search', '')

        # Build query
        query = User.query

        # Apply filters
        if role_filter:
            try:
                role_enum = UserRole(role_filter)
                query = query.filter(User.role == role_enum)
            except ValueError:
                pass

        if status_filter == 'active':
            query = query.filter(User.is_active == True)
        elif status_filter == 'inactive':
            query = query.filter(User.is_active == False)

        if search:
            query = query.filter(
                or_(
                    User.username.ilike(f'%{search}%'),
                    User.email.ilike(f'%{search}%')
                )
            )

        # Order by creation date (newest first)
        query = query.order_by(desc(User.created_at))

        # Paginate
        paginated_users = query.paginate(
            page=page, per_page=per_page, error_out=False
        )

        # Serialize users
        user_schema = UserSchema(many=True, exclude=['password_hash'])
        users_data = user_schema.dump(paginated_users.items)

        # Add statistics for each user
        for i, user in enumerate(paginated_users.items):
            # Count tasks and model runs
            task_count = Task.query.filter_by(user_id=user.id).count()
            model_run_count = ModelRun.query.filter_by(user_id=user.id).count()
            custom_model_count = CustomModel.query.filter_by(user_id=user.id).count()

            users_data[i]['stats'] = {
                'tasks_count': task_count,
                'model_runs_count': model_run_count,
                'custom_models_count': custom_model_count,
                'last_login': user.last_login.isoformat() if user.last_login else None
            }

        return jsonify({
            'users': users_data,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': paginated_users.total,
                'pages': paginated_users.pages,
                'has_next': paginated_users.has_next,
                'has_prev': paginated_users.has_prev
            }
        })

    except Exception as e:
        current_app.logger.error(f"Error fetching users: {e}")
        return jsonify({'error': 'Failed to fetch users'}), 500

@admin_bp.route('/users/<uuid:user_id>', methods=['GET'])
@jwt_required()
@admin_required()
@rate_limit('admin')
def get_user_detail(user_id):
    """Get detailed information about a specific user."""
    try:
        user = User.query.get_or_404(user_id)

        # User details
        user_schema = UserSchema(exclude=['password_hash'])
        user_data = user_schema.dump(user)

        # Detailed statistics
        tasks = Task.query.filter_by(user_id=user_id).all()
        model_runs = ModelRun.query.filter_by(user_id=user_id).all()
        custom_models = CustomModel.query.filter_by(user_id=user_id).all()

        # Recent activity
        recent_model_runs = ModelRun.query.filter_by(user_id=user_id)\
            .order_by(desc(ModelRun.created_at))\
            .limit(10).all()

        model_run_schema = ModelRunSchema(many=True)
        recent_activity = model_run_schema.dump(recent_model_runs)

        # Storage usage
        storage_usage = 0
        for run in model_runs:
            if run.original_data_path:
                # This would require actual file system integration
                storage_usage += 0  # Placeholder

        # Resource usage
        resource_usage = {
            'total_tasks': len(tasks),
            'total_model_runs': len(model_runs),
            'total_custom_models': len(custom_models),
            'successful_runs': len([r for r in model_runs if r.status == 'SUCCESS']),
            'failed_runs': len([r for r in model_runs if r.status == 'FAILED']),
            'storage_usage_bytes': storage_usage,
            'account_age_days': (datetime.datetime.utcnow() - user.created_at).days
        }

        return jsonify({
            'user': user_data,
            'resource_usage': resource_usage,
            'recent_activity': recent_activity
        })

    except Exception as e:
        current_app.logger.error(f"Error fetching user detail: {e}")
        return jsonify({'error': 'Failed to fetch user details'}), 500

@admin_bp.route('/users/<uuid:user_id>/suspend', methods=['POST'])
@jwt_required()
@admin_required()
@rate_limit('admin')
def suspend_user(user_id):
    """Suspend or unsuspend a user account."""
    try:
        data = request.get_json()
        suspend = data.get('suspend', True)
        reason = data.get('reason', 'Administrative action')

        user = User.query.get_or_404(user_id)
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)

        # Don't allow self-suspension
        if str(user_id) == current_user_id:
            return jsonify({'error': 'Cannot suspend your own account'}), 400

        # Don't allow suspending super admins unless current user is super admin
        if user.role == UserRole.SUPER_ADMIN and current_user.role != UserRole.SUPER_ADMIN:
            return jsonify({'error': 'Cannot suspend super admin account'}), 403

        user.is_active = not suspend

        # Log the action
        admin_action = AdminLog(
            admin_id=current_user_id,
            action='suspend_user' if suspend else 'unsuspend_user',
            resource_type='user',
            resource_id=user_id,
            details={
                'target_user': user.username,
                'reason': reason,
                'previous_status': not user.is_active
            },
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )
        db.session.add(admin_action)
        db.session.commit()

        return jsonify({
            'message': f"User {'suspended' if suspend else 'unsuspended'} successfully",
            'user': {
                'id': str(user.id),
                'username': user.username,
                'is_active': user.is_active
            }
        })

    except Exception as e:
        current_app.logger.error(f"Error suspending user: {e}")
        db.session.rollback()
        return jsonify({'error': 'Failed to update user status'}), 500

@admin_bp.route('/users/<uuid:user_id>/role', methods=['POST'])
@jwt_required()
@admin_required(UserRole.SUPER_ADMIN)
@rate_limit('admin')
def update_user_role(user_id):
    """Update user role (super admin only)."""
    try:
        data = request.get_json()
        new_role = data.get('role')
        reason = data.get('reason', 'Role update by super admin')

        if new_role not in [role.value for role in UserRole]:
            return jsonify({'error': 'Invalid role'}), 400

        user = User.query.get_or_404(user_id)
        current_user_id = get_jwt_identity()

        # Don't allow self role changes
        if str(user_id) == current_user_id:
            return jsonify({'error': 'Cannot change your own role'}), 400

        old_role = user.role.value
        user.role = UserRole(new_role)

        # Log the action
        admin_action = AdminLog(
            admin_id=current_user_id,
            action='update_user_role',
            resource_type='user',
            resource_id=user_id,
            details={
                'target_user': user.username,
                'old_role': old_role,
                'new_role': new_role,
                'reason': reason
            },
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )
        db.session.add(admin_action)
        db.session.commit()

        return jsonify({
            'message': 'User role updated successfully',
            'user': {
                'id': str(user.id),
                'username': user.username,
                'role': user.role.value
            }
        })

    except Exception as e:
        current_app.logger.error(f"Error updating user role: {e}")
        db.session.rollback()
        return jsonify({'error': 'Failed to update user role'}), 500

@admin_bp.route('/analytics', methods=['GET'])
@jwt_required()
@admin_required()
@rate_limit('admin')
def get_analytics():
    """Get platform analytics and usage statistics."""
    try:
        # Time range filter
        days = request.args.get('days', 30, type=int)
        start_date = datetime.datetime.utcnow() - datetime.timedelta(days=days)

        # User statistics
        total_users = User.query.count()
        active_users = User.query.filter(User.last_login >= start_date).count()
        new_users = User.query.filter(User.created_at >= start_date).count()

        # User by role
        users_by_role = db.session.query(
            User.role, func.count(User.id)
        ).group_by(User.role).all()

        # Task and model run statistics
        total_tasks = Task.query.count()
        tasks_in_period = Task.query.filter(Task.created_at >= start_date).count()
        total_model_runs = ModelRun.query.count()
        runs_in_period = ModelRun.query.filter(ModelRun.created_at >= start_date).count()

        # Model run status distribution
        runs_by_status = db.session.query(
            ModelRun.status, func.count(ModelRun.id)
        ).group_by(ModelRun.status).all()

        # Custom model statistics
        total_custom_models = CustomModel.query.count()
        custom_models_in_period = CustomModel.query.filter(
            CustomModel.created_at >= start_date
        ).count()

        # System metrics
        recent_metrics = SystemMetrics.query.filter(
            SystemMetrics.timestamp >= start_date
        ).order_by(desc(SystemMetrics.timestamp)).all()

        # Export job statistics
        total_exports = ExportJob.query.count()
        exports_in_period = ExportJob.query.filter(
            ExportJob.created_at >= start_date
        ).count()

        # Security events
        security_events_in_period = SecurityEvent.query.filter(
            SecurityEvent.created_at >= start_date
        ).count()

        return jsonify({
            'period': {
                'days': days,
                'start_date': start_date.isoformat(),
                'end_date': datetime.datetime.utcnow().isoformat()
            },
            'users': {
                'total': total_users,
                'active': active_users,
                'new': new_users,
                'by_role': [{role.value: count} for role, count in users_by_role]
            },
            'tasks': {
                'total': total_tasks,
                'new': tasks_in_period
            },
            'model_runs': {
                'total': total_model_runs,
                'new': runs_in_period,
                'by_status': [{status: count} for status, count in runs_by_status]
            },
            'custom_models': {
                'total': total_custom_models,
                'new': custom_models_in_period
            },
            'exports': {
                'total': total_exports,
                'new': exports_in_period
            },
            'security': {
                'events_in_period': security_events_in_period
            },
            'system_metrics': [
                {
                    'name': metric.metric_name,
                    'value': metric.metric_value,
                    'unit': metric.metric_unit,
                    'timestamp': metric.timestamp.isoformat()
                } for metric in recent_metrics[-100:]  # Last 100 metrics
            ]
        })

    except Exception as e:
        current_app.logger.error(f"Error fetching analytics: {e}")
        return jsonify({'error': 'Failed to fetch analytics'}), 500

@admin_bp.route('/tasks', methods=['GET'])
@jwt_required()
@admin_required()
@rate_limit('admin')
def get_all_tasks():
    """Get all tasks in the system with admin visibility."""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)

        # Filters
        status_filter = request.args.get('status')
        user_id_filter = request.args.get('user_id')

        query = Task.query.options(
            joinedload(Task.owner),
            joinedload(Task.model_runs)
        )

        # Apply filters
        if user_id_filter:
            try:
                query = query.filter(Task.user_id == uuid.UUID(user_id_filter))
            except ValueError:
                pass

        # Order by creation date
        query = query.order_by(desc(Task.created_at))

        # Paginate
        paginated_tasks = query.paginate(
            page=page, per_page=per_page, error_out=False
        )

        # Serialize tasks
        task_schema = TaskSchema(many=True)
        tasks_data = task_schema.dump(paginated_tasks.items)

        # Add user information and model run counts
        for i, task in enumerate(paginated_tasks.items):
            tasks_data[i]['owner'] = {
                'id': str(task.owner.id),
                'username': task.owner.username,
                'email': task.owner.email,
                'role': task.owner.role.value
            }
            tasks_data[i]['model_runs_count'] = len(task.model_runs)

        return jsonify({
            'tasks': tasks_data,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': paginated_tasks.total,
                'pages': paginated_tasks.pages,
                'has_next': paginated_tasks.has_next,
                'has_prev': paginated_tasks.has_prev
            }
        })

    except Exception as e:
        current_app.logger.error(f"Error fetching tasks: {e}")
        return jsonify({'error': 'Failed to fetch tasks'}), 500

@admin_bp.route('/system/maintenance', methods=['POST'])
@jwt_required()
@admin_required(UserRole.SUPER_ADMIN)
@rate_limit('admin')
def toggle_maintenance():
    """Enable or disable maintenance mode."""
    try:
        data = request.get_json()
        enabled = data.get('enabled', True)
        message = data.get('message', 'System under maintenance')

        # Store maintenance mode in Redis or database
        # This is a simplified implementation
        maintenance_key = 'system:maintenance_mode'

        if enabled:
            # Set maintenance mode
            from redis import Redis
            redis_client = Redis.from_url(current_app.config['REDIS_URL'])
            redis_client.set(
                maintenance_key,
                str({'enabled': True, 'message': message, 'set_at': datetime.datetime.utcnow().isoformat()}),
                ex=3600  # Expire after 1 hour
            )
        else:
            # Disable maintenance mode
            from redis import Redis
            redis_client = Redis.from_url(current_app.config['REDIS_URL'])
            redis_client.delete(maintenance_key)

        # Log the action
        current_user_id = get_jwt_identity()
        admin_action = AdminLog(
            admin_id=current_user_id,
            action='toggle_maintenance',
            resource_type='system',
            details={
                'enabled': enabled,
                'message': message
            },
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )
        db.session.add(admin_action)
        db.session.commit()

        return jsonify({
            'message': f"Maintenance mode {'enabled' if enabled else 'disabled'}",
            'maintenance': {
                'enabled': enabled,
                'message': message if enabled else None
            }
        })

    except Exception as e:
        current_app.logger.error(f"Error toggling maintenance mode: {e}")
        return jsonify({'error': 'Failed to update maintenance mode'}), 500

@admin_bp.route('/logs/security', methods=['GET'])
@jwt_required()
@admin_required()
@rate_limit('admin')
def get_security_logs():
    """Get security event logs."""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 50, type=int), 200)

        # Filters
        severity_filter = request.args.get('severity')
        event_type_filter = request.args.get('event_type')
        resolved_filter = request.args.get('resolved')

        query = SecurityEvent.query.options(
            joinedload(SecurityEvent.user)
        )

        # Apply filters
        if severity_filter:
            try:
                from .models.enhanced import SecurityEventSeverity
                severity_enum = SecurityEventSeverity(severity_filter)
                query = query.filter(SecurityEvent.severity == severity_enum)
            except ValueError:
                pass

        if event_type_filter:
            query = query.filter(SecurityEvent.event_type == event_type_filter)

        if resolved_filter is not None:
            query = query.filter(SecurityEvent.resolved == (resolved_filter.lower() == 'true'))

        # Order by creation date
        query = query.order_by(desc(SecurityEvent.created_at))

        # Paginate
        paginated_events = query.paginate(
            page=page, per_page=per_page, error_out=False
        )

        events_data = []
        for event in paginated_events.items:
            event_data = {
                'id': str(event.id),
                'event_type': event.event_type,
                'severity': event.severity.value,
                'description': event.description,
                'ip_address': event.ip_address,
                'user_agent': event.user_agent,
                'request_path': event.request_path,
                'request_method': event.request_method,
                'resolved': event.resolved,
                'created_at': event.created_at.isoformat(),
                'details': event.details
            }

            if event.user:
                event_data['user'] = {
                    'id': str(event.user.id),
                    'username': event.user.username,
                    'email': event.user.email
                }

            if event.resolved and event.resolver:
                event_data['resolver'] = {
                    'id': str(event.resolver.id),
                    'username': event.resolver.username
                }
                event_data['resolved_at'] = event.resolved_at.isoformat()
                event_data['resolution_notes'] = event.resolution_notes

            events_data.append(event_data)

        return jsonify({
            'events': events_data,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': paginated_events.total,
                'pages': paginated_events.pages,
                'has_next': paginated_events.has_next,
                'has_prev': paginated_events.has_prev
            }
        })

    except Exception as e:
        current_app.logger.error(f"Error fetching security logs: {e}")
        return jsonify({'error': 'Failed to fetch security logs'}), 500

@admin_bp.route('/notifications/send', methods=['POST'])
@jwt_required()
@admin_required()
@rate_limit('admin')
def send_notification():
    """Send system notification to users."""
    try:
        data = request.get_json()
        message = data.get('message', '')
        target_users = data.get('target_users', 'all')  # 'all', 'students', 'admins', or list of user IDs
        notification_type = data.get('type', 'info')  # 'info', 'warning', 'error'
        title = data.get('title', 'System Notification')

        if not message:
            return jsonify({'error': 'Message is required'}), 400

        current_user_id = get_jwt_identity()

        # Determine target users
        target_user_ids = []
        if target_users == 'all':
            users = User.query.filter(User.is_active == True).all()
            target_user_ids = [user.id for user in users]
        elif target_users == 'students':
            users = User.query.filter(
                and_(User.role == UserRole.STUDENT, User.is_active == True)
            ).all()
            target_user_ids = [user.id for user in users]
        elif target_users == 'admins':
            users = User.query.filter(
                and_(
                    User.role.in_([UserRole.ADMIN, UserRole.SUPER_ADMIN]),
                    User.is_active == True
                )
            ).all()
            target_user_ids = [user.id for user in users]
        elif isinstance(target_users, list):
            # Convert string IDs to UUID
            for user_id_str in target_users:
                try:
                    target_user_ids.append(uuid.UUID(user_id_str))
                except ValueError:
                    continue

        # Store notifications (simplified - in production would use a proper notification system)
        notification_data = {
            'title': title,
            'message': message,
            'type': notification_type,
            'created_by': current_user_id,
            'created_at': datetime.datetime.utcnow().isoformat(),
            'target_count': len(target_user_ids)
        }

        # Log the action
        admin_action = AdminLog(
            admin_id=current_user_id,
            action='send_notification',
            resource_type='notification',
            details=notification_data,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )
        db.session.add(admin_action)
        db.session.commit()

        return jsonify({
            'message': 'Notification sent successfully',
            'notification': notification_data
        })

    except Exception as e:
        current_app.logger.error(f"Error sending notification: {e}")
        return jsonify({'error': 'Failed to send notification'}), 500