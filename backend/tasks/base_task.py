# backend/tasks/base_task.py

from celery_worker import celery
from app import db
from app.models import ModelRun
import datetime
from flask_socketio import SocketIO
import subprocess # Added
import threading # Added
import queue # Added
import json # Added
import sys # Added

# SocketIO client to emit messages *from* the worker via Redis
external_socketio = SocketIO(message_queue='redis://broker:6379/0')

# --- NEW: Helper function for concurrent stream reading ---
def stream_subprocess_output(process, model_run_id, report_func, report_json_func, logger):
    """
    Reads stdout and stderr concurrently using threads and reports logs.

    Args:
        process: The subprocess.Popen object.
        model_run_id: The ID of the model run for reporting.
        report_func: The report_log method from the Celery task.
        report_json_func: The report_json_log method from the Celery task.
        logger: The Flask app logger instance.
    """
    output_queue = queue.Queue()
    stream_names = {'stdout', 'stderr'} # Keep track of active streams

    def reader_thread(stream, stream_name):
        """Reads lines from a stream and puts them into the queue."""
        if stream is None: # Handle case where a stream wasn't piped
            logger.warning(f"Stream '{stream_name}' is None for run {model_run_id}.")
            output_queue.put((stream_name, None)) # Signal immediate finish for this stream
            return
        try:
            # Use iter to read lines efficiently without blocking indefinitely
            for line in iter(stream.readline, ''):
                output_queue.put((stream_name, line))
        except Exception as e:
            # Log errors during stream reading itself
            logger.error(f"Error reading {stream_name} for run {model_run_id}: {e}", exc_info=True)
        finally:
            # Signal that this stream has finished
            output_queue.put((stream_name, None))
            try:
                stream.close() # Ensure the stream is closed
            except Exception as close_err:
                 logger.warning(f"Error closing {stream_name} for run {model_run_id}: {close_err}")

    # Create and start threads for stdout and stderr
    stdout_thread = threading.Thread(target=reader_thread, args=(process.stdout, 'stdout'))
    stderr_thread = threading.Thread(target=reader_thread, args=(process.stderr, 'stderr'))

    stdout_thread.start()
    stderr_thread.start()

    active_streams_count = 2
    while active_streams_count > 0:
        try:
            # Get output from the queue, wait up to 1 second
            stream_name, line = output_queue.get(timeout=1.0)

            if line is None:  # Sentinel value indicating end of a stream
                active_streams_count -= 1
                logger.debug(f"Stream '{stream_name}' finished for run {model_run_id}. Active: {active_streams_count}")
                continue

            line = line.strip()
            if not line: # Skip empty lines
                continue

            # Determine log level: ERROR for stderr, INFO for stdout by default
            log_level = "ERROR" if stream_name == 'stderr' else "INFO"

            # Attempt to parse as JSON (common for stdout, possible for stderr)
            if line.startswith('{') and line.endswith('}'):
                try:
                    log_data = json.loads(line)
                    # Let report_json_log handle the specific event type
                    report_json_func(model_run_id, log_data)
                except json.JSONDecodeError:
                    # If JSON parsing fails, report as plain text with original level
                    report_func(model_run_id, f"[{stream_name}] {line}", log_level)
            else:
                # Report plain text line with original level
                report_func(model_run_id, f"[{stream_name}] {line}", log_level)

        except queue.Empty:
            # Timeout occurred. Check if the process has ended AND if we're still expecting stream signals
            process_poll = process.poll()
            if process_poll is not None and active_streams_count == 0:
                 logger.debug(f"Process ended (rc={process_poll}) and streams closed for run {model_run_id}. Exiting stream loop.")
                 break # Process finished and both streams signaled done
            elif process_poll is not None:
                # Process ended, but streams might still be sending data, keep reading queue briefly
                logger.debug(f"Process ended (rc={process_poll}), but waiting for streams ({active_streams_count} active) for run {model_run_id}.")
            # Otherwise, the process might still be running or streams closing, continue loop
            pass
        except Exception as e:
            logger.error(f"Error processing output queue for run {model_run_id}: {e}", exc_info=True)
            # Optionally report this error via report_func
            report_func(model_run_id, f"[STREAMING_ERROR] {e}", "ERROR")
            # Decide if you want to break the loop on queue processing errors

    # Wait for threads to fully complete (give them a reasonable timeout)
    try:
        stdout_thread.join(timeout=5.0)
        stderr_thread.join(timeout=5.0)
        if stdout_thread.is_alive() or stderr_thread.is_alive():
            logger.warning(f"Reader threads did not exit cleanly for run {model_run_id}")
    except Exception as join_err:
        logger.error(f"Error joining reader threads for run {model_run_id}: {join_err}")

    logger.info(f"Finished streaming subprocess output for run {model_run_id}")

