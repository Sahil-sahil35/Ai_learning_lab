#!/usr/bin/env python3
"""
Image CNN (ResNet18) training script.
Assumes data is already extracted in output_dir/extracted_data.
Prints progress and metrics as structured JSON logs to stdout.
Saves model, final metrics, and summary.
"""
import argparse
import os
import torch
import torch.nn as nn
from torchvision import transforms, datasets, models
from torch.utils.data import DataLoader
import json
import sys
import time
import datetime # Use datetime for timestamps

# --- JSON Logging ---
def log(message_type, payload):
    """Prints a structured JSON log to stdout."""
    log_entry = {
        "type": message_type,
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        **payload
    }
    print(json.dumps(log_entry, default=str)) # Use default=str for potential numpy/torch types
    sys.stdout.flush()

# --- Training Loop Helpers ---
def train_one_epoch(model, loader, opt, loss_fn, device, epoch, total_epochs):
    model.train()
    total_loss, total_correct, total_samples = 0.0, 0, 0
    num_batches = len(loader)

    for i, (xb, yb) in enumerate(loader):
        batch_start_time = time.time()
        xb, yb = xb.to(device), yb.to(device)
        opt.zero_grad()
        preds = model(xb)
        loss = loss_fn(preds, yb)
        loss.backward()
        opt.step()

        total_loss += loss.item() * xb.size(0)
        total_correct += (preds.argmax(1) == yb).sum().item()
        total_samples += xb.size(0)

        # Log progress periodically (e.g., every 10% or every 20 batches)
        log_interval = max(1, num_batches // 10)
        if (i + 1) % log_interval == 0 or (i + 1) == num_batches:
             log("progress", {
                 "current_step": epoch,
                 "total_steps": total_epochs,
                 "step_name": "Epoch",
                 "batch": i + 1,
                 "total_batches": num_batches,
                 "batch_time_ms": round((time.time() - batch_start_time) * 1000) # Optional batch timing
             })

    return total_loss / total_samples, total_correct / total_samples

def eval_one_epoch(model, loader, loss_fn, device):
    model.eval()
    total_loss, total_correct, total_samples = 0.0, 0, 0
    if not loader: # Handle case where validation set is missing
         return 0.0, 0.0

    with torch.no_grad():
        for xb, yb in loader:
            xb, yb = xb.to(device), yb.to(device)
            preds = model(xb)
            loss = loss_fn(preds, yb)
            total_loss += loss.item() * xb.size(0)
            total_correct += (preds.argmax(1) == yb).sum().item()
            total_samples += xb.size(0)

    # Avoid division by zero if loader was empty (shouldn't happen if val_dir exists)
    if total_samples == 0: return 0.0, 0.0
    return total_loss / total_samples, total_correct / total_samples

# --- Main Training Function ---
def train_cnn(args):
    start_time = time.time()
    log("log", {"message": "Image CNN (ResNet18) training script started."})
    os.makedirs(args.output_dir, exist_ok=True)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    log("log", {"message": f"Using device: {device}"})

    training_history = []
    final_metrics_summary = {}

    try:
        # --- 1. Load Data (from extracted location) ---
        data_dir = os.path.join(args.output_dir, "extracted_data")
        # --- Adjust root if single top-level folder exists ---
        if os.path.exists(data_dir) and len(os.listdir(data_dir)) == 1 and os.path.isdir(os.path.join(data_dir, os.listdir(data_dir)[0])):
             data_dir = os.path.join(data_dir, os.listdir(data_dir)[0])
             log("log", {"message": f"Adjusted data root to single folder within extracted_data: {os.path.basename(data_dir)}"})
        # --- End adjustment ---

        train_dir = os.path.join(data_dir, "train")
        val_dir = os.path.join(data_dir, "val")

        if not os.path.exists(train_dir):
            raise FileNotFoundError("Critical: 'train' directory not found inside extracted data.")
        if not os.path.exists(val_dir):
            log("log", {"message": "Warning: 'val' directory not found. Validation metrics will be zero.", "log_type": "WARNING"})
            val_dir = None # Set to None if missing

        # Define transforms
        train_tf = transforms.Compose([
            transforms.RandomResizedCrop(224, scale=(0.8, 1.0)), # Adjusted scale slightly
            transforms.RandomHorizontalFlip(),
            transforms.ColorJitter(brightness=0.2, contrast=0.2), # Added augmentation
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ])
        val_tf = transforms.Compose([
            transforms.Resize(256),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ])

        # Create datasets and dataloaders
        train_ds = datasets.ImageFolder(train_dir, transform=train_tf)
        # Use more workers if CPU allows, num_workers=0 for debugging
        num_workers = min(4, os.cpu_count() // 2) if os.cpu_count() else 0
        train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True, num_workers=num_workers, pin_memory=True if device=='cuda' else False)

        val_loader = None
        val_ds = None
        if val_dir:
            try:
                val_ds = datasets.ImageFolder(val_dir, transform=val_tf)
                val_loader = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False, num_workers=num_workers, pin_memory=True if device=='cuda' else False)
            except FileNotFoundError: # Handle case where val exists but is empty/invalid
                 log("log", {"message": "Warning: 'val' directory exists but is empty or invalid. Skipping validation.", "log_type": "WARNING"})
                 val_dir = None # Treat as missing

        num_classes = len(train_ds.classes)
        if num_classes < 2:
             raise ValueError("Training requires at least 2 classes in the 'train' directory.")
        log("log", {"message": f"Found {num_classes} classes: {', '.join(train_ds.classes)}"})
        log("log", {"message": f"Train samples: {len(train_ds)}, Val samples: {len(val_ds) if val_ds else 0}"})

        # --- 2. Build Model ---
        log("log", {"message": "Initializing ResNet18 model..."})
        model = models.resnet18(weights='ResNet18_Weights.DEFAULT')
        num_ftrs = model.fc.in_features
        model.fc = nn.Linear(num_ftrs, num_classes)
        model = model.to(device)

        # Optimizer and Loss
        opt = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=0.01) # Use AdamW
        loss_fn = nn.CrossEntropyLoss()

        # Learning rate scheduler (optional but recommended)
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(opt, mode='max', factor=0.1, patience=3, verbose=True)

        # --- 3. Training Loop ---
        best_acc = 0.0
        epochs_without_improvement = 0
        early_stopping_patience = 5 # Stop if val_acc doesn't improve for 5 epochs

        log("log", {"message": f"Starting training for {args.n_estimators} epochs..."})
        for epoch in range(1, args.n_estimators + 1):
            epoch_start_time = time.time()
            log("log", {"message": f"--- Epoch {epoch}/{args.n_estimators} ---"})

            tr_loss, tr_acc = train_one_epoch(model, train_loader, opt, loss_fn, device, epoch, args.n_estimators)
            val_loss, val_acc = eval_one_epoch(model, val_loader, loss_fn, device)

            epoch_time = time.time() - epoch_start_time

            metrics_entry = {
                "epoch": epoch,
                "total_epochs": args.n_estimators,
                "train_loss": round(tr_loss, 5),
                "train_accuracy": round(tr_acc, 5),
                "val_loss": round(val_loss, 5),
                "val_accuracy": round(val_acc, 5),
                "epoch_time_s": round(epoch_time, 1)
            }
            log("metric", metrics_entry) # Log metrics every epoch
            training_history.append(metrics_entry)

            # Update final metrics summary with latest validation metrics
            final_metrics_summary = {
                "accuracy": round(val_acc, 5), # Use val_accuracy as primary metric
                "final_val_loss": round(val_loss, 5),
                "final_train_loss": round(tr_loss, 5) # Include train loss for reference
            }

            # Learning rate scheduler step
            if val_loader: scheduler.step(val_acc)

            # Checkpoint saving and Early Stopping
            if val_acc > best_acc:
                best_acc = val_acc
                torch.save(model.state_dict(), os.path.join(args.output_dir, "model.pth"))
                log("log", {"message": f"Epoch {epoch}: New best model saved! Validation Accuracy: {best_acc:.4f}"})
                epochs_without_improvement = 0
            else:
                epochs_without_improvement += 1
                log("log", {"message": f"Epoch {epoch}: No improvement in validation accuracy for {epochs_without_improvement} epoch(s)."})
                if val_loader and epochs_without_improvement >= early_stopping_patience:
                     log("log", {"message": f"Early stopping triggered after {epoch} epochs.", "log_type": "WARNING"})
                     break # Exit training loop


        log("log", {"message": "Training loop finished."})

        # --- 4. Final Artifacts ---
        log("log", {"message": "Saving final artifacts..."})

        # History
        history_path = os.path.join(args.output_dir, 'training_history.json')
        with open(history_path, 'w') as f: json.dump(training_history, f, indent=2)

        # Final Metrics (using the best recorded accuracy)
        final_metrics_summary['best_val_accuracy'] = round(best_acc, 5) # Add best accuracy explicitly
        final_metrics_path = os.path.join(args.output_dir, 'final_metrics.json')
        with open(final_metrics_path, 'w') as f: json.dump(final_metrics_summary, f, indent=2)
        log("log", {"message": f"Final metrics saved: {final_metrics_summary}"})

        # Summary
        summary = {
            "model_type": "Image CNN (ResNet18)",
            "task": "Image Classification",
            "final_metrics_summary": final_metrics_summary,
            "training_time_seconds": round(time.time() - start_time, 2),
            "training_epochs_completed": epoch, # Record actual epochs run
            "num_classes": num_classes,
            "classes": train_ds.classes,
        }
        summary_path = os.path.join(args.output_dir, 'educational_summary.json')
        with open(summary_path, 'w') as f: json.dump(summary, f, indent=2)
        log("log", {"message": "Educational summary saved."})

    except Exception as e:
        error_msg = f"Critical training error: {e}"
        log("log", {"message": error_msg, "log_type": "ERROR"})
        print(f"ERROR: {error_msg}", file=sys.stderr) # Also print to stderr
        sys.exit(1)


# --- Script Entrypoint ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Image CNN Training Script')
    # Standard args (data path is not used directly, only output_dir)
    parser.add_argument('--data', required=True, help='Path to original data file (zip) - used for context, not loading.')
    parser.add_argument('--output-dir', required=True, help='Directory containing extracted data and to save results')
    parser.add_argument('--run-id', required=True, help='Run ID for logging context')

    # Model-specific args from config.json (names must match)
    parser.add_argument('--n_estimators', type=int, default=10, help='Number of Epochs') # Name comes from config
    parser.add_argument('--batch_size', type=int, default=32, help='Batch size for training')
    parser.add_argument('--learning_rate', type=float, default=0.001, help='Learning rate for optimizer')
    # Add other hyperparameters if defined in config.json

    args = parser.parse_args()

    train_cnn(args)