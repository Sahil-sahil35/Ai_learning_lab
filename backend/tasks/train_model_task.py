# backend/tasks/train_model_task.py

from celery_worker import celery
from .base_task import JobReportingTask # Imports stream_output implicitly now
from app.models_pkg import ModelRun
from app import db
import subprocess
import os
import sys
import json
import time

@celery.task(bind=True, base=JobReportingTask)
def train_model_task(self, model_run_id, user_config):
    # --- START: Fetch run or fail early ---
    try:
        run = self._get_run(model_run_id)
    except ValueError as e:
        # Log error via task logger if possible, though flask_app might not be ready
        # self.flask_app.logger.error(f"Train task failed: {e}")
        # Cannot use report_log as run_id might be invalid for socket room
        return {"status": "FAILED", "error": str(e)}
    # --- END: Fetch run ---

    self.report_log(model_run_id, f"Received training request for model: {run.model_id_str}")
    self.update_status(model_run_id, "STARTING") # Indicate startup phase
    start_time = time.time()
    process = None

    try:
        # --- 1. Setup Paths and Config ---
        model_dir = os.path.join(self.flask_app.config['MODELS_DIR'], run.model_id_str)
        # --- Use model config for script names ---
        config_path = os.path.join(model_dir, 'config.json')
        if not os.path.exists(config_path): raise FileNotFoundError(f"Model config.json not found: {config_path}")
        try:
             with open(config_path, 'r') as f:
                 model_meta = json.load(f)
                 training_script_name = model_meta.get('training_script', 'train.py') # Default to train.py
                 model_parameters_config = model_meta.get('parameters', [])
        except Exception as config_err:
             raise ValueError(f"Could not load or parse model config.json: {config_err}")

        training_script_path = os.path.join(model_dir, training_script_name)
        if not os.path.exists(training_script_path): raise FileNotFoundError(f"Training script '{training_script_name}' not found: {training_script_path}")
        # --- End Use model config ---

        data_path = run.cleaned_data_path or run.original_data_path
        if not data_path: raise FileNotFoundError(f"No data path (original or cleaned) set for run {model_run_id}")
        if not run.run_output_dir: raise ValueError(f"Output directory not set for run {model_run_id}")

        # Ensure output directory exists
        os.makedirs(run.run_output_dir, exist_ok=True)

        # --- 2. Construct Command (Using Refined Validation Logic from Previous Step) ---
        command = [
            sys.executable, # Use the same Python interpreter Celery runs with
            training_script_path,
            '--data', data_path,
            '--output-dir', run.run_output_dir,
            '--run-id', str(model_run_id) # Pass run_id for context if needed
        ]

        # --- Parameter Validation Logic ---
        param_map = {p['name']: p for p in model_parameters_config}
        for key, value in user_config.items():
            param_config = param_map.get(key)
            if not param_config:
                self.report_log(model_run_id, f"Skipping unknown parameter from user config: {key}", "WARNING")
                continue

            is_allowed_null_or_empty = param_config.get('default') is None or param_config.get('allow_empty', False)
            param_type = param_config.get('type')
            validated_value = value
            validated_value_str = None

            if validated_value is None:
                if not is_allowed_null_or_empty:
                    self.report_log(model_run_id, f"Skipping None parameter '{key}' (not allowed).", "WARNING")
                    continue
                if param_type == 'boolean_checkbox': validated_value = False
            elif validated_value == '':
                 if not is_allowed_null_or_empty and param_type != 'text':
                     self.report_log(model_run_id, f"Skipping empty non-text parameter '{key}' (not allowed).", "WARNING")
                     continue

            try:
                if validated_value is not None:
                    if param_type == 'number':
                        f_val = float(validated_value)
                        if param_config.get('min') is not None and f_val < param_config['min']: f_val = param_config['min']
                        if param_config.get('max') is not None and f_val > param_config['max']: f_val = param_config['max']
                        validated_value_str = str(f_val)
                    elif param_type == 'select':
                        str_value = str(validated_value)
                        options = [str(o) for o in param_config.get('options', [])]
                        if str_value not in options:
                             raise ValueError(f"Invalid option '{str_value}'. Allowed: {options}")
                        validated_value_str = str_value
                    elif param_type == 'boolean_checkbox':
                         validated_value = bool(validated_value)
                         validated_value_str = None
                    elif param_type == 'target_column':
                         if not isinstance(validated_value, str) or not validated_value:
                             raise ValueError(f"Target column must be a non-empty string.")
                         validated_value_str = str(validated_value)
                    else:
                         validated_value_str = str(validated_value)
            except (ValueError, TypeError) as val_err:
                 self.report_log(model_run_id, f"Invalid value '{value}' for parameter '{key}': {val_err}", "ERROR")
                 raise ValueError(f"Invalid value for parameter '{key}': {val_err}")

            if param_type == 'boolean_checkbox':
                 if validated_value: command.append(f'--{key}')
            elif validated_value_str is not None:
                 command.append(f'--{key}')
                 command.append(validated_value_str)
        # --- End Parameter Validation ---

        self.report_log(model_run_id, f"Final command: {' '.join(command)}", "DEBUG")

        # --- 3. Execute Subprocess ---
        process_env = os.environ.copy()
        process_env['PYTHONUNBUFFERED'] = '1'

        self.update_status(model_run_id, "TRAINING") # Update status right before Popen

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            universal_newlines=True,
            env=process_env,
            bufsize=1
        )

        # --- Use the NEW streaming function from base_task ---
        self.stream_output(process, model_run_id)

        # Wait for the process to complete AFTER streaming finishes
        return_code = process.wait()

        # --- 4. Process Results ---
        if return_code != 0:
            # Error messages were streamed live. Raise generic exception.
            raise Exception(f"Training script failed with exit code {return_code}. Check logs for details.")
        else:
            self.report_log(model_run_id, "Training script finished successfully. Validating output files...")

            # --- Validate and Save Output ---
            metrics_path = os.path.join(run.run_output_dir, 'final_metrics.json')
            summary_path = os.path.join(run.run_output_dir, 'educational_summary.json')
            # history_path = os.path.join(run.run_output_dir, 'training_history.json') # Optional

            final_metrics_data = None
            summary_data = None
            files_missing = []

            try: # Load Metrics
                with open(metrics_path, 'r') as f:
                    final_metrics_data = json.load(f)
                self.report_log(model_run_id, "Loaded final_metrics.json")
            except FileNotFoundError: files_missing.append('final_metrics.json')
            except json.JSONDecodeError: raise ValueError("Could not parse final_metrics.json")
            except Exception as e: raise ValueError(f"Error reading final_metrics.json: {e}")

            try: # Load Summary (Optional)
                with open(summary_path, 'r') as f:
                    summary_data = json.load(f)
                self.report_log(model_run_id, "Loaded educational_summary.json")
            except FileNotFoundError: self.report_log(model_run_id, "educational_summary.json not found.", "WARNING")
            except json.JSONDecodeError: self.report_log(model_run_id, "Could not parse educational_summary.json", "WARNING")
            except Exception as e: self.report_log(model_run_id, f"Error reading educational_summary.json: {e}", "WARNING")

            if 'final_metrics.json' in files_missing:
                raise FileNotFoundError(f"Required output files missing: {', '.join(files_missing)}")

            # --- Update Database ---
            try:
                # Re-fetch run just before update is safer with long tasks
                run_to_update = db.session.get(ModelRun, model_run_id)
                if not run_to_update: raise ValueError("ModelRun disappeared during task execution.")

                run_to_update.final_metrics = final_metrics_data
                run_to_update.educational_summary = summary_data
                # completed_at and status handled by update_status

                self.update_status(model_run_id, "SUCCESS") # Commit happens here
                self.report_log(model_run_id, "Training complete. Final results saved to database.")

                # Emit final results summary via WebSocket
                self.report_json_log(model_run_id, {
                    "type": "final_result_summary",
                    "metrics": final_metrics_data,
                    "summary": summary_data
                 })

                return {"status": "SUCCESS"}

            except Exception as db_err:
                 db.session.rollback()
                 self.report_log(model_run_id, f"Database error saving final results: {db_err}", "ERROR")
                 try: self.update_status(model_run_id, "FAILED")
                 except: pass
                 raise Exception(f"Database error saving results: {db_err}")


    except Exception as e:
        self.flask_app.logger.error(f"Training task error for run {model_run_id}: {e}", exc_info=True)
        error_message = f"Training task failed: {str(e)}"
        # Log via WebSocket only if it hasn't been logged during streaming already
        # (Hard to guarantee, so log anyway, frontend can deduplicate if needed)
        self.report_log(model_run_id, error_message, "ERROR")

        try:
             # Ensure status is updated even on unexpected exceptions
             self.update_status(model_run_id, "FAILED")
        except Exception as status_err:
             self.flask_app.logger.error(f"Failed to update status to FAILED after error for run {model_run_id}: {status_err}")

        # Task returns failure status to Celery
        # Use Celery's mechanism to indicate failure by re-raising or returning error dict
        return {"status": "FAILED", "error": error_message}

    finally:
        # Cleanup: Ensure subprocess is terminated if task fails/is revoked mid-execution
        if process and process.poll() is None:
            self.report_log(model_run_id, "Terminating subprocess due to task exit.", "WARNING")
            try:
                process.terminate()
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                self.report_log(model_run_id, "Force killed subprocess.", "WARNING")
            except Exception as term_err:
                self.report_log(model_run_id, f"Error during subprocess termination: {term_err}", "ERROR")