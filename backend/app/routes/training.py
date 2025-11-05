# backend/app/routes/training.py

from flask import Blueprint, request, jsonify, current_app, send_from_directory
from flask_jwt_extended import jwt_required, decode_token
from flask_socketio import join_room, leave_room, emit
from ..models import Task, ModelRun, User
# Use specific schemas
from ..schemas import model_run_schema, ModelRunSchema
from ..services.auth_helpers import get_user_from_token
from .. import db, socketio
import os
import werkzeug.utils
import uuid
import json # For loading analysis results

training_bp = Blueprint('training_bp', __name__)

# --- Helper ---
def get_run_owner(model_run_id):
    """Helper to safely get user ID from a model run."""
    run = ModelRun.query.get(model_run_id)
    if run:
        return str(run.user_id)
    return None

# --- Upload Route (Keep as is) ---
@training_bp.route('/<task_id>/upload', methods=['POST'])
@jwt_required()
def upload_data_and_create_run(task_id):
    # ... (user/task checks remain the same) ...
    user = get_user_from_token()
    task = Task.query.get(task_id)
    if not task or str(task.user_id) != str(user.id): return jsonify({"msg": "Task not found or unauthorized"}), 403
    if 'file' not in request.files: return jsonify({"msg": "No file part"}), 400
    file = request.files['file']
    if file.filename == '': return jsonify({"msg": "No selected file"}), 400
    model_id_str = request.form.get('model_id')
    if not model_id_str: return jsonify({"msg": "model_id is required"}), 400

    # --- START FIX [Issue #17] --- Sanitize filename ---
    original_filename = file.filename
    safe_filename = werkzeug.utils.secure_filename(original_filename)
    if not safe_filename: # secure_filename can return empty string for bad names
        return jsonify({"msg": "Invalid filename provided"}), 400
    # --- END FIX ---

    try:
        new_run = ModelRun(
            model_id_str=model_id_str, task_id=task.id, user_id=user.id,
            status='PENDING_UPLOAD'
        )
        db.session.add(new_run)
        db.session.commit() # Commit here to get new_run.id

        run_dir = os.path.join(
            current_app.config['USER_UPLOADS_DIR'], str(user.id), str(new_run.id)
        )
        os.makedirs(run_dir, exist_ok=True)

        # --- START FIX [Issue #17] --- Use safe filename ---
        original_data_path = os.path.join(run_dir, safe_filename)
        # --- END FIX ---

        file.save(original_data_path)

        new_run.original_data_path = original_data_path
        new_run.run_output_dir = run_dir
        new_run.status = 'PENDING_ANALYSIS'
        db.session.commit()

        return jsonify(model_run_schema.dump(new_run)), 201

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error in upload_data_and_create_run: {e}", exc_info=True)
        # Clean up directory if run creation failed mid-way? Optional.
        return jsonify({"msg": "Error uploading file", "error": str(e)}), 500
    
    
# --- Start Analysis Route ---
@training_bp.route('/run/<model_run_id>/analyze', methods=['POST'])
@jwt_required()
def start_analysis(model_run_id):
    """ Triggers the data analysis Celery task. """
    from tasks.analyze_data_task import analyze_data_task # Import locally

    user = get_user_from_token()
    run = ModelRun.query.get(model_run_id)

    if not run or str(run.user_id) != str(user.id):
         return jsonify({"msg": "Model run not found or unauthorized"}), 403

    # Check if analysis already done or in progress?
    allowed_start_statuses = ['PENDING_ANALYSIS', 'ANALYSIS_FAILED']
    if run.status not in allowed_start_statuses:
         return jsonify({"msg": f"Analysis cannot be started. Current status: {run.status}"}), 409 # 409 Conflict
    # --- END FIX [Issue #3] ---

    task = analyze_data_task.apply_async(args=[str(run.id)])

    run.celery_task_id = task.id
    # run.status = 'ANALYZING' # Status updated by task now
    db.session.commit() # Commit task ID assignment

    return jsonify({
        "msg": "Data analysis started",
        "celery_task_id": task.id,
        "run": model_run_schema.dump(run) # Return current state
    }), 202


