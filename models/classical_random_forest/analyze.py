#!/usr/bin/env python3
"""
Data Analyzer for Tabular Data (CSV).
Accepts --data path (csv) and --output-dir path.
Prints analysis results (including preview and issues) as structured JSON to stdout
and saves a complete analysis_results.json file.
"""
import pandas as pd
import numpy as np
import json
import os
import sys
import argparse
from scipy import stats # For skewness/kurtosis

# --- Custom JSON Encoder for Numpy Types ---
class NumpyEncoder(json.JSONEncoder):
    """ Special json encoder for numpy types """
    def default(self, obj):
        if isinstance(obj, (np.int_, np.intc, np.intp, np.int8,
                            np.int16, np.int32, np.int64, np.uint8,
                            np.uint16, np.uint32, np.uint64)):
            return int(obj)
        elif isinstance(obj, (np.float_, np.float16, np.float32,
                               np.float64)):
            return float(obj)
        elif isinstance(obj, (np.ndarray,)):
            return obj.tolist()
        return json.JSONEncoder.default(self, obj)

# --- Plain Text Logging ---
def log(message_type, payload):
    """Prints a plain text log to stdout."""
    message = payload.get('message', '')
    if isinstance(message, dict):
        message = json.dumps(message)

    print(f"[{message_type.upper()}] {message}")
    sys.stdout.flush()

