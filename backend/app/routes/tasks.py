# backend/app/routes/tasks.py
from flask import Blueprint, request, jsonify, current_app # Added current_app
from flask_jwt_extended import jwt_required
from ..models import Task, User, ModelRun # Added ModelRun
from ..schemas import task_schema, tasks_schema
from ..services.auth_helpers import get_user_from_token
from .. import db
import uuid
# --- START FIX [Issue #2] ---
import os
import shutil # For deleting directories
# --- END FIX [Issue #2] ---

tasks_bp = Blueprint('tasks_bp', __name__)

# ... (keep create_task, get_tasks, get_task routes as they are) ...
@tasks_bp.route('/', methods=['POST'])
@jwt_required()
def create_task():
    """ Creates a new task for the logged-in user. """
    user = get_user_from_token()
    if not user: return jsonify({"msg": "User not found"}), 404
    data = request.get_json()
    if not data or not data.get('name'): return jsonify({"msg": "Task name is required"}), 400
    try:
        new_task = Task(name=data['name'], description=data.get('description'), owner=user)
        db.session.add(new_task)
        db.session.commit()
        return jsonify(task_schema.dump(new_task)), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"msg": "Could not create task", "error": str(e)}), 500

@tasks_bp.route('/', methods=['GET'])
@jwt_required()
def get_tasks():
    """ Gets all tasks (and their nested model runs) for the logged-in user. """
    user = get_user_from_token()
    if not user: return jsonify({"msg": "User not found"}), 404
    tasks = Task.query.filter_by(user_id=user.id).order_by(Task.created_at.desc()).all()
    return jsonify(tasks_schema.dump(tasks)), 200

@tasks_bp.route('/<task_id>', methods=['GET'])
@jwt_required()
def get_task(task_id):
    """ Gets a single task by its ID. Ensures the task belongs to the logged-in user. """
    user = get_user_from_token()
    task = Task.query.get(task_id)
    if not task: return jsonify({"msg": "Task not found"}), 404
    if str(task.user_id) != str(user.id): return jsonify({"msg": "Unauthorized"}), 403
    return jsonify(task_schema.dump(task)), 200
# --- END keep routes ---

@tasks_bp.route('/<task_id>', methods=['DELETE'])
@jwt_required()
def delete_task(task_id):
    """
    Deletes a task by its ID and associated files.
    Ensures the task belongs to the logged-in user.
    (Note: This will cascade and delete all associated model runs from DB)
    """
    user = get_user_from_token()
    task = Task.query.get(task_id)

    if not task:
        return jsonify({"msg": "Task not found"}), 404

    if str(task.user_id) != str(user.id):
        return jsonify({"msg": "Unauthorized"}), 403

    # --- START FIX [Issue #2] ---
    # Find associated run directories BEFORE deleting the task from DB
    runs_to_delete = ModelRun.query.filter_by(task_id=task.id).all()
    dirs_to_delete = [run.run_output_dir for run in runs_to_delete if run.run_output_dir and os.path.exists(run.run_output_dir)]
    # Note: run_output_dir usually contains the original data file as well.
    # If original_data_path could be outside run_output_dir, add it separately:
    # dirs_to_delete.extend([run.original_data_path for run in runs_to_delete if ...])
    # For safety, ensure the path is within the user's base upload directory
    user_base_dir = os.path.join(current_app.config['USER_UPLOADS_DIR'], str(user.id))
    valid_dirs_to_delete = [d for d in dirs_to_delete if d.startswith(user_base_dir)]
    # --- END FIX [Issue #2] ---

    try:
        # Delete task from DB (cascades to ModelRun entries)
        db.session.delete(task)
        db.session.commit()

        # --- START FIX [Issue #2] ---
        # Now delete the directories from the filesystem
        deleted_dirs_count = 0
        errors_deleting_dirs = []
        for dir_path in valid_dirs_to_delete:
            try:
                # Check again if it exists before attempting deletion
                if os.path.exists(dir_path):
                     shutil.rmtree(dir_path)
                     current_app.logger.info(f"Deleted directory: {dir_path}")
                     deleted_dirs_count += 1
            except Exception as e:
                current_app.logger.error(f"Error deleting directory {dir_path}: {e}")
                errors_deleting_dirs.append(dir_path)

        response_msg = "Task deleted successfully."
        if errors_deleting_dirs:
            response_msg += f" Warning: Failed to delete directories: {', '.join(errors_deleting_dirs)}"
        elif deleted_dirs_count > 0:
             response_msg += f" Associated files ({deleted_dirs_count} directories) also deleted."

        return jsonify({"msg": response_msg}), 200
        # --- END FIX [Issue #2] ---

    except Exception as e:
        db.session.rollback()
        # --- START FIX [Issue #2] ---
        # Log the DB error, but don't delete files if DB op failed
        current_app.logger.error(f"Error deleting task {task_id} from DB: {e}")
        return jsonify({"msg": "Error deleting task from database", "error": str(e)}), 500
        # --- END FIX [Issue #2] ---