# --- START FIX [Issue #1] ---
# --- NEW: Start Cleaning Route ---
@training_bp.route('/run/<model_run_id>/clean', methods=['POST'])
@jwt_required()
def start_cleaning(model_run_id):
    """ Triggers the data cleaning Celery task. """
    from tasks.clean_data_task import clean_data_task # Import locally

    user = get_user_from_token()
    run = ModelRun.query.get(model_run_id)

    if not run or str(run.user_id) != str(user.id):
         return jsonify({"msg": "Model run not found or unauthorized"}), 403

    # Ensure analysis was successful before cleaning
    # Allow retrying if previous cleaning failed
    allowed_start_statuses = ['SUCCESS', 'CLEANING_FAILED'] # SUCCESS from analysis
    if run.status not in allowed_start_statuses:
         return jsonify({"msg": f"Cleaning cannot be started. Prerequisite step not complete or run in invalid state. Status: {run.status}"}), 409
    # --- END FIX [Issue #3]
    cleaning_options = request.get_json() or {}
    if not cleaning_options:
        return jsonify({"msg": "Cleaning options are required in the request body"}), 400

    task = clean_data_task.apply_async(args=[str(run.id), cleaning_options])

    run.celery_task_id = task.id
    # run.status = 'CLEANING' # Task will update status
    db.session.commit() # Commit task ID assignment

    return jsonify({
        "msg": "Data cleaning started",
        "celery_task_id": task.id,
        "run": model_run_schema.dump(run) # Return current state
    }), 202
# --- END FIX [Issue #1] ---


# --- Start Training Route ---
# --- START FIX [Issue #1] ---
# Modified status check
@training_bp.route('/run/<model_run_id>/train', methods=['POST'])
@jwt_required()
def start_training(model_run_id):
    """ Triggers the model training Celery task. """
    from tasks.train_model_task import train_model_task # Import locally

    user = get_user_from_token()
    run = ModelRun.query.get(model_run_id)

    if not run or str(run.user_id) != str(user.id):
         return jsonify({"msg": "Model run not found or unauthorized"}), 403

    # Ensure cleaning was successful (or analysis if cleaning is skipped/not applicable)
    # Allow retrying if previous training failed
    allowed_start_statuses = ['SUCCESS', 'CLEANING_SUCCESS', 'FAILED']
    if run.status not in allowed_start_statuses:
         return jsonify({"msg": f"Training cannot be started. Prerequisite step not complete or run in invalid state. Status: {run.status}"}), 409
    # --- END FIX [Issue #3] --

    user_config = request.get_json() or {}

    task = train_model_task.apply_async(args=[str(run.id), user_config])

    run.celery_task_id = task.id
    run.status = 'STARTING' # Task will update to TRAINING etc.
    run.started_at = db.func.now()
    run.completed_at = None # Reset completion time
    run.final_metrics = None # Clear previous results
    run.educational_summary = None # Clear previous results
    db.session.commit()

    return jsonify({
        "msg": "Model training started",
        "celery_task_id": task.id,
        "run": model_run_schema.dump(run) # Return current state
    }), 202


# --- Get Run Details + Analysis ---
@training_bp.route('/run/<model_run_id>', methods=['GET'])
@jwt_required()
def get_run_details(model_run_id):
    """ Fetches ModelRun details and includes parsed analysis results if available. """
    user = get_user_from_token()
    run = ModelRun.query.get(model_run_id)

    if not run or str(run.user_id) != str(user.id):
         return jsonify({"msg": "Model run not found or unauthorized"}), 403

    # Use a schema that includes nested objects if desired, or manually construct
    run_data = model_run_schema.dump(run)

    # --- Load and Embed Analysis Results ---
    analysis_data = None
    # Option 1: Load from DB column (if saved by task)
    if run.analysis_results:
        analysis_data = run.analysis_results # Assumes it's already JSON/dict
    # Option 2: Load from file (fallback or if not saving to DB)
    elif run.run_output_dir:
        analysis_file_path = os.path.join(run.run_output_dir, 'analysis_results.json')
        if os.path.exists(analysis_file_path):
            try:
                with open(analysis_file_path, 'r') as f:
                    analysis_data = json.load(f)
            except Exception as e:
                current_app.logger.warning(f"Could not load analysis file for run {run.id}: {e}")

    run_data['analysis_results'] = analysis_data # Add to the response
    # --- End Load Analysis ---

    # --- START FIX [Issue #1] ---
    # --- Load and Embed Cleaning Report ---
    cleaning_report_data = None
    # Option 1: Load from DB
    if run.cleaning_report:
         cleaning_report_data = run.cleaning_report
    # Option 2: Load from file (fallback)
    elif run.run_output_dir:
         cleaning_report_file = os.path.join(run.run_output_dir, 'cleaning_report.json')
         if os.path.exists(cleaning_report_file):
              try:
                  with open(cleaning_report_file, 'r') as f:
                      cleaning_report_data = json.load(f)
              except Exception as e:
                  current_app.logger.warning(f"Could not load cleaning report file for run {run.id}: {e}")

    run_data['cleaning_report'] = cleaning_report_data
    # --- END FIX [Issue #1] ---


    return jsonify(run_data), 200

