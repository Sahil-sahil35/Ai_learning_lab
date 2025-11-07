"""
Health monitoring and metrics endpoints for system status and performance tracking.
Provides comprehensive health checks and performance metrics.
"""

import os
import psutil
import time
from datetime import datetime, timedelta
from flask import Blueprint, jsonify, current_app
from sqlalchemy import text
from .. import db
from ..utils.logger import get_logger
from ..utils.error_handlers import DatabaseError, ExternalServiceError

health_bp = Blueprint('health_bp', __name__)
logger = get_logger('health')

def check_database_health():
    """Check database connectivity and performance."""
    try:
        start_time = time.time()

        # Test basic connectivity
        result = db.session.execute(text('SELECT 1'))
        result.fetchone()

        query_time = (time.time() - start_time) * 1000  # Convert to ms

        # Check connection pool stats
        engine = db.engine
        pool = engine.pool

        return {
            'status': 'healthy',
            'response_time_ms': round(query_time, 2),
            'connection_pool': {
                'size': pool.size(),
                'checked_in': pool.checkedin(),
                'checked_out': pool.checkedout(),
                'overflow': pool.overflow()
            }
        }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            'status': 'unhealthy',
            'error': str(e),
            'response_time_ms': None
        }

def check_redis_health():
    """Check Redis connectivity and performance."""
    try:
        if not redis_client:
            return {'status': 'not_configured'}

        start_time = time.time()

        # Test Redis operations
        test_key = f'health_check_{int(time.time())}'
        redis_client.set(test_key, 'test', ex=10)
        value = redis_client.get(test_key)
        redis_client.delete(test_key)

        response_time = (time.time() - start_time) * 1000

        # Get Redis info
        info = redis_client.info()

        return {
            'status': 'healthy',
            'response_time_ms': round(response_time, 2),
            'memory_usage_mb': round(info.get('used_memory', 0) / 1024 / 1024, 2),
            'connected_clients': info.get('connected_clients', 0),
            'total_commands_processed': info.get('total_commands_processed', 0)
        }
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        return {
            'status': 'unhealthy',
            'error': str(e),
            'response_time_ms': None
        }

def check_system_resources():
    """Check system resource usage."""
    try:
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)

        # Memory usage
        memory = psutil.virtual_memory()
        memory_usage = {
            'total_gb': round(memory.total / 1024 / 1024 / 1024, 2),
            'available_gb': round(memory.available / 1024 / 1024 / 1024, 2),
            'used_gb': round(memory.used / 1024 / 1024 / 1024, 2),
            'percent': memory.percent
        }

        # Disk usage
        disk = psutil.disk_usage('/')
        disk_usage = {
            'total_gb': round(disk.total / 1024 / 1024 / 1024, 2),
            'free_gb': round(disk.free / 1024 / 1024 / 1024, 2),
            'used_gb': round(disk.used / 1024 / 1024 / 1024, 2),
            'percent': round((disk.used / disk.total) * 100, 2)
        }

        # Process info
        process = psutil.Process()
        process_info = {
            'cpu_percent': process.cpu_percent(),
            'memory_mb': round(process.memory_info().rss / 1024 / 1024, 2),
            'threads': process.num_threads(),
            'uptime_seconds': time.time() - process.create_time()
        }

        return {
            'cpu_percent': cpu_percent,
            'memory': memory_usage,
            'disk': disk_usage,
            'process': process_info
        }
    except Exception as e:
        logger.error(f"System resource check failed: {e}")
        return {
            'status': 'error',
            'error': str(e)
        }

def check_docker_health():
    """Check Docker daemon and container status."""
    try:
        import docker

        client = docker.from_env()
        client.ping()

        # Get container stats
        containers = client.containers.list(all=True)

        container_stats = []
        for container in containers[:10]:  # Limit to first 10 containers
            try:
                stats = container.stats(stream=False)
                container_stats.append({
                    'name': container.name,
                    'status': container.status,
                    'cpu_percent': round(stats.get('cpu_stats', {}).get('cpu_usage', {}).get('total_usage', 0) / 1000000, 2),
                    'memory_mb': round(stats.get('memory_stats', {}).get('usage', 0) / 1024 / 1024, 2)
                })
            except Exception:
                continue

        return {
            'status': 'healthy',
            'total_containers': len(containers),
            'running_containers': len([c for c in containers if c.status == 'running']),
            'container_stats': container_stats[:5]  # Return only first 5 for brevity
        }
    except ImportError:
        return {'status': 'not_available', 'message': 'Docker Python library not installed'}
    except Exception as e:
        logger.error(f"Docker health check failed: {e}")
        return {
            'status': 'unhealthy',
            'error': str(e)
        }

