#!/usr/bin/env python3
"""
Random Forest training script for tabular data.
Accepts --data, --output-dir, --run-id, and model parameters.
Prints progress and metrics as structured JSON logs to stdout.
Saves model, final metrics, and summary.
"""
import argparse
import pandas as pd
import numpy as np
import json
import os
import sys
import time
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import (accuracy_score, classification_report, confusion_matrix,
                           mean_squared_error, r2_score, roc_auc_score, precision_recall_fscore_support) # Added PRF
from sklearn.preprocessing import LabelEncoder
import joblib # Use joblib for model saving

# --- JSON Logging (same as analyze.py/clean.py) ---
def log(message_type, payload):
    """Prints a structured JSON log to stdout."""
    log_entry = {
        "type": message_type,
        "timestamp": pd.Timestamp.utcnow().isoformat() + "Z",
        **payload
    }
    print(json.dumps(log_entry, default=str)) # default=str handles numpy types
    sys.stdout.flush()

# --- Training Function ---
def train_random_forest(args):
    start_time = time.time()
    log("log", {"message": "Random Forest training script started."})
    os.makedirs(args.output_dir, exist_ok=True)

    training_history = []
    final_metrics = {}

    try:
        # --- 1. Load Data ---
        try:
            # Assume data is cleaned CSV now
            df = pd.read_csv(args.data)
            log("log", {"message": f"Loaded data from {args.data}. Shape: {df.shape}"})
        except Exception as e:
            raise ValueError(f"Failed to load training data CSV: {e}")

        # --- 2. Prepare Data (Features/Target, Split) ---
        if args.target_column not in df.columns:
            raise ValueError(f"Target column '{args.target_column}' not found in the data.")

        X = df.drop(columns=[args.target_column])
        y = df[args.target_column]

        # --- Data Type Check & Task Determination ---
        # Infer task if not provided, check for consistency
        inferred_task = 'regression' if pd.api.types.is_numeric_dtype(y) and y.nunique() > 15 else 'classification'
        if args.task_type and args.task_type != inferred_task:
             log("log", {"message": f"Warning: Provided task_type '{args.task_type}' might conflict with inferred type '{inferred_task}' based on target '{args.target_column}'. Proceeding with '{args.task_type}'.", "log_type": "WARNING"})
             task = args.task_type
        else:
             task = inferred_task
             log("log", {"message": f"Inferred task type: {task}"})


        # Handle potential non-numeric features (should be encoded by clean.py ideally)
        numeric_cols = X.select_dtypes(include=np.number).columns
        non_numeric_cols = X.select_dtypes(exclude=np.number).columns
        if len(non_numeric_cols) > 0:
             log("log", {"message": f"Warning: Non-numeric columns found: {list(non_numeric_cols)}. Attempting Label Encoding. Cleaning step is recommended.", "log_type": "WARNING"})
             for col in non_numeric_cols:
                 try:
                     X[col] = LabelEncoder().fit_transform(X[col].astype(str))
                 except Exception as enc_err:
                     raise ValueError(f"Failed to auto-encode non-numeric column '{col}': {enc_err}. Please clean data first.")

        # Split data
        stratify_opt = y if task == 'classification' and y.nunique() > 1 else None
        try:
             X_train, X_val, y_train, y_val = train_test_split(
                 X, y, test_size=args.test_size, random_state=args.random_state, stratify=stratify_opt
             )
             log("log", {"message": f"Data split complete. Train shape: {X_train.shape}, Val shape: {X_val.shape}"})
        except ValueError as split_err:
             if "n_splits=1" in str(split_err): # Handle small classes
                  log("log", {"message": "Stratification failed due to small class size. Splitting without stratification.", "log_type": "WARNING"})
                  X_train, X_val, y_train, y_val = train_test_split(
                      X, y, test_size=args.test_size, random_state=args.random_state, stratify=None
                  )
             else: raise split_err # Re-raise other split errors


        # --- 3. Initialize & Train Model (Iterative for Progress) ---
        model_params = {
            'n_estimators': 1, # Start with 1
            'max_depth': args.max_depth if args.max_depth else None,
            'random_state': args.random_state,
            'warm_start': True, # Crucial for iterative training
            'n_jobs': -1 # Use all available cores
        }
        if task == 'classification':
            model = RandomForestClassifier(**model_params)
        else:
            model = RandomForestRegressor(**model_params)

        total_estimators = args.n_estimators
        log("log", {"message": f"Starting iterative training for {total_estimators} estimators..."})

        for i in range(1, total_estimators + 1):
            model.n_estimators = i
            model.fit(X_train, y_train)

            # Calculate metrics every N steps for efficiency, but log progress more often
            log_metrics_step = max(1, total_estimators // 20) # Log metrics roughly 20 times + final
            should_log_metrics = (i % log_metrics_step == 0) or (i == total_estimators)

            metrics_entry = {
                "estimator": i,
                "total_estimators": total_estimators,
                # Add more relevant metrics based on task
            }

            if should_log_metrics:
                train_pred = model.predict(X_train)
                val_pred = model.predict(X_val)

                if task == 'classification':
                    train_acc = accuracy_score(y_train, train_pred)
                    val_acc = accuracy_score(y_val, val_pred)
                    metrics_entry.update({
                        'train_accuracy': round(train_acc, 4),
                        'val_accuracy': round(val_acc, 4),
                        # Simple loss approximation
                        'train_loss': round(1 - train_acc, 4),
                        'val_loss': round(1 - val_acc, 4)
                    })
                    # Add Precision/Recall/F1 for binary/multiclass if needed (can be slower)
                    if i == total_estimators: # Calculate more detailed final metrics
                         precision, recall, f1, _ = precision_recall_fscore_support(y_val, val_pred, average='weighted', zero_division=0)
                         metrics_entry['val_precision'] = round(precision, 4)
                         metrics_entry['val_recall'] = round(recall, 4)
                         metrics_entry['val_f1_score'] = round(f1, 4)
                         try: # Calculate AUC if possible (binary/multiclass with predict_proba)
                             if hasattr(model, "predict_proba"):
                                 val_proba = model.predict_proba(X_val)
                                 # Handle binary vs multiclass AUC
                                 if val_proba.shape[1] == 2:
                                     auc = roc_auc_score(y_val, val_proba[:, 1])
                                 else:
                                     auc = roc_auc_score(y_val, val_proba, multi_class='ovr', average='weighted')
                                 metrics_entry['val_roc_auc'] = round(auc, 4)
                         except Exception as auc_err:
                              log("log", {"message": f"Could not calculate AUC: {auc_err}", "log_type": "WARNING"})


                else: # Regression
                    train_rmse = np.sqrt(mean_squared_error(y_train, train_pred))
                    val_rmse = np.sqrt(mean_squared_error(y_val, val_pred))
                    train_r2 = r2_score(y_train, train_pred)
                    val_r2 = r2_score(y_val, val_pred)
                    metrics_entry.update({
                        'train_rmse': round(train_rmse, 4),
                        'val_rmse': round(val_rmse, 4),
                        'train_r2': round(train_r2, 4),
                        'val_r2': round(val_r2, 4)
                    })
                # Log metrics
                log("metric", metrics_entry)
                training_history.append(metrics_entry)
                final_metrics = metrics_entry # Keep track of the latest full metric set

            # Log progress more frequently
            if i % max(1, total_estimators // 50) == 0 or i == total_estimators: # Log progress roughly 50 times
                log("progress", {
                    "current_step": i,
                    "total_steps": total_estimators,
                    "step_name": "Estimator"
                })

        log("log", {"message": "Training loop completed."})

        # --- 4. Feature Importance ---
        try:
            importances = model.feature_importances_
            feature_names = X.columns
            feature_importance_dict = dict(sorted(zip(feature_names, importances), key=lambda item: item[1], reverse=True))
            log("analysis_result", {"key": "feature_importance", "data": feature_importance_dict})
        except Exception as fi_err:
             log("log", {"message": f"Could not calculate feature importances: {fi_err}", "log_type": "WARNING"})
             feature_importance_dict = None


        # --- 5. Final Artifacts ---
        log("log", {"message": "Saving final model and results..."})

        # Save Model
        model_path = os.path.join(args.output_dir, 'model.joblib')
        joblib.dump(model, model_path)
        log("log", {"message": f"Model saved to {model_path}"})

        # Save Training History
        history_path = os.path.join(args.output_dir, 'training_history.json')
        with open(history_path, 'w') as f:
            json.dump(training_history, f, indent=2)

        # Save Final Metrics (Refined from the last iteration)
        final_metrics_path = os.path.join(args.output_dir, 'final_metrics.json')
        # Select key final metrics based on task
        metrics_to_save = {}
        if task == 'classification':
             keys = ['val_accuracy', 'val_precision', 'val_recall', 'val_f1_score', 'val_roc_auc', 'val_loss', 'train_accuracy', 'train_loss']
        else: # Regression
             keys = ['val_r2', 'val_rmse', 'train_r2', 'train_rmse']

        for k in keys:
             if k in final_metrics:
                 metrics_to_save[k] = final_metrics[k]
        # Add confusion matrix if classification
        if task == 'classification':
             try:
                 cm = confusion_matrix(y_val, val_pred)
                 metrics_to_save['confusion_matrix'] = cm.tolist() # Convert to list for JSON
             except Exception as cm_err:
                 log("log", {"message": f"Could not generate confusion matrix: {cm_err}", "log_type": "WARNING"})


        with open(final_metrics_path, 'w') as f:
            json.dump(metrics_to_save, f, indent=2)
        log("log", {"message": f"Final metrics saved to {final_metrics_path}"})


        # Save Educational Summary
        summary = {
            "model_type": "Random Forest",
            "task": task.capitalize(),
            "final_metrics_summary": {k: v for k, v in metrics_to_save.items() if k.startswith('val_')}, # Key validation metrics
            "feature_importance_top_5": dict(list(feature_importance_dict.items())[:5]) if feature_importance_dict else None,
            "training_time_seconds": round(time.time() - start_time, 2),
            "training_iters": total_estimators,
            "data_shape": {"train": list(X_train.shape), "validation": list(X_val.shape)}
        }
        summary_path = os.path.join(args.output_dir, 'educational_summary.json')
        with open(summary_path, 'w') as f:
             json.dump(summary, f, indent=2)
        log("log", {"message": f"Educational summary saved to {summary_path}"})


    except Exception as e:
        error_msg = f"Critical training error: {e}"
        # --- IMPORTANT: Log error as JSON via stdout ---
        # The streaming fix in the Celery task will catch stderr, but also log via stdout for redundancy
        log("log", {"message": error_msg, "log_type": "ERROR"})
        # --- Print to stderr as well, just in case ---
        print(f"ERROR: {error_msg}", file=sys.stderr)
        sys.exit(1) # Exit with non-zero code

# --- Script Entrypoint ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Random Forest Training Script')
    # --- Standard args ---
    parser.add_argument('--data', required=True, help='Path to input CSV data file (cleaned)')
    parser.add_argument('--output-dir', required=True, help='Directory to save model and results')
    parser.add_argument('--run-id', required=True, help='Run ID for logging context')

    # --- Args from model config.json ---
    # Match names in config.json
    parser.add_argument('--target_column', type=str, required=True, help='Name of the target variable column')
    parser.add_argument('--task_type', type=str, choices=['classification', 'regression'], help='Explicit task type (optional, will infer if omitted)')
    parser.add_argument('--test_size', type=float, default=0.2, help='Proportion of data for validation set')
    parser.add_argument('--n_estimators', type=int, default=100, help='Number of trees in the forest')
    # Use 'store_true' for boolean flags if needed, or handle None for numbers
    parser.add_argument('--max_depth', type=int, default=None, help='Maximum depth of the trees (None for unlimited)')
    parser.add_argument('--random_state', type=int, default=42, help='Seed for reproducibility')
    # Add other RF parameters as needed (min_samples_split, etc.)

    args = parser.parse_args()

    # --- Convert potential 'None' string back to None for max_depth ---
    if isinstance(args.max_depth, str) and args.max_depth.lower() == 'none':
        args.max_depth = None

    train_random_forest(args)