"""
Secure sandbox execution environment for custom model training and validation.
Uses Docker containers with resource limits and security restrictions.
"""

import os
import uuid
import tempfile
import shutil
import docker
import json
import time
import subprocess
import threading
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

class SandboxExecutor:
    """Secure execution environment for custom ML code."""

    def __init__(self):
        self.client = docker.from_env()
        self.base_image = "ml-learnlab/sandbox:latest"
        self.temp_dir = Path(tempfile.gettempdir()) / "ml_sandbox"
        self.temp_dir.mkdir(exist_ok=True)

    def _create_sandbox_container(self, code_content: str, model_type: str,
                                 config: Dict[str, Any]) -> docker.models.containers.Container:
        """Create a sandbox container with the code and configuration."""
        container_name = f"sandbox-{uuid.uuid4().hex[:12]}"

        # Create temporary files
        work_dir = self.temp_dir / container_name
        work_dir.mkdir(exist_ok=True)

        try:
            # Write code to file
            code_file = work_dir / "model.py"
            with open(code_file, 'w') as f:
                f.write(code_content)

            # Write config to file
            config_file = work_dir / "config.json"
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)

            # Create validation script
            validation_script = work_dir / "validate.py"
            with open(validation_script, 'w') as f:
                f.write(self._get_validation_script(model_type))

            # Resource limits - enhanced for production
            limits = {
                'memory': '2g',  # 2GB RAM
                'cpu_quota': 200000,  # Limit to 2 cores maximum
                'cpu_period': 100000,
                'blkio_weight': 100,  # Low I/O priority
                'pids_limit': 50  # Limit process count
            }

            # Security settings - hardened for production
            security_opts = [
                'no-new-privileges:true',
                'seccomp=default',  # Use default seccomp profile for better security
                'apparmor:docker-default',  # Add AppArmor confinement
                'label=disable'  # Disable labeling for better compatibility
            ]

            # Create container
            container = self.client.containers.create(
                image=self.base_image,
                name=container_name,
                command="tail -f /dev/null",  # Keep container running
                working_dir="/workspace",
                volumes={
                    str(work_dir): {'bind': '/workspace', 'mode': 'rw'}
                },
                mem_limit=limits['memory'],
                cpu_quota=limits['cpu_quota'],
                cpu_period=limits['cpu_period'],
                blkio_weight=limits['blkio_weight'],
                pids_limit=limits['pids_limit'],
                security_opt=security_opts,
                read_only=False,  # Need to write to workspace
                network_mode='none',  # Complete network isolation for security
                remove=False  # We'll clean up manually
            )

            # Start container
            container.start()
            logger.info(f"Created sandbox container: {container_name}")

            return container

        except Exception as e:
            # Cleanup on error
            if work_dir.exists():
                shutil.rmtree(work_dir)
            raise e

    def _get_validation_script(self, model_type: str) -> str:
        """Get validation script for the model type."""
        return f'''
import sys
import ast
import importlib.util
import traceback

def validate_code():
    """Validate the model code."""
    errors = []
    warnings = []
    suggestions = []

    try:
        # Read the model code
        with open('model.py', 'r') as f:
            code_content = f.read()

        # Parse AST to check syntax
        try:
            ast.parse(code_content)
        except SyntaxError as e:
            errors.append(f"Syntax error: {{e}}")
            return {{"valid": False, "errors": errors}}

        # Import the module
        spec = importlib.util.spec_from_file_location("model", "model.py")
        model_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(model_module)

        # Check for required functions
        required_functions = ['train_model']
        for func_name in required_functions:
            if not hasattr(model_module, func_name):
                errors.append(f"Missing required function: {{func_name}}")

        # Check for train_model function signature
        if hasattr(model_module, 'train_model'):
            import inspect
            sig = inspect.signature(model_module.train_model)
            required_params = ['data_path']
            for param in required_params:
                if param not in sig.parameters:
                    errors.append(f"train_model() must accept '{param}' parameter")

        # Check for common ML libraries
        try:
            import pandas as pd
            import numpy as np
        except ImportError as e:
            warnings.append(f"ML library not available: {{e}}")

        # Validate model type specific requirements
        if '{model_type}' == 'classification':
            # Check for classification specific imports/requirements
            if 'sklearn' not in code_content and 'keras' not in code_content and 'tensorflow' not in code_content:
                suggestions.append("Consider using sklearn, keras, or tensorflow for classification tasks")
        elif '{model_type}' == 'regression':
            # Check for regression specific requirements
            if 'sklearn' not in code_content and 'keras' not in code_content and 'tensorflow' not in code_content:
                suggestions.append("Consider using sklearn, keras, or tensorflow for regression tasks")

        # Security checks
        dangerous_imports = ['os.system', 'subprocess.call', 'eval', 'exec']
        for dangerous in dangerous_imports:
            if dangerous in code_content:
                warnings.append(f"Potentially dangerous code detected: {{dangerous}}")

    except Exception as e:
        errors.append(f"Validation error: {{e}}")
        return {{"valid": False, "errors": errors, "traceback": traceback.format_exc()}}

    return {{
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "suggestions": suggestions
    }}

if __name__ == "__main__":
    result = validate_code()
    print(json.dumps(result))
'''

    def validate_code(self, code: str, model_type: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate code syntax and structure in sandbox."""
        container = None
        work_dir = None

        try:
            # Create sandbox container
            container = self._create_sandbox_container(code, model_type, config)

            # Run validation
            exit_code, output = container.exec_run(
                "python validate.py",
                workdir="/workspace"
            )

            # Parse results
            try:
                result = json.loads(output.decode('utf-8'))
            except json.JSONDecodeError:
                result = {
                    "valid": False,
                    "errors": [f"Validation script error: {output.decode('utf-8')}"]
                }

            return result

        except Exception as e:
            logger.error(f"Code validation error: {e}")
            return {
                "valid": False,
                "errors": [f"Validation failed: {str(e)}"]
            }

        finally:
            # Cleanup
            if container:
                try:
                    container.stop()
                    container.remove()
                except:
                    pass

            if work_dir and work_dir.exists():
                shutil.rmtree(work_dir)

    def train_model(self, code: str, model_type: str, data_path: str,
                    config: Dict[str, Any], model_id: str) -> Dict[str, Any]:
        """Train model in sandbox environment with enhanced security and resource management."""
        container = None
        work_dir = None
        job_id = str(uuid.uuid4())

        # Set training timeout (30 minutes max as per security requirements)
        training_timeout = config.get('timeout', 1800)  # 30 minutes default

        try:
            # Create sandbox container
            container = self._create_sandbox_container(code, model_type, config)
            work_dir = self.temp_dir / container.name

            # Copy data to container (simplified - in production would use proper data mounting)
            data_filename = Path(data_path).name
            container_path = f"/workspace/data/{data_filename}"

            # Create training script
            training_script = work_dir / "train.py"
            with open(training_script, 'w') as f:
                f.write(f'''
import sys
import json
import traceback
from model import train_model

def main():
    try:
        # Load configuration
        with open('config.json', 'r') as f:
            config = json.load(f)

        # Set output directory
        output_dir = '/workspace/output'
        os.makedirs(output_dir, exist_ok=True)

        # Train model
        metrics = train_model(
            data_path='{container_path}',
            config=config,
            output_dir=output_dir
        )

        # Save metrics
        with open(f'/workspace/output/metrics.json', 'w') as f:
            json.dump(metrics, f, indent=2)

        print("Training completed successfully")
        print(json.dumps({{"status": "success", "metrics": metrics}}))

    except Exception as e:
        error_info = {{
            "status": "error",
            "error": str(e),
            "traceback": traceback.format_exc()
        }}
        print(json.dumps(error_info))
        sys.exit(1)

if __name__ == "__main__":
    main()
''')

            # Start training in background
            def train_in_background():
                try:
                    exit_code, output = container.exec_run(
                        f"python train.py",
                        workdir="/workspace"
                    )

                    # Log results (in production would store in database)
                    logger.info(f"Training job {job_id} completed with exit code: {exit_code}")
                    logger.info(f"Training output: {output.decode('utf-8')}")

                    # Update model status in database (simplified)
                    # This would be handled by the calling function

                except Exception as e:
                    logger.error(f"Background training error: {e}")

            # Start training thread
            training_thread = threading.Thread(target=train_in_background)
            training_thread.daemon = True
            training_thread.start()

            return {
                'job_id': job_id,
                'status': 'started',
                'estimated_duration': 300  # 5 minutes estimate
            }

        except Exception as e:
            logger.error(f"Model training error: {e}")
            return {
                'job_id': job_id,
                'status': 'failed',
                'error': str(e)
            }

        finally:
            # Note: Don't cleanup immediately as training runs in background
            # Cleanup would be handled by a monitoring service
            pass

    def execute_code(self, code: str, inputs: List[Any] = None,
                     timeout: int = 30) -> Tuple[bool, Any]:
        """Execute arbitrary code with timeout."""
        container = None
        work_dir = None

        try:
            # Create execution script
            work_dir = self.temp_dir / f"exec-{uuid.uuid4().hex[:12]}"
            work_dir.mkdir(exist_ok=True)

            exec_script = work_dir / "execute.py"
            with open(exec_script, 'w') as f:
                f.write(f'''
import sys
import json
import traceback

# Code to execute
{code}

if __name__ == "__main__":
    try:
        # Execute with provided inputs if any
        if {repr(inputs)}:
            inputs = {repr(inputs)}
            result = main(*inputs)
        else:
            result = main()

        print(json.dumps({{"success": True, "result": result}}))
    except Exception as e:
        print(json.dumps({{"success": False, "error": str(e), "traceback": traceback.format_exc()}}))
''')

            # Create temporary container for execution
            container = self.client.containers.run(
                image=self.base_image,
                command=f"python execute.py",
                volumes={str(work_dir): {'bind': '/workspace', 'mode': 'rw'}},
                working_dir="/workspace",
                mem_limit="512m",  # Lower memory for simple execution
                cpu_quota=25000,
                detach=True,
                remove=True
            )

            # Wait for completion with timeout
            result = container.wait(timeout=timeout)

            # Get output
            logs = container.logs().decode('utf-8')

            # Parse result
            try:
                output = json.loads(logs.strip())
                return output['success'], output.get('result') if output['success'] else output.get('error')
            except json.JSONDecodeError:
                return False, f"Execution output: {logs}"

        except docker.errors.ContainerError as e:
            return False, f"Container execution error: {e}"
        except docker.errors.TimeoutError:
            if container:
                container.kill()
            return False, "Execution timed out"
        except Exception as e:
            return False, f"Execution error: {e}"

        finally:
            # Cleanup
            if container:
                try:
                    container.remove(force=True)
                except:
                    pass

            if work_dir and work_dir.exists():
                shutil.rmtree(work_dir)

    def cleanup_container(self, container_name: str):
        """Clean up a specific container."""
        try:
            container = self.client.containers.get(container_name)
            container.stop()
            container.remove()
            logger.info(f"Cleaned up container: {container_name}")
        except docker.errors.NotFound:
            logger.warning(f"Container not found for cleanup: {container_name}")
        except Exception as e:
            logger.error(f"Error cleaning up container {container_name}: {e}")

    def cleanup_old_containers(self, max_age_hours: int = 24):
        """Clean up old sandbox containers."""
        try:
            containers = self.client.containers.list(
                all=True,
                filters={"name": "sandbox-"}
            )

            for container in containers:
                try:
                    # Check container age
                    container.reload()
                    created_time = container.attrs['Created']
                    created = datetime.datetime.strptime(
                        created_time[:19], "%Y-%m-%dT%H:%M:%S"
                    ).replace(tzinfo=datetime.timezone.utc)

                    age_hours = (datetime.datetime.now(datetime.timezone.utc) - created).total_seconds() / 3600

                    if age_hours > max_age_hours:
                        container.remove(force=True)
                        logger.info(f"Cleaned up old container: {container.name}")

                except Exception as e:
                    logger.error(f"Error cleaning up container {container.name}: {e}")

        except Exception as e:
            logger.error(f"Error in cleanup routine: {e}")

# Initialize sandbox executor
sandbox_executor = SandboxExecutor()