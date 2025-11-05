"""
Export functionality for training results, models, and reports.
Supports multiple formats and background processing.
"""

import os
import uuid
import json
import zipfile
import tempfile
import datetime
from pathlib import Path
from flask import Blueprint, request, jsonify, current_app, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity
from celery import current_task
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from reportlab.lib import colors

from .. import db
from ..models import User, ModelRun, Task
from ..models.enhanced import ExportJob, ExportStatus
from ..services.report_generator import ReportGenerator
from ..middleware.security import security_monitor
from ..middleware.rate_limiter import rate_limit

exports_bp = Blueprint('exports', __name__, url_prefix='/api/exports')

@exports_bp.route('/training/<uuid:model_run_id>', methods=['POST'])
@jwt_required()
@rate_limit('api')
def export_training_data(model_run_id):
    """Export training data and results."""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()

        # Validate model run exists and belongs to user
        model_run = ModelRun.query.filter_by(id=model_run_id, user_id=user_id).first()
        if not model_run:
            return jsonify({'error': 'Model run not found'}), 404

        # Create export job
        export_job = ExportJob(
            user_id=user_id,
            job_type='training_report',
            source_id=model_run_id,
            export_config={
                'format': data.get('format', 'pdf'),
                'include_data': data.get('include_data', False),
                'include_charts': data.get('include_charts', True),
                'include_code': data.get('include_code', False),
                'custom_sections': data.get('custom_sections', [])
            },
            status=ExportStatus.PENDING
        )
        db.session.add(export_job)
        db.session.commit()

        # Queue background job
        from ..tasks.export_tasks import generate_training_export
        task = generate_training_export.delay(export_job.id, str(model_run_id), data)

        # Update job with task ID
        export_job.celery_task_id = task.id
        db.session.commit()

        return jsonify({
            'message': 'Export job created successfully',
            'job_id': export_job.id,
            'estimated_time': '2-5 minutes'
        }), 202

    except Exception as e:
        current_app.logger.error(f"Error creating training export: {e}")
        return jsonify({'error': 'Failed to create export job'}), 500

@exports_bp.route('/model/<uuid:model_run_id>', methods=['POST'])
@jwt_required()
@rate_limit('api')
def export_model(model_run_id):
    """Export trained model in multiple formats."""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()

        # Validate model run exists and belongs to user
        model_run = ModelRun.query.filter_by(id=model_run_id, user_id=user_id).first()
        if not model_run:
            return jsonify({'error': 'Model run not found'}), 404

        # Check if model is trained
        if model_run.status != 'SUCCESS':
            return jsonify({'error': 'Model must be successfully trained before export'}), 400

        export_formats = data.get('formats', ['pickle'])
        valid_formats = ['pickle', 'joblib', 'onnx', 'h5', 'json']

        for fmt in export_formats:
            if fmt not in valid_formats:
                return jsonify({'error': f'Invalid export format: {fmt}'}), 400

        # Create export job
        export_job = ExportJob(
            user_id=user_id,
            job_type='model_export',
            source_id=model_run_id,
            export_config={
                'formats': export_formats,
                'include_metadata': data.get('include_metadata', True),
                'include_dependencies': data.get('include_dependencies', False),
                'compression': data.get('compression', False)
            },
            status=ExportStatus.PENDING
        )
        db.session.add(export_job)
        db.session.commit()

        # Queue background job
        from ..tasks.export_tasks import generate_model_export
        task = generate_model_export.delay(export_job.id, str(model_run_id), data)

        # Update job with task ID
        export_job.celery_task_id = task.id
        db.session.commit()

        return jsonify({
            'message': 'Model export job created successfully',
            'job_id': export_job.id,
            'estimated_time': '1-3 minutes'
        }), 202

    except Exception as e:
        current_app.logger.error(f"Error creating model export: {e}")
        return jsonify({'error': 'Failed to create export job'}), 500