# --- Get Run Results ---
@training_bp.route('/run/<model_run_id>/results', methods=['GET'])
@jwt_required()
def get_run_results(model_run_id):
    """ Fetches final results for a completed ModelRun. """
    user = get_user_from_token()
    run = ModelRun.query.get(model_run_id)

    if not run or str(run.user_id) != str(user.id):
         return jsonify({"msg": "Model run not found or unauthorized"}), 403

    # --- List available files in the output directory ---
    files = []
    if run.run_output_dir and os.path.exists(run.run_output_dir):
         try:
              # List only files, ignore directories (like 'extracted_data')
              files = [f for f in os.listdir(run.run_output_dir)
                       if os.path.isfile(os.path.join(run.run_output_dir, f))]
         except Exception as e:
              current_app.logger.error(f"Could not list files for run {run.id}: {e}")

    # Structure the response
    results_payload = {
        "run": model_run_schema.dump(run), # Includes metrics/summary from DB columns
        "results": { # Keep structure similar to frontend mock
            "metrics": run.final_metrics or {},
            "summary": run.educational_summary or {},
            "files": files
        }
    }

    return jsonify(results_payload), 200


# --- Serve Static Files from Run Directory ---
@training_bp.route('/run/<model_run_id>/file/<path:filename>', methods=['GET'])
@jwt_required()
def get_run_file(model_run_id, filename):
    """ Securely serves files from a run's output directory. """
    user = get_user_from_token()
    run = ModelRun.query.get(model_run_id)

    if not run or str(run.user_id) != str(user.id):
         return jsonify({"msg": "Model run not found or unauthorized"}), 403

    if not run.run_output_dir:
        return jsonify({"msg": "Output directory not configured for this run"}), 404

    # Basic security: prevent path traversal
    if '..' in filename or filename.startswith('/'):
        return jsonify({"msg": "Invalid filename"}), 400

    directory = run.run_output_dir
    file_path = os.path.join(directory, filename)

    # Check if file exists within the directory
    if not os.path.exists(file_path) or not os.path.isfile(file_path):
         # Check if it exists without the directory prefix (e.g. if filename already has it)
         if os.path.exists(filename) and os.path.isfile(filename) and filename.startswith(directory):
             # Allow if filename is an absolute path starting with the allowed directory
             pass
         else:
             return jsonify({"msg": "File not found"}), 404


    # Use send_from_directory for safer serving
    # We send the directory and the filename separately
    return send_from_directory(directory, filename)


# --- Enhanced WebSocket Handlers ---
@socketio.on('join_room')
def handle_join_room(data):
    token = data.get('token')
    model_run_id = data.get('model_run_id')
    client_sid = request.sid

    if not token or not model_run_id:
        emit('room_error', {
            'model_run_id': model_run_id,
            'message': 'Token and model_run_id are required'
        }, room=client_sid)
        return

    try:
        # Decode token with error handling
        try:
            user_identity = decode_token(token)['sub']
        except Exception as token_error:
            emit('room_error', {
                'model_run_id': model_run_id,
                'message': 'Invalid or expired token'
            }, room=client_sid)
            return

        owner_id = get_run_owner(model_run_id)
        if not owner_id:
            emit('room_error', {
                'model_run_id': model_run_id,
                'message': 'Model run not found'
            }, room=client_sid)
            return

        if str(user_identity) == owner_id:
            join_room(str(model_run_id))  # Room must be string
            current_app.logger.info(f"User {user_identity} joined room {model_run_id}")

            # Emit success confirmation
            emit('room_joined', {
                'model_run_id': model_run_id,
                'message': f'Successfully joined room {model_run_id}'
            }, room=client_sid)
        else:
            current_app.logger.warning(f"Unauthorized attempt: User {user_identity} tried joining room {model_run_id}")
            emit('room_error', {
                'model_run_id': model_run_id,
                'message': 'Unauthorized to join this room'
            }, room=client_sid)

    except Exception as e:
        current_app.logger.error(f"Error joining room {model_run_id}: {e}")
        emit('room_error', {
            'model_run_id': model_run_id,
            'message': 'Server error during join process'
        }, room=client_sid)


@socketio.on('leave_room')
def handle_leave_room(data):
    model_run_id = data.get('model_run_id')
    if model_run_id:
        leave_room(str(model_run_id))
        current_app.logger.info(f"User {request.sid} left room {model_run_id}")
        # Emit confirmation *to the specific room* (maybe not necessary on leave)
        # socketio.emit('status', {'msg': f'User left room {model_run_id}'}, room=str(model_run_id))


@socketio.on('connect')
def handle_connect():
    current_app.logger.info(f"Client connected: {request.sid}")

@socketio.on('disconnect')
def handle_disconnect():
    # Rooms are left automatically on disconnect
    current_app.logger.info(f"Client disconnected: {request.sid}")