# --- End NEW Helper Function ---


class JobReportingTask(celery.Task):
    abstract = True

    @property
    def flask_app(self):
        # Keep existing flask_app property
        if hasattr(super(), 'flask_app'):
            return super().flask_app
        else:
             # Ensure this error is descriptive
             raise RuntimeError("Flask app context not available in Celery task. Ensure ContextTask is correctly set.")

    def _get_run(self, model_run_id):
        # Keep existing _get_run method (with ValueError raise)
        run = db.session.get(ModelRun, model_run_id)
        if run is None:
            # Log the error before raising, helps diagnose celery issues
            self.flask_app.logger.error(f"ModelRun with ID {model_run_id} not found in database during _get_run.")
            raise ValueError(f"ModelRun with ID {model_run_id} not found in database.")
        return run

    def _emit(self, model_run_id, event, payload):
        # Keep existing _emit method
        try:
            # Ensure room is a string
            room_id = str(model_run_id)
            external_socketio.emit(event, payload, room=room_id)
            # Debug log - remove in production if too verbose
            # self.flask_app.logger.debug(f"Emitted '{event}' to room '{room_id}': {payload}")
        except Exception as e:
            self.flask_app.logger.error(f"External SocketIO emit via Redis failed for room {model_run_id}: {e}")

    def report_log(self, model_run_id, message, log_type='INFO'):
        # Keep existing report_log method
        payload = { "type": log_type, "message": message, "timestamp": datetime.datetime.utcnow().isoformat() }
        self._emit(model_run_id, 'training_log', payload)

    def report_json_log(self, model_run_id, json_data):
        # Keep existing report_json_log method
        json_data['timestamp'] = datetime.datetime.utcnow().isoformat()
        event_type = 'training_log' # Default event
        log_content_type = json_data.get('type')

        # Map specific log content types to different WebSocket events
        if log_content_type == 'progress': event_type = 'training_progress'
        elif log_content_type == 'metric': event_type = 'training_metric'
        # Analysis results and cleaning reports are also sent via 'training_log'
        elif log_content_type == 'analysis_result': event_type = 'training_log'
        elif log_content_type == 'cleaning_report': event_type = 'training_log'
        # Add more mappings if needed

        self._emit(model_run_id, event_type, json_data)

    def update_status(self, model_run_id, status):
        # Keep existing update_status method
        try:
            run = self._get_run(model_run_id) # Uses the method that raises ValueError
            run.status = status
             # Define terminal statuses clearly
            terminal_statuses = ['SUCCESS', 'FAILED', 'ANALYSIS_FAILED', 'CLEANING_SUCCESS', 'CLEANING_FAILED', 'CANCELLED'] # Added CANCELLED
            if status in terminal_statuses:
                 run.completed_at = db.func.now()
            db.session.commit()
            self.flask_app.logger.info(f"Updated status for run {model_run_id} to {status}")
            self._emit(model_run_id, 'status_update', {"status": status})
        except ValueError as ve:
             # Log the specific error if run wasn't found
             self.flask_app.logger.warning(f"Could not update status for run {model_run_id}: {ve}")
        except Exception as e:
            db.session.rollback()
            self.flask_app.logger.error(f"DB status update failed for run {model_run_id}: {e}", exc_info=True)
            # Attempt to notify client about DB error, might fail if run_id is invalid
            try: self._emit(model_run_id, 'status_update', {"status": "DB_ERROR", "error": str(e)})
            except: pass # Ignore emit errors here

    # --- NEW: Convenience method to call the streaming function ---
    def stream_output(self, process, model_run_id):
        """ Executes the subprocess output streaming. """
        stream_subprocess_output(
            process,
            model_run_id,
            self.report_log,         # Pass the instance's report_log
            self.report_json_log,    # Pass the instance's report_json_log
            self.flask_app.logger    # Pass the Flask logger instance
        )
    # --- End NEW Method ---