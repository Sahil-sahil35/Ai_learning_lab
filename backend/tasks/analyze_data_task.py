# backend/tasks/analyze_data_task.py

from celery_worker import celery
from .base_task import JobReportingTask # Imports stream_output implicitly
from app.models_pkg import ModelRun
from app import db
import subprocess
import os
import sys
import json

@celery.task(bind=True, base=JobReportingTask)
def analyze_data_task(self, model_run_id):
    # --- START: Fetch run or fail early ---
    try:
        run = self._get_run(model_run_id)
    except ValueError as e:
        # self.flask_app.logger.error(f"Analyze task failed: {e}")
        return {"status": "FAILED", "error": str(e)}
    # --- END: Fetch run ---

    self.report_log(model_run_id, f"Starting data analysis for model: {run.model_id_str}...")
    self.update_status(model_run_id, "ANALYZING")
    process = None

    try:
        # --- 1. Setup Paths ---
        model_dir = os.path.join(self.flask_app.config['MODELS_DIR'], run.model_id_str)
        # --- Get script name from config ---
        config_path = os.path.join(model_dir, 'config.json')
        if not os.path.exists(config_path): raise FileNotFoundError(f"Model config.json not found: {config_path}")
        try:
             with open(config_path, 'r') as f:
                 model_meta = json.load(f)
                 analysis_script_name = model_meta.get('analysis_script', 'analyze.py') # Default
        except Exception as config_err:
             raise ValueError(f"Could not load/parse model config.json: {config_err}")

        analysis_script_path = os.path.join(model_dir, analysis_script_name)
        if not os.path.exists(analysis_script_path):
            raise FileNotFoundError(f"Analysis script '{analysis_script_name}' not found: {analysis_script_path}")
        # --- End Get script name ---

        if not run.original_data_path:
             raise FileNotFoundError(f"Original data path not set for run {model_run_id}")
        if not run.run_output_dir:
             raise ValueError(f"Output directory not set for run {model_run_id}")

        os.makedirs(run.run_output_dir, exist_ok=True)

        # --- 2. Construct Command ---
        command = [
            sys.executable,
            analysis_script_path,
            '--data', run.original_data_path,
            '--output-dir', run.run_output_dir,
            '--run-id', str(model_run_id) # Pass run_id if script needs it
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

        # Wait for the process AFTER streaming
        return_code = process.wait()

        # --- 4. Process Results ---
        if return_code == 0:
            self.report_log(model_run_id, "Analysis script finished successfully. Processing results file...")

            # --- Read, Emit, and Save Results ---
            analysis_file_path = os.path.join(run.run_output_dir, 'analysis_results.json') # Standard filename

            if os.path.exists(analysis_file_path):
                try:
                    with open(analysis_file_path, 'r') as f:
                        analysis_data = json.load(f)

                    # Emit the full result object via WebSocket log channel
                    self.report_json_log(model_run_id, {'type': 'analysis_result', 'data': analysis_data})
                    self.report_log(model_run_id, "Emitted full analysis results via WebSocket.")

                    # --- Save full analysis to DB ---
                    try:
                        # Re-fetch run just before update
                        run_to_update = db.session.get(ModelRun, model_run_id)
                        if not run_to_update: raise ValueError("ModelRun disappeared during task.")

                        run_to_update.analysis_results = analysis_data
                        # completed_at handled by update_status

                        self.update_status(model_run_id, "SUCCESS") # Use generic SUCCESS after analysis
                        self.report_log(model_run_id, "Analysis complete. Results saved to database.")
                        return {"status": "SUCCESS"}

                    except Exception as db_err:
                         db.session.rollback()
                         self.report_log(model_run_id, f"Database error saving analysis results: {db_err}", "ERROR")
                         try: self.update_status(model_run_id, "ANALYSIS_FAILED")
                         except: pass
                         raise Exception(f"Database error saving results: {db_err}")

                except Exception as e:
                    self.report_log(model_run_id, f"Failed to read or process analysis results file: {e}", "ERROR")
                    raise Exception(f"Result processing error: {e}") # Raise to trigger task failure
            else:
                raise FileNotFoundError("Analysis results file ('analysis_results.json') not found.")

        else: # process failed
             # Errors were streamed live
            raise Exception(f"Analysis script failed with exit code {return_code}. Check logs.")

    except Exception as e:
        self.flask_app.logger.error(f"Analysis task error for run {model_run_id}: {e}", exc_info=True)
        error_message = f"Analysis task failed: {str(e)}"
        self.report_log(model_run_id, error_message, "ERROR")

        # Send a structured error message to the frontend
        self.report_json_log(model_run_id, {
            'type': 'error',
            'source': 'analysis_task',
            'message': error_message
        })

        try:
             self.update_status(model_run_id, "ANALYSIS_FAILED")
        except Exception as status_err:
            self.flask_app.logger.error(f"Failed to update status to ANALYSIS_FAILED for run {model_run_id}: {status_err}")

        return {"status": "ANALYSIS_FAILED", "error": error_message}

    finally:
        # Cleanup subprocess
        if process and process.poll() is None:
            self.report_log(model_run_id, "Terminating analysis subprocess.", "WARNING")
            try: process.terminate(); process.wait(timeout=2)
            except: process.kill()