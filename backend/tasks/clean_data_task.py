# backend/tasks/clean_data_task.py

from celery_worker import celery
from .base_task import JobReportingTask
from app.models_pkg import ModelRun
from app import db
import subprocess
import os
import sys
import json

@celery.task(bind=True, base=JobReportingTask)
def clean_data_task(self, model_run_id, cleaning_options):
    # --- START: Fetch run or fail early ---
    try:
        run = self._get_run(model_run_id)
    except ValueError as e:
        # self.flask_app.logger.error(f"Clean task failed: {e}")
        return {"status": "FAILED", "error": str(e)}
    # --- END: Fetch run ---

    self.report_log(model_run_id, f"Starting data cleaning for model: {run.model_id_str}...")
    self.update_status(model_run_id, "CLEANING")
    process = None

    try:
        # --- 1. Setup Paths ---
        model_dir = os.path.join(self.flask_app.config['MODELS_DIR'], run.model_id_str)
        # --- Get script name from config (optional, default to clean.py) ---
        config_path = os.path.join(model_dir, 'config.json')
        cleaning_script_name = 'clean.py' # Default
        if os.path.exists(config_path):
             try:
                 with open(config_path, 'r') as f:
                     model_meta = json.load(f)
                     # Check if a specific cleaning script is defined
                     cleaning_script_name = model_meta.get('cleaning_script', cleaning_script_name)
             except Exception as config_err:
                 self.report_log(model_run_id, f"Warning: Could not read model config for cleaning script name: {config_err}", "WARNING")

        cleaning_script_path = os.path.join(model_dir, cleaning_script_name)
        # --- End Get script name ---

        # --- Check if cleaning script exists ---
        if not os.path.exists(cleaning_script_path):
            # If no script exists, maybe treat as success (no cleaning needed)?
            self.report_log(model_run_id, f"Cleaning script '{cleaning_script_name}' not found. Skipping cleaning step.", "WARNING")
            run.cleaned_data_path = run.original_data_path # Use original data
            run.cleaning_report = {"summary": "Cleaning skipped: Script not found."}
            self.update_status(model_run_id, "CLEANING_SUCCESS") # Mark as success
            self.report_json_log(model_run_id, {'type': 'cleaning_report', 'data': run.cleaning_report})
            return {"status": "CLEANING_SUCCESS", "message": "Skipped: Cleaning script not found."}
        # --- End Check ---

        if not run.original_data_path:
             raise FileNotFoundError(f"Original data path not set for run {model_run_id}")
        if not run.run_output_dir:
             raise ValueError(f"Output directory not set for run {model_run_id}")

        os.makedirs(run.run_output_dir, exist_ok=True)

        # Define cleaned data path consistently
        base, ext = os.path.splitext(os.path.basename(run.original_data_path))
        cleaned_file_name = f"{base}_cleaned{ext}" # Maintain original extension
        cleaned_data_path = os.path.join(run.run_output_dir, cleaned_file_name)

        # --- 2. Construct Command ---
        command = [
            sys.executable,
            cleaning_script_path,
            '--data', run.original_data_path,
            '--output-file', cleaned_data_path, # Target output file
            '--options', json.dumps(cleaning_options or {}), # Pass options safely
            '--output-dir', run.run_output_dir, # For report file
            '--run-id', str(model_run_id) # Optional
        ]
        self.report_log(model_run_id, f"Executing command: {' '.join(command)}", "DEBUG")

        # --- 3. Execute Subprocess ---
        process_env = os.environ.copy()
        process_env['PYTHONUNBUFFERED'] = '1'

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, # Capture stderr
            text=True,
            universal_newlines=True,
            env=process_env,
            bufsize=1
        )

        # --- Use the NEW streaming function from base_task ---
        self.stream_output(process, model_run_id)

        # Wait AFTER streaming
        return_code = process.wait()

        # --- 4. Process Results ---
        if return_code == 0:
            self.report_log(model_run_id, "Cleaning script finished successfully.")

            # --- Verify output file and load report ---
            cleaning_report_path = os.path.join(run.run_output_dir, 'cleaning_report.json')
            report_data = None

            if os.path.exists(cleaned_data_path):
                # Load report (optional, but expected)
                if os.path.exists(cleaning_report_path):
                     try:
                         with open(cleaning_report_path, 'r') as f:
                             report_data = json.load(f)
                         self.report_log(model_run_id, "Loaded cleaning_report.json")
                         # Emit the report via WebSocket log channel
                         self.report_json_log(model_run_id, {'type': 'cleaning_report', 'data': report_data})
                     except Exception as e:
                          self.report_log(model_run_id, f"Warning: Could not load/parse cleaning_report.json: {e}", "WARNING")
                else:
                     self.report_log(model_run_id, "cleaning_report.json not found.", "WARNING")

                # --- Update Database ---
                try:
                    # Re-fetch run just before update
                    run_to_update = db.session.get(ModelRun, model_run_id)
                    if not run_to_update: raise ValueError("ModelRun disappeared.")

                    run_to_update.cleaned_data_path = cleaned_data_path
                    run_to_update.cleaning_report = report_data # Store report if available
                    # completed_at handled by update_status

                    self.update_status(model_run_id, "CLEANING_SUCCESS") # Commit happens here
                    self.report_log(model_run_id, "Cleaning complete. Cleaned data path and report saved.")
                    return {"status": "CLEANING_SUCCESS"}

                except Exception as db_err:
                     db.session.rollback()
                     self.report_log(model_run_id, f"Database error saving cleaning results: {db_err}", "ERROR")
                     try: self.update_status(model_run_id, "CLEANING_FAILED")
                     except: pass
                     raise Exception(f"Database error saving cleaning results: {db_err}")
            else:
                # Script succeeded (exit 0) but didn't create the output file
                raise FileNotFoundError(f"Cleaning script finished but output file not found: {cleaned_data_path}")

        else: # process failed
            # Errors were streamed live
            raise Exception(f"Cleaning script failed with exit code {return_code}. Check logs.")

    except Exception as e:
        self.flask_app.logger.error(f"Cleaning task error for run {model_run_id}: {e}", exc_info=True)
        error_message = f"Cleaning task failed: {str(e)}"
        self.report_log(model_run_id, error_message, "ERROR")

        try:
             self.update_status(model_run_id, "CLEANING_FAILED")
        except Exception as status_err:
            self.flask_app.logger.error(f"Failed to update status to CLEANING_FAILED for run {model_run_id}: {status_err}")

        return {"status": "CLEANING_FAILED", "error": error_message}

    finally:
        # Cleanup subprocess
        if process and process.poll() is None:
            self.report_log(model_run_id, "Terminating cleaning subprocess.", "WARNING")
            try: process.terminate(); process.wait(timeout=2)
            except: process.kill()