@exports_bp.route('/report/<uuid:model_run_id>', methods=['POST'])
@jwt_required()
@rate_limit('api')
def generate_report(model_run_id):
    """Generate comprehensive training report."""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()

        # Validate model run exists and belongs to user
        model_run = ModelRun.query.filter_by(id=model_run_id, user_id=user_id).first()
        if not model_run:
            return jsonify({'error': 'Model run not found'}), 404

        report_type = data.get('type', 'comprehensive')
        format_type = data.get('format', 'pdf')

        if report_type not in ['summary', 'detailed', 'comprehensive']:
            return jsonify({'error': 'Invalid report type'}), 400

        if format_type not in ['pdf', 'html', 'json']:
            return jsonify({'error': 'Invalid format type'}), 400

        # Create export job
        export_job = ExportJob(
            user_id=user_id,
            job_type='training_report',
            source_id=model_run_id,
            export_config={
                'report_type': report_type,
                'format': format_type,
                'include_sections': data.get('include_sections', [
                    'overview', 'data_analysis', 'methodology',
                    'results', 'visualization', 'conclusions'
                ]),
                'custom_logo': data.get('custom_logo'),
                'company_info': data.get('company_info'),
                'custom_css': data.get('custom_css') if format_type == 'html' else None
            },
            status=ExportStatus.PENDING
        )
        db.session.add(export_job)
        db.session.commit()

        # Queue background job
        from ..tasks.export_tasks import generate_comprehensive_report
        task = generate_comprehensive_report.delay(export_job.id, str(model_run_id), data)

        # Update job with task ID
        export_job.celery_task_id = task.id
        db.session.commit()

        return jsonify({
            'message': 'Report generation job created successfully',
            'job_id': export_job.id,
            'estimated_time': '3-10 minutes'
        }), 202

    except Exception as e:
        current_app.logger.error(f"Error creating report generation: {e}")
        return jsonify({'error': 'Failed to create report generation job'}), 500

@exports_bp.route('/batch', methods=['POST'])
@jwt_required()
@rate_limit('api')
def create_batch_export():
    """Create batch export for multiple training runs."""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()

        model_run_ids = data.get('model_run_ids', [])
        if not model_run_ids:
            return jsonify({'error': 'No model runs specified'}), 400

        # Validate all model runs belong to user
        model_runs = ModelRun.query.filter(
            ModelRun.id.in_(model_run_ids),
            ModelRun.user_id == user_id
        ).all()

        if len(model_runs) != len(model_run_ids):
            return jsonify({'error': 'Some model runs not found or access denied'}), 404

        # Create batch export job
        export_job = ExportJob(
            user_id=user_id,
            job_type='batch_export',
            export_config={
                'model_run_ids': model_run_ids,
                'include_summary': data.get('include_summary', True),
                'include_individual_reports': data.get('include_individual_reports', True),
                'comparison_analysis': data.get('comparison_analysis', True),
                'format': data.get('format', 'zip')
            },
            status=ExportStatus.PENDING
        )
        db.session.add(export_job)
        db.session.commit()

        # Queue background job
        from ..tasks.export_tasks import generate_batch_export
        task = generate_batch_export.delay(export_job.id, model_run_ids, data)

        # Update job with task ID
        export_job.celery_task_id = task.id
        db.session.commit()

        return jsonify({
            'message': 'Batch export job created successfully',
            'job_id': export_job.id,
            'model_runs_count': len(model_run_ids),
            'estimated_time': '10-20 minutes'
        }), 202

    except Exception as e:
        current_app.logger.error(f"Error creating batch export: {e}")
        return jsonify({'error': 'Failed to create batch export job'}), 500

@exports_bp.route('/status/<uuid:job_id>', methods=['GET'])
@jwt_required()
@rate_limit('api')
def get_export_status(job_id):
    """Get status of an export job."""
    try:
        user_id = get_jwt_identity()

        export_job = ExportJob.query.filter_by(id=job_id, user_id=user_id).first()
        if not export_job:
            return jsonify({'error': 'Export job not found'}), 404

        response_data = {
            'job_id': str(export_job.id),
            'job_type': export_job.job_type,
            'status': export_job.status.value,
            'progress_percentage': export_job.progress_percentage,
            'created_at': export_job.created_at.isoformat(),
            'estimated_completion': None
        }

        if export_job.started_at:
            response_data['started_at'] = export_job.started_at.isoformat()

        if export_job.completed_at:
            response_data['completed_at'] = export_job.completed_at.isoformat()

        if export_job.error_message:
            response_data['error_message'] = export_job.error_message

        if export_job.status == ExportStatus.COMPLETED:
            response_data['download_url'] = f'/api/exports/download/{export_job.id}'
            response_data['file_size'] = export_job.file_size_bytes
            response_data['expires_at'] = export_job.expires_at.isoformat() if export_job.expires_at else None

        return jsonify(response_data)

    except Exception as e:
        current_app.logger.error(f"Error getting export status: {e}")
        return jsonify({'error': 'Failed to get export status'}), 500