def get_application_metrics():
    """Get application-specific metrics."""
    try:
        # Get recent training jobs (mock implementation)
        # In a real implementation, this would query the database
        training_metrics = {
            'total_jobs': 0,
            'running_jobs': 0,
            'completed_jobs_today': 0,
            'failed_jobs_today': 0,
            'average_training_time_minutes': 0
        }

        # User metrics
        user_metrics = {
            'total_users': 0,
            'active_users_today': 0,
            'new_users_today': 0
        }

        # API metrics
        api_metrics = {
            'requests_last_hour': 0,
            'average_response_time_ms': 0,
            'error_rate_percent': 0
        }

        return {
            'training': training_metrics,
            'users': user_metrics,
            'api': api_metrics
        }
    except Exception as e:
        logger.error(f"Application metrics collection failed: {e}")
        return {
            'status': 'error',
            'error': str(e)
        }

@health_bp.route('/health', methods=['GET'])
def health_check():
    """Basic health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'version': os.getenv('APP_VERSION', 'unknown'),
        'environment': os.getenv('FLASK_CONFIG', 'unknown')
    }), 200

@health_bp.route('/health/detailed', methods=['GET'])
def detailed_health_check():
    """Comprehensive health check with all system components."""
    start_time = time.time()

    # Run all health checks
    database_health = check_database_health()
    redis_health = check_redis_health()
    system_resources = check_system_resources()
    docker_health = check_docker_health()
    application_metrics = get_application_metrics()

    # Determine overall health status
    checks = [database_health, redis_health, docker_health]
    unhealthy_checks = [c for c in checks if c.get('status') == 'unhealthy']

    overall_status = 'healthy' if not unhealthy_checks else 'degraded' if len(unhealthy_checks) == 1 else 'unhealthy'
    status_code = 200 if overall_status == 'healthy' else 503 if overall_status == 'unhealthy' else 200

    response_time = (time.time() - start_time) * 1000

    response_data = {
        'status': overall_status,
        'timestamp': datetime.utcnow().isoformat(),
        'response_time_ms': round(response_time, 2),
        'checks': {
            'database': database_health,
            'redis': redis_health,
            'docker': docker_health,
            'system_resources': system_resources
        },
        'metrics': application_metrics,
        'environment': {
            'version': os.getenv('APP_VERSION', 'unknown'),
            'config': os.getenv('FLASK_CONFIG', 'unknown'),
            'hostname': os.getenv('HOSTNAME', os.uname().nodename)
        }
    }

    return jsonify(response_data), status_code

@health_bp.route('/metrics', methods=['GET'])
def metrics():
    """Prometheus-style metrics endpoint."""
    try:
        system_resources = check_system_resources()
        database_health = check_database_health()
        redis_health = check_redis_health()

        # Convert to Prometheus format
        metrics_text = f"""# HELP ai_learning_lab_system_cpu_percent CPU usage percentage
# TYPE ai_learning_lab_system_cpu_percent gauge
ai_learning_lab_system_cpu_percent {system_resources.get('cpu_percent', 0)}

# HELP ai_learning_lab_system_memory_percent Memory usage percentage
# TYPE ai_learning_lab_system_memory_percent gauge
ai_learning_lab_system_memory_percent {system_resources.get('memory', {}).get('percent', 0)}

# HELP ai_learning_lab_system_disk_percent Disk usage percentage
# TYPE ai_learning_lab_system_disk_percent gauge
ai_learning_lab_system_disk_percent {system_resources.get('disk', {}).get('percent', 0)}

# HELP ai_learning_lab_database_response_time_ms Database response time in milliseconds
# TYPE ai_learning_lab_database_response_time_ms gauge
ai_learning_lab_database_response_time_ms {database_health.get('response_time_ms', 0)}

# HELP ai_learning_lab_redis_response_time_ms Redis response time in milliseconds
# TYPE ai_learning_lab_redis_response_time_ms gauge
ai_learning_lab_redis_response_time_ms {redis_health.get('response_time_ms', 0)}

# HELP ai_learning_lab_up Application uptime indicator
# TYPE ai_learning_lab_up gauge
ai_learning_lab_up 1
"""

        return metrics_text, 200, {'Content-Type': 'text/plain; charset=utf-8'}

    except Exception as e:
        logger.error(f"Metrics collection failed: {e}")
        return "Error collecting metrics", 500, {'Content-Type': 'text/plain; charset=utf-8'}

@health_bp.route('/health/ready', methods=['GET'])
def readiness_check():
    """Kubernetes readiness probe - checks if application is ready to serve traffic."""
    database_health = check_database_health()

    if database_health.get('status') == 'healthy':
        return jsonify({
            'status': 'ready',
            'timestamp': datetime.utcnow().isoformat()
        }), 200
    else:
        return jsonify({
            'status': 'not_ready',
            'reason': 'database_unhealthy',
            'timestamp': datetime.utcnow().isoformat()
        }), 503

@health_bp.route('/health/live', methods=['GET'])
def liveness_check():
    """Kubernetes liveness probe - checks if application is alive."""
    return jsonify({
        'status': 'alive',
        'timestamp': datetime.utcnow().isoformat()
    }), 200