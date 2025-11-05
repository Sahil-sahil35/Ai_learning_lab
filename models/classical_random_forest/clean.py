#!/usr/bin/env python3
"""
Data Cleaning script for Tabular Data (CSV).
Accepts --data, --output-file, --options (JSON string), --output-dir.
Applies cleaning steps based on options.
Prints progress/report via structured JSON logs to stdout.
Saves cleaned data to --output-file and cleaning_report.json to --output-dir.
Generates preview of cleaned data.
"""
import pandas as pd
import numpy as np
import json
import os
import sys
import argparse
import time
from sklearn.impute import SimpleImputer, KNNImputer # Added KNN
from sklearn.preprocessing import LabelEncoder, StandardScaler, MinMaxScaler, RobustScaler # Added Scalers

# --- JSON Logging (same as analyze.py) ---
def log(message_type, payload):
    """Prints a structured JSON log to stdout."""
    log_entry = {
        "type": message_type,
        "timestamp": pd.Timestamp.utcnow().isoformat() + "Z",
        **payload
    }
    print(json.dumps(log_entry, default=str))
    sys.stdout.flush()

# --- Main Cleaning Function ---
def clean_tabular_data(data_path, output_file, options_json, output_dir):
    start_time = time.time()
    log("log", {"message": f"Starting tabular data cleaning: {data_path}"})
    os.makedirs(output_dir, exist_ok=True)

    # --- Initialize Report ---
    report = {
        'summary': {
            'original_file': os.path.basename(data_path),
            'cleaned_file': os.path.basename(output_file),
            'cleaning_time_seconds': 0,
            'original_shape': None,
            'cleaned_shape': None,
            'rows_removed': 0,
            'columns_removed': 0, # Placeholder
            'data_loss_percentage': 0
        },
        'options_applied': {},
        'operations_performed': {}, # Detailed counts/actions
        'preview_cleaned_data': {}, # Preview AFTER cleaning
        'issues_remaining': [] # Issues after cleaning
    }

    try:
        # --- 1. Load Data ---
        try:
            df = pd.read_csv(data_path, sep=None, engine='python', on_bad_lines='warn')
            if df.shape[1] == 1: df = pd.read_csv(data_path, sep=',', on_bad_lines='warn')
            original_shape = list(df.shape)
            report['summary']['original_shape'] = original_shape
            log("log", {"message": f"Loaded data. Original shape: {original_shape}"})
        except Exception as load_err:
             raise ValueError(f"Failed to load input CSV for cleaning: {load_err}")

        # --- 2. Parse Options ---
        try:
            options = json.loads(options_json)
            report['options_applied'] = options # Record options used
            log("log", {"message": f"Applying cleaning options: {options}"})
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON options string provided: {e}")

        # --- 3. Apply Cleaning Steps ---
        ops_performed = report['operations_performed']
        initial_rows = len(df)

        # Remove Duplicates
        if options.get('remove_duplicates', True): # Default to true? Or false? Let's say true.
            initial_count = len(df)
            df.drop_duplicates(inplace=True)
            removed = initial_count - len(df)
            ops_performed['duplicates_removed'] = int(removed)
            if removed > 0: log("log", {"message": f"Removed {removed} duplicate rows."})

        # Handle Missing Values
        if options.get('handle_missing', False):
            method = options.get('missing_method', 'remove')
            ops_performed['missing_values_method'] = method
            missing_before = int(df.isnull().sum().sum())
            numeric_cols = df.select_dtypes(include=np.number).columns
            categorical_cols = df.select_dtypes(exclude=np.number).columns # Simpler selection

            if method == 'remove':
                df.dropna(inplace=True)
            elif method in ['mean', 'median']:
                if len(numeric_cols) > 0:
                    imputer = SimpleImputer(strategy=method)
                    df[numeric_cols] = imputer.fit_transform(df[numeric_cols])
                # Always use mode for categoricals if imputing
                if len(categorical_cols) > 0 and df[categorical_cols].isnull().any().any():
                    cat_imputer = SimpleImputer(strategy='most_frequent')
                    df[categorical_cols] = cat_imputer.fit_transform(df[categorical_cols])
            elif method == 'mode': # Applies mode to ALL columns
                if df.isnull().any().any():
                     imputer = SimpleImputer(strategy='most_frequent')
                     df[:] = imputer.fit_transform(df) # Use df[:] to modify inplace if possible
            elif method == 'knn':
                 if len(numeric_cols) > 0 and df[numeric_cols].isnull().any().any():
                      try:
                          n_neighbors = options.get('knn_neighbors', 5)
                          knn_imputer = KNNImputer(n_neighbors=int(n_neighbors))
                          df[numeric_cols] = knn_imputer.fit_transform(df[numeric_cols])
                          ops_performed['knn_neighbors'] = int(n_neighbors)
                      except Exception as knn_err:
                           log("log", {"message": f"KNN Imputation failed: {knn_err}. Falling back to median for numeric.", "log_type": "WARNING"})
                           imputer = SimpleImputer(strategy='median')
                           df[numeric_cols] = imputer.fit_transform(df[numeric_cols])
                           ops_performed['missing_values_method'] += " (fallback: median)"
                 # Still use mode for categoricals with KNN for numeric
                 if len(categorical_cols) > 0 and df[categorical_cols].isnull().any().any():
                     cat_imputer = SimpleImputer(strategy='most_frequent')
                     df[categorical_cols] = cat_imputer.fit_transform(df[categorical_cols])

            missing_after = int(df.isnull().sum().sum())
            ops_performed['missing_values_fixed'] = int(missing_before - missing_after)
            if ops_performed['missing_values_fixed'] > 0 or method=='remove':
                 log("log", {"message": f"Handled missing values using '{method}'. Fixed: {ops_performed['missing_values_fixed']}."})
            # Check if any missing remain AFTER imputation (shouldn't happen with SimpleImputer)
            if missing_after > 0:
                 log("log", {"message": f"Warning: {missing_after} missing values remain after imputation attempt.", "log_type": "WARNING"})
                 report['issues_remaining'].append(f"Missing values remain: {missing_after}")


        # Handle Outliers (IQR Capping)
        if options.get('handle_outliers', False):
            method = options.get('outlier_method', 'iqr')
            ops_performed['outlier_handling_method'] = method
            outliers_capped = 0
            if method == 'iqr':
                 numeric_cols = df.select_dtypes(include=np.number).columns
                 for col in numeric_cols:
                      if df[col].nunique() > 1: # Avoid constants
                           Q1 = df[col].quantile(0.25)
                           Q3 = df[col].quantile(0.75)
                           IQR = Q3 - Q1
                           lower_bound = Q1 - 1.5 * IQR
                           upper_bound = Q3 + 1.5 * IQR

                           outlier_mask = (df[col] < lower_bound) | (df[col] > upper_bound)
                           col_outliers = int(outlier_mask.sum())
                           if col_outliers > 0:
                                outliers_capped += col_outliers
                                # Cap outliers
                                df[col] = np.where(df[col] < lower_bound, lower_bound, df[col])
                                df[col] = np.where(df[col] > upper_bound, upper_bound, df[col])
                 ops_performed['outliers_capped'] = int(outliers_capped)
                 if outliers_capped > 0: log("log", {"message": f"Capped {outliers_capped} outliers using IQR method."})
            # Add other outlier methods (e.g., Z-score) here if needed

        # Encode Categorical Variables (Label Encoding)
        if options.get('encode_categorical', True): # Default to true for many models
            categorical_cols = df.select_dtypes(include=['object', 'category']).columns
            encoded_cols = []
            encoding_map = {} # Store mapping if needed later
            if len(categorical_cols) > 0:
                 for col in categorical_cols:
                      try:
                          le = LabelEncoder()
                          df[col] = le.fit_transform(df[col].astype(str)) # Ensure string type
                          # encoding_map[col] = dict(zip(le.classes_, le.transform(le.classes_)))
                          encoded_cols.append(col)
                      except Exception as enc_err:
                           log("log", {"message": f"Failed to encode column '{col}': {enc_err}. Skipping.", "log_type": "WARNING"})
                 ops_performed['categorical_encoded_count'] = len(encoded_cols)
                 # ops_performed['encoding_details'] = encoding_map # Might be large
                 if len(encoded_cols) > 0: log("log", {"message": f"Label encoded {len(encoded_cols)} categorical columns."})
            else:
                 ops_performed['categorical_encoded_count'] = 0


        # Feature Scaling
        if options.get('feature_scaling', False):
            method = options.get('scaling_method', 'standard')
            ops_performed['feature_scaling_method'] = method
            numeric_cols = df.select_dtypes(include=np.number).columns
            scaled_cols = []
            if len(numeric_cols) > 0:
                if method == 'standard': scaler = StandardScaler()
                elif method == 'minmax': scaler = MinMaxScaler()
                elif method == 'robust': scaler = RobustScaler()
                else:
                    log("log", {"message": f"Unknown scaling method '{method}'. Skipping scaling.", "log_type": "WARNING"})
                    scaler = None

                if scaler:
                    try:
                        df[numeric_cols] = scaler.fit_transform(df[numeric_cols])
                        scaled_cols = list(numeric_cols)
                        ops_performed['scaled_columns_count'] = len(scaled_cols)
                        log("log", {"message": f"Applied '{method}' scaling to {len(scaled_cols)} numeric columns."})
                    except Exception as scale_err:
                         log("log", {"message": f"Scaling failed: {scale_err}. Skipping.", "log_type": "ERROR"})
                         report['issues_remaining'].append(f"Scaling failed: {scale_err}")

            else:
                 ops_performed['scaled_columns_count'] = 0
                 log("log", {"message": "No numeric columns found to scale.", "log_type": "INFO"})

        # --- 4. Final Shape & Summary Stats ---
        cleaned_shape = list(df.shape)
        report['summary']['cleaned_shape'] = cleaned_shape
        rows_removed = initial_rows - cleaned_shape[0]
        report['summary']['rows_removed'] = int(rows_removed)
        report['summary']['columns_removed'] = int(original_shape[1] - cleaned_shape[1]) # If cols were dropped
        if initial_rows > 0:
             report['summary']['data_loss_percentage'] = round((rows_removed / initial_rows) * 100, 2)

        # Check for remaining issues AFTER cleaning
        final_missing = int(df.isnull().sum().sum())
        if final_missing > 0:
             report['issues_remaining'].append(f"Missing values still remain: {final_missing}")
             log("log", {"message": f"CRITICAL WARNING: {final_missing} missing values remain after cleaning!", "log_type": "ERROR"})


        # --- 5. Generate Cleaned Data Preview ---
        preview_limit = 20
        preview_df_cleaned = df.head(preview_limit).copy()
        # Highlight remaining problematic cells (e.g., missing if they weren't handled)
        problem_cells_cleaned = {}
        for r_idx in range(len(preview_df_cleaned)):
             missing_cols_indices = [c_idx for c_idx, col in enumerate(preview_df_cleaned.columns) if pd.isna(preview_df_cleaned.iloc[r_idx, c_idx])]
             if missing_cols_indices:
                 problem_cells_cleaned[r_idx] = missing_cols_indices
        # Convert preview to JSON
        preview_cleaned_data = {
            'headers': list(df.columns),
            'rows': preview_df_cleaned.astype(object).where(pd.notnull(preview_df_cleaned), None).values.tolist(),
            'problem_cells': problem_cells_cleaned
        }
        report['preview_cleaned_data'] = preview_cleaned_data
        log("analysis_result", {"key": "preview_cleaned_data", "data": preview_cleaned_data}) # Use analysis_result type for preview


        # --- 6. Save Cleaned Data & Report ---
        try:
            df.to_csv(output_file, index=False)
            log("log", {"message": f"Cleaned data saved successfully to {output_file}"})
        except Exception as save_err:
             raise IOError(f"Failed to save cleaned data CSV: {save_err}")

        report['summary']['cleaning_time_seconds'] = round(time.time() - start_time, 2)
        report_path = os.path.join(output_dir, 'cleaning_report.json')
        try:
            # Convert numpy types before saving report
            serializable_report = json.loads(json.dumps(report, default=str))
            with open(report_path, 'w') as f:
                json.dump(serializable_report, f, indent=2)
            log("log", {"message": f"Cleaning report saved to {report_path}"})
        except Exception as report_err:
             log("log", {"message": f"Error saving cleaning report: {report_err}", "log_type": "ERROR"})
             # Don't fail the whole task if only report saving fails

        # --- Emit Final Report via log ---
        log("cleaning_report", {"data": report}) # Send final structured report

        log("log", {"message": "Tabular cleaning process completed."})

    except Exception as e:
        error_msg = f"Error during cleaning: {e}"
        log("log", {"message": error_msg, "log_type": "ERROR"})
        report['summary']['error'] = error_msg # Add error to report
        report['summary']['cleaned_shape'] = list(df.shape) if 'df' in locals() else None # Record shape at time of error
        report['summary']['cleaning_time_seconds'] = round(time.time() - start_time, 2)
        # Attempt to save partial error report
        try:
            report_path = os.path.join(output_dir, 'cleaning_report.json')
            serializable_report = json.loads(json.dumps(report, default=str))
            with open(report_path, 'w') as f:
                json.dump(serializable_report, f, indent=2)
            log("log", {"message": f"Partial error report saved to {report_path}", "log_type": "WARNING"})
        except Exception as report_save_err:
             log("log", {"message": f"Could not save error report: {report_save_err}", "log_type": "ERROR"})
        sys.exit(1) # Exit with error code

# --- Script Entrypoint ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Clean Tabular Data (CSV)')
    parser.add_argument('--data', required=True, help='Path to input data file (csv)')
    parser.add_argument('--output-file', required=True, help='Path to save cleaned data file (csv)')
    parser.add_argument('--options', required=True, help='JSON string of cleaning options')
    parser.add_argument('--output-dir', required=True, help='Directory to save cleaning report')
    parser.add_argument('--run-id', help='Run ID (optional, for context)')
    args = parser.parse_args()

    clean_tabular_data(args.data, args.output_file, args.options, args.output_dir)