@exports_bp.route('/download/<uuid:job_id>', methods=['GET'])
@jwt_required()
@rate_limit('api')
def download_export(job_id):
    """Download completed export file."""
    try:
        user_id = get_jwt_identity()

        export_job = ExportJob.query.filter_by(id=job_id, user_id=user_id).first()
        if not export_job:
            return jsonify({'error': 'Export job not found'}), 404

        if export_job.status != ExportStatus.COMPLETED:
            return jsonify({'error': 'Export not completed'}), 400

        if export_job.is_expired():
            return jsonify({'error': 'Export has expired'}), 410

        # Get file path from job
        if not export_job.file_paths:
            return jsonify({'error': 'Export file not found'}), 404

        file_path = export_job.file_paths[0]  # Use first file for single exports
        if not os.path.exists(file_path):
            return jsonify({'error': 'Export file not found on disk'}), 404

        # Determine file type and set appropriate headers
        filename = os.path.basename(file_path)
        file_extension = os.path.splitext(filename)[1].lower()

        if file_extension == '.pdf':
            mimetype = 'application/pdf'
        elif file_extension == '.zip':
            mimetype = 'application/zip'
        elif file_extension == '.json':
            mimetype = 'application/json'
        elif file_extension in ['.pkl', '.pickle']:
            mimetype = 'application/octet-stream'
        else:
            mimetype = 'application/octet-stream'

        # Log download
        security_monitor.log_security_event('export_downloaded', {
            'job_id': str(job_id),
            'filename': filename,
            'file_size': os.path.getsize(file_path)
        }, 'low')

        return send_file(
            file_path,
            as_attachment=True,
            download_name=filename,
            mimetype=mimetype
        )

    except Exception as e:
        current_app.logger.error(f"Error downloading export: {e}")
        return jsonify({'error': 'Failed to download export'}), 500

@exports_bp.route('/history', methods=['GET'])
@jwt_required()
@rate_limit('api')
def get_export_history():
    """Get user's export history."""
    try:
        user_id = get_jwt_identity()

        # Query parameters
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        job_type = request.args.get('job_type')
        status = request.args.get('status')

        query = ExportJob.query.filter_by(user_id=user_id)

        # Apply filters
        if job_type:
            query = query.filter(ExportJob.job_type == job_type)

        if status:
            try:
                status_enum = ExportStatus(status)
                query = query.filter(ExportJob.status == status_enum)
            except ValueError:
                pass

        # Order by creation date
        query = query.order_by(desc(ExportJob.created_at))

        # Paginate
        paginated_jobs = query.paginate(
            page=page, per_page=per_page, error_out=False
        )

        jobs_data = []
        for job in paginated_jobs.items:
            job_data = {
                'id': str(job.id),
                'job_type': job.job_type,
                'status': job.status.value,
                'progress_percentage': job.progress_percentage,
                'created_at': job.created_at.isoformat(),
                'file_size_bytes': job.file_size_bytes
            }

            if job.started_at:
                job_data['started_at'] = job.started_at.isoformat()

            if job.completed_at:
                job_data['completed_at'] = job.completed_at.isoformat()

            if job.status == ExportStatus.COMPLETED:
                job_data['download_url'] = f'/api/exports/download/{job.id}'
                job_data['expires_at'] = job.expires_at.isoformat() if job.expires_at else None

            if job.error_message:
                job_data['error_message'] = job.error_message

            jobs_data.append(job_data)

        return jsonify({
            'exports': jobs_data,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': paginated_jobs.total,
                'pages': paginated_jobs.pages,
                'has_next': paginated_jobs.has_next,
                'has_prev': paginated_jobs.has_prev
            }
        })

    except Exception as e:
        current_app.logger.error(f"Error getting export history: {e}")
        return jsonify({'error': 'Failed to get export history'}), 500

@exports_bp.route('/<uuid:job_id>', methods=['DELETE'])
@jwt_required()
@rate_limit('api')
def delete_export(job_id):
    """Delete an export job and its files."""
    try:
        user_id = get_jwt_identity()

        export_job = ExportJob.query.filter_by(id=job_id, user_id=user_id).first()
        if not export_job:
            return jsonify({'error': 'Export job not found'}), 404

        # Only allow deletion of completed or failed jobs
        if export_job.status not in [ExportStatus.COMPLETED, ExportStatus.FAILED]:
            return jsonify({'error': 'Cannot delete active export job'}), 400

        # Delete files
        if export_job.file_paths:
            for file_path in export_job.file_paths:
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                except Exception as e:
                    current_app.logger.warning(f"Failed to delete file {file_path}: {e}")

        # Delete database record
        db.session.delete(export_job)
        db.session.commit()

        # Log deletion
        security_monitor.log_security_event('export_deleted', {
            'job_id': str(job_id),
            'job_type': export_job.job_type
        }, 'low')

        return jsonify({'message': 'Export job deleted successfully'})

    except Exception as e:
        current_app.logger.error(f"Error deleting export: {e}")
        return jsonify({'error': 'Failed to delete export'}), 500