# --- Analysis Function ---
def analyze_tabular_data(data_path, output_dir):
    log("log", {"message": f"Starting tabular data analysis: {data_path}"})
    os.makedirs(output_dir, exist_ok=True)

    full_analysis_results = {
        'basic_info': {},
        'data_quality': {},
        'statistical_summary': {},
        'distribution_analysis': {},
        'preview_data': {},
        'issues': [] # Added issues list
    }
    issues = full_analysis_results['issues']

    try:
        # --- 1. Load Data ---
        try:
            # Try detecting common delimiters, fall back to comma
            df = pd.read_csv(data_path, sep=None, engine='python', on_bad_lines='warn')
            if df.shape[1] == 1: # If only one col, likely wrong delimiter, force comma
                 log("log", {"message": "Single column detected, retrying with comma delimiter.", "log_type": "WARNING"})
                 df = pd.read_csv(data_path, sep=',', on_bad_lines='warn')
            log("log", {"message": f"Successfully loaded data. Shape: {df.shape}"})
        except Exception as load_err:
            log("log", {"message": f"Error loading CSV: {load_err}", "log_type": "ERROR"})
            issues.append({"severity": "ERROR", "message": f"Failed to load or parse CSV file: {load_err}"})
            # Attempt partial save before exiting
            save_results(full_analysis_results, output_dir)
            sys.exit(1)

        # --- 2. Basic Info ---
        basic_info = {
            'shape': list(df.shape),
            'columns': list(df.columns),
            'data_types': df.dtypes.astype(str).to_dict(),
            'memory_usage': int(df.memory_usage(deep=True).sum())
        }
        full_analysis_results['basic_info'] = basic_info
        log("analysis_result", {"key": "basic_info", "data": basic_info})

        # --- 3. Data Quality ---
        missing_values = df.isnull().sum()
        missing_percentage = (missing_values / len(df) * 100)
        duplicate_rows = int(df.duplicated().sum())

        data_quality = {
            'missing_values': missing_values[missing_values > 0].astype(int).to_dict(),
            'missing_percentage': missing_percentage[missing_percentage > 0].round(2).to_dict(),
            'duplicate_rows': duplicate_rows
            # Outliers detection could be added here (e.g., IQR) but might be slow
        }
        full_analysis_results['data_quality'] = data_quality
        log("analysis_result", {"key": "data_quality", "data": data_quality}) # Emit summary

        # Populate issues list based on quality checks
        if sum(data_quality['missing_values'].values()) > 0:
            issues.append({
                "severity": "WARNING",
                "message": f"Found {sum(data_quality['missing_values'].values())} missing values across {len(data_quality['missing_values'])} columns.",
                "details": data_quality['missing_percentage']
            })
        if duplicate_rows > 0:
            issues.append({
                "severity": "WARNING",
                "message": f"Found {duplicate_rows} duplicate rows."
            })

        # --- 4. Statistical Summary ---
        numeric_summary = df.describe(include=[np.number]).round(3).astype(object).where(pd.notnull(df), None).to_dict()
        categorical_summary = {}
        for col in df.select_dtypes(include=['object', 'category']).columns:
             summary = df[col].describe().astype(object).where(pd.notnull(df[col]), None).to_dict()
             # Add top 5 value counts for context
             summary['top_5_values'] = df[col].value_counts().head(5).astype(object).to_dict()
             categorical_summary[col] = summary

        statistical_summary = {'numeric': numeric_summary, 'categorical': categorical_summary}
        full_analysis_results['statistical_summary'] = statistical_summary
        # Don't log full stats, too large. Quality summary is enough for initial view.

        # --- 5. Distribution Analysis ---
        distributions = {}
        for col in df.select_dtypes(include=[np.number]).columns:
            if df[col].nunique() > 1: # Avoid calculating for constant columns
                skewness = round(float(stats.skew(df[col].dropna())), 3)
                kurtosis = round(float(stats.kurtosis(df[col].dropna())), 3)
                distributions[col] = {
                    'skewness': skewness,
                    'kurtosis': kurtosis,
                    'normality_suggestion': 'Likely Normal' if abs(skewness) < 1 and abs(kurtosis) < 1 else 'Likely Skewed/Non-Normal'
                }
        full_analysis_results['distribution_analysis'] = distributions
        # Don't log distributions by default.

        # --- 6. Data Preview with Issue Highlighting ---
        preview_limit = 20 # Number of rows for preview
        preview_df = df.head(preview_limit).copy()

        # Identify problematic cells (only missing values for now)
        problem_cells = {} # {rowIndex: [colIndex1, colIndex2, ...]}
        for r_idx in range(len(preview_df)):
             missing_cols_indices = [c_idx for c_idx, col in enumerate(preview_df.columns) if pd.isna(preview_df.iloc[r_idx, c_idx])]
             if missing_cols_indices:
                 problem_cells[r_idx] = missing_cols_indices

        # Convert preview to JSON serializable format (handle NaN, NaT, etc.)
        preview_data = {
            'headers': list(df.columns),
            'rows': preview_df.astype(object).where(pd.notnull(preview_df), None).values.tolist(), # Convert NaN to None
            'problem_cells': problem_cells # Include indices of problematic cells
        }
        full_analysis_results['preview_data'] = preview_data
        log("analysis_result", {"key": "preview_data", "data": preview_data}) # Emit preview


        # --- 7. Final Log and Save ---
        log("analysis_result", {"key": "issues", "data": issues}) # Emit final issues list
        save_results(full_analysis_results, output_dir)
        log("log", {"message": f"Analysis complete. Found {len(issues)} potential issues."})

    except Exception as e:
        error_msg = f"Unexpected error during analysis: {e}"
        log("log", {"message": error_msg, "log_type": "ERROR"})
        issues.append({"severity": "CRITICAL", "message": error_msg})
        full_analysis_results['issues'] = issues # Ensure errors are in the final dict
        # Attempt to save partial results containing the error
        save_results(full_analysis_results, output_dir)
        sys.exit(1) # Exit with error code

def save_results(results_dict, output_dir):
    """Saves the full analysis results to a JSON file."""
    results_file_path = os.path.join(output_dir, 'analysis_results.json')
    try:
        with open(results_file_path, 'w') as f:
            json.dump(results_dict, f, indent=2, cls=NumpyEncoder)
        log("log", {"message": f"Full analysis results saved to {results_file_path}"})
    except Exception as save_err:
         log("log", {"message": f"Error saving analysis results JSON: {save_err}", "log_type": "ERROR"})

# --- Script Entrypoint ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Analyze Tabular Data (CSV)')
    parser.add_argument('--data', required=True, help='Path to input CSV data file')
    parser.add_argument('--output-dir', required=True, help='Directory to save analysis results')
    parser.add_argument('--run-id', help='Run ID (optional, for context)') # Optional run-id
    args = parser.parse_args()

    analyze_tabular_data(args.data, args.output_dir)