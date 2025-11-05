# backend/app/services/model_registry.py
import os
import json
from flask import current_app

def get_available_models():
    """
    Scans the MODELS_DIR for valid model packages.
    A valid package MUST contain config.json, analyze.py, train.py
    and optionally clean.py.
    config.json must have id, name, data_type, analysis_script, training_script.
    """
    models_dir = current_app.config['MODELS_DIR']
    available_models = []

    if not os.path.exists(models_dir):
        current_app.logger.error(f"Models directory not found: {models_dir}")
        return []

    required_keys = ['id', 'name', 'data_type', 'analysis_script', 'training_script', 'parameters']
    required_scripts_base = ['analyze.py', 'train.py'] # Base required scripts

    for item_name in os.listdir(models_dir):
        model_path = os.path.join(models_dir, item_name)
        config_path = os.path.join(model_path, 'config.json')

        # --- START FIX [Issue #14] ---
        # 1. Check if it's a directory
        if not os.path.isdir(model_path):
            current_app.logger.debug(f"Skipping non-directory item: {item_name}")
            continue

        # 2. Check for config.json
        if not os.path.exists(config_path):
            current_app.logger.warning(f"Skipping model '{item_name}': Missing config.json.")
            continue

        try:
            with open(config_path, 'r') as f:
                config = json.load(f)

            # 3. Validate config.json required keys
            missing_keys = [key for key in required_keys if key not in config]
            if missing_keys:
                current_app.logger.warning(f"Invalid config.json in '{item_name}': Missing keys: {', '.join(missing_keys)}.")
                continue

            # 4. Verify config 'id' matches directory name (Convention)
            if config['id'] != item_name:
                 current_app.logger.warning(f"Config 'id' ({config['id']}) does not match directory name ('{item_name}') in {item_name}.")
                 continue # Enforce convention

            # 5. Check for required script files specified in config
            required_scripts = list(required_scripts_base) # Copy base list
            analysis_script = config.get('analysis_script', 'analyze.py')
            training_script = config.get('training_script', 'train.py')
            cleaning_script = config.get('cleaning_script') # Optional

            missing_scripts = []
            analysis_path = os.path.join(model_path, analysis_script)
            training_path = os.path.join(model_path, training_script)
            cleaning_path = os.path.join(model_path, cleaning_script) if cleaning_script else None

            if not os.path.exists(analysis_path) or not os.path.isfile(analysis_path):
                 missing_scripts.append(analysis_script)
            if not os.path.exists(training_path) or not os.path.isfile(training_path):
                 missing_scripts.append(training_script)
            # Optionally check for cleaning script if defined in config
            # if cleaning_script and (not os.path.exists(cleaning_path) or not os.path.isfile(cleaning_path)):
            #     missing_scripts.append(cleaning_script)

            if missing_scripts:
                 current_app.logger.warning(f"Skipping model '{item_name}': Missing required script files: {', '.join(missing_scripts)}.")
                 continue

            # 6. Basic parameter validation (check if it's a list)
            if not isinstance(config.get('parameters'), list):
                 current_app.logger.warning(f"Invalid config.json in '{item_name}': 'parameters' key is not a list.")
                 continue

            # If all checks pass, add the model config
            available_models.append(config)
            current_app.logger.info(f"Successfully loaded model: {item_name}")
        # --- END FIX [Issue #14] ---

        except json.JSONDecodeError:
            current_app.logger.error(f"Error decoding config.json in {item_name}")
        except Exception as e:
            current_app.logger.error(f"Error loading model {item_name}: {e}")

    return available_models