#!/usr/bin/env python3
"""
Data Analyzer for Image ZIP Data.
Accepts a --data path (zip file) and --output-dir path.
Extracts the zip, analyzes structure (train/val, classes), file types.
Prints analysis results as structured JSON to stdout and saves analysis_results.json.
"""
import zipfile
import json
import os
import sys
import argparse
from collections import defaultdict
import datetime # Use datetime for timestamps

# --- JSON Logging ---
def log(message_type, payload):
    """Prints a structured JSON log to stdout."""
    log_entry = {
        "type": message_type,
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z", # ISO 8601 format
        **payload
    }
    # Use default=str for potentially non-serializable types if any occur
    print(json.dumps(log_entry, default=str))
    sys.stdout.flush()

# --- Analysis Function ---
def analyze_image_zip(data_path, output_dir):
    log("log", {"message": f"Starting image ZIP analysis: {data_path}"})
    os.makedirs(output_dir, exist_ok=True)

    full_analysis_results = {
        'basic_info': {},
        'data_quality': {}, # Placeholder, less relevant for zip structure
        'structure_summary': {},
        'file_summary': {},
        'preview_data': {}, # Simple file list preview
        'issues': []
    }
    issues = full_analysis_results['issues']

    try:
        # --- 1. Validate & Extract ZIP ---
        if not zipfile.is_zipfile(data_path):
            raise ValueError("Input file is not a valid ZIP archive.")

        extracted_dir = os.path.join(output_dir, "extracted_data")
        os.makedirs(extracted_dir, exist_ok=True)
        file_list = []
        log("log", {"message": f"Extracting ZIP archive to {extracted_dir}..."})
        try:
            with zipfile.ZipFile(data_path, 'r') as zf:
                # Filter out macOS resource fork files during extraction list creation
                file_list = [f for f in zf.namelist() if not f.startswith('__MACOSX/') and not f.endswith('.DS_Store')]
                for member in file_list:
                    zf.extract(member, extracted_dir) # Extract only necessary files
            log("log", {"message": f"Successfully extracted {len(file_list)} relevant files."})
        except zipfile.BadZipFile:
            raise ValueError("ZIP file is corrupted.")
        except Exception as extract_err:
             raise IOError(f"Error extracting ZIP file: {extract_err}")

        # --- 2. Analyze Structure & Files ---
        structure = defaultdict(lambda: defaultdict(int)) # { 'train': {'classA': 10, 'classB': 12}, 'val': {...} }
        file_types = defaultdict(int)
        class_names = set()
        preview_files = [] # Store first few file paths for preview

        valid_image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff'} # Common image types
        non_image_files = []

        # Use os.walk for robust directory traversal after extraction
        root_extracted_path = extracted_dir # Start walking from the extraction root
        if len(os.listdir(root_extracted_path)) == 1 and os.path.isdir(os.path.join(root_extracted_path, os.listdir(root_extracted_path)[0])):
             # Handle case where zip contains a single top-level folder
             root_extracted_path = os.path.join(root_extracted_path, os.listdir(root_extracted_path)[0])
             log("log", {"message": f"Adjusted analysis root to single top-level folder found in ZIP: {os.path.basename(root_extracted_path)}"})


        for dirpath, dirnames, filenames in os.walk(root_extracted_path):
            # Make dirpath relative to the (potentially adjusted) extraction root
            relative_dirpath = os.path.relpath(dirpath, extracted_dir)

            for filename in filenames:
                relative_filepath = os.path.join(relative_dirpath, filename)
                # Skip macOS hidden files explicitly
                if filename == '.DS_Store' or filename.startswith('._'): continue

                ext = os.path.splitext(filename)[1].lower()
                if ext: file_types[ext] += 1

                # Add to preview
                if len(preview_files) < 15:
                     preview_files.append(relative_filepath.replace(os.path.sep, '/')) # Use forward slash for display

                # Check if it's a likely image
                if ext not in valid_image_extensions:
                     non_image_files.append(relative_filepath)

                # Analyze structure (expecting train/class/img.jpg or val/class/img.jpg)
                parts = relative_filepath.split(os.path.sep)
                # Adjust part indices based on whether there was a top-level folder
                offset = 0
                if root_extracted_path != extracted_dir:
                    offset = 1 # Skip the top-level folder name part

                if len(parts) > (2 + offset): # Need at least split/class/file
                    split_name = parts[offset]
                    class_name = parts[offset + 1]
                    if split_name in ['train', 'val']:
                        structure[split_name][class_name] += 1
                        class_names.add(class_name)

        # --- 3. Compile Results & Issues ---
        basic_info = {
            'total_files_extracted': len(file_list),
            'analysis_root': os.path.basename(root_extracted_path) if root_extracted_path != extracted_dir else '(ZIP Root)',
            'detected_splits': sorted(list(structure.keys()))
        }
        full_analysis_results['basic_info'] = basic_info
        log("analysis_result", {"key": "basic_info", "data": basic_info})

        structure_summary = {split: dict(classes) for split, classes in structure.items()}
        full_analysis_results['structure_summary'] = structure_summary
        log("analysis_result", {"key": "structure_summary", "data": structure_summary}) # Emit summary

        file_summary = {'file_types_found': dict(file_types), 'total_files_analyzed': sum(file_types.values())}
        full_analysis_results['file_summary'] = file_summary
        log("analysis_result", {"key": "file_summary", "data": file_summary})

        preview_data = {'file_list_head': preview_files}
        full_analysis_results['preview_data'] = preview_data
        log("analysis_result", {"key": "preview_data", "data": preview_data}) # Emit preview

        class_summary = {"count": len(class_names), "names": sorted(list(class_names))}
        full_analysis_results['class_summary'] = class_summary # Add for completeness
        log("analysis_result", {"key": "class_summary", "data": class_summary})


        # Issues based on structure and files
        if 'train' not in structure:
            issues.append({"severity": "ERROR", "message": "Missing 'train' folder containing class subdirectories."})
        if 'val' not in structure:
            issues.append({"severity": "WARNING", "message": "Missing 'val' (validation) folder. Highly recommended for reliable training."})
        if len(class_names) < 2:
            issues.append({"severity": "ERROR", "message": f"Only found {len(class_names)} class(es). Image classification requires at least 2 classes."})
        if non_image_files:
             issues.append({
                 "severity": "WARNING",
                 "message": f"Found {len(non_image_files)} non-image files.",
                 "details": non_image_files[:10] # Show first 10
             })
        # Check for empty class folders (could be added by iterating structure)


        # --- 4. Final Log, Emit Issues, Save ---
        log("analysis_result", {"key": "issues", "data": issues}) # Emit final issues list
        save_results(full_analysis_results, output_dir)
        log("log", {"message": f"Image ZIP analysis complete. Found {len(issues)} potential issues."})

    except Exception as e:
        error_msg = f"Unexpected error during image ZIP analysis: {e}"
        log("log", {"message": error_msg, "log_type": "ERROR"})
        issues.append({"severity": "CRITICAL", "message": error_msg})
        full_analysis_results['issues'] = issues
        save_results(full_analysis_results, output_dir) # Attempt save
        sys.exit(1)

def save_results(results_dict, output_dir):
    """Saves the full analysis results to analysis_results.json."""
    results_file_path = os.path.join(output_dir, 'analysis_results.json')
    try:
        serializable_results = json.loads(json.dumps(results_dict, default=str))
        with open(results_file_path, 'w') as f:
            json.dump(serializable_results, f, indent=2)
        log("log", {"message": f"Full analysis results saved to {results_file_path}"})
    except Exception as save_err:
         log("log", {"message": f"Error saving analysis results JSON: {save_err}", "log_type": "ERROR"})


# --- Script Entrypoint ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Analyze Image ZIP Data')
    parser.add_argument('--data', required=True, help='Path to input ZIP data file')
    parser.add_argument('--output-dir', required=True, help='Directory to extract data and save results')
    parser.add_argument('--run-id', help='Run ID (optional, for context)')
    args = parser.parse_args()

    analyze_image_zip(args.data, args.output_dir)