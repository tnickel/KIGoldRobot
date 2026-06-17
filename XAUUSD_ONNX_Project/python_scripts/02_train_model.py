#!/usr/bin/env python3
"""
Phase 2: Machine Learning & ONNX Export (02_train_model.py)
----------------------------------------------------------
This script loads the volatility-normalized feature dataset, splits it chronologically
into Train (70%), Validation (15%), and Test (15%) splits, trains a scikit-learn
Pipeline (StandardScaler + RandomForestClassifier), evaluates model performance (focusing
on Precision and F1-score), and exports the entire pipeline to an ONNX model.

Crucial:
- Chronological splitting is used to avoid time-series data leakage.
- ZipMap is disabled during ONNX export to output clean tensors for MT5.
"""

import os
import sys
import json
import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, accuracy_score, confusion_matrix

# ONNX Conversion Imports
from skl2onnx import convert_sklearn
from skl2onnx.common.data_types import FloatTensorType

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, "data", "xauusd_features.csv")
MODEL_OUT_PATH = os.path.join(BASE_DIR, "mql5_ea", "model.onnx")

# Features to use for training
FEATURE_COLS = [
    'atr',
    'rsi',
    'dist_ema20',
    'dist_ema50',
    'dist_sma200',
    'macd_diff_norm',
    'body_size_norm',
    'upper_shadow_norm',
    'lower_shadow_norm',
    'tick_volume_ratio',
    'dxy_dist_ema20',
    'vix_close',
    'sin_hour',
    'cos_hour',
    'sin_day',
    'cos_day'
]
TARGET_COL = 'target'



def load_data():
    """Loads and checks the engineered features dataset."""
    if not os.path.exists(DATA_PATH):
        print(f"Error: Features file not found at {DATA_PATH}.")
        print("Please run '01_data_fetch.py' first to generate features.")
        sys.exit(1)
        
    df = pd.read_csv(DATA_PATH)
    # Convert 'time' back if index is not set
    if 'time' in df.columns:
        df.set_index('time', inplace=True)
    elif df.index.name != 'time' and 'time' in df.index.names:
        pass # Already index
        
    print(f"Loaded dataset: {df.shape[0]} rows, {df.shape[1]} columns.")
    return df


def split_data(df):
    """Splits data chronologically into Train (70%), Val (15%), and Test (15%)."""
    n = len(df)
    train_end = int(n * 0.70)
    val_end = int(n * 0.85)
    
    # Chronological Split
    train_df = df.iloc[:train_end]
    val_df = df.iloc[train_end:val_end]
    test_df = df.iloc[val_end:]
    
    X_train, y_train = train_df[FEATURE_COLS], train_df[TARGET_COL]
    X_val, y_val = val_df[FEATURE_COLS], val_df[TARGET_COL]
    X_test, y_test = test_df[FEATURE_COLS], test_df[TARGET_COL]
    
    print(f"\nChronological Split Summary:")
    print(f"  Train set      : {X_train.shape[0]} rows ({train_df.index[0]} to {train_df.index[-1]})")
    print(f"  Validation set : {X_val.shape[0]} rows ({val_df.index[0]} to {val_df.index[-1]})")
    print(f"  Test set       : {X_test.shape[0]} rows ({test_df.index[0]} to {test_df.index[-1]})")
    
    return X_train, y_train, X_val, y_val, X_test, y_test


def evaluate_model(y_true, y_pred, label):
    """Prints evaluation metrics including Precision, Recall, F1, and Accuracy."""
    print(f"\n================= {label} Evaluation =================")
    print("Classification Report:")
    print(classification_report(y_true, y_pred, zero_division=0))
    print(f"Accuracy: {accuracy_score(y_true, y_pred):.4f}")
    
    # Print Confusion Matrix
    print("Confusion Matrix:")
    cm = confusion_matrix(y_true, y_pred, labels=[-1, 0, 1])
    print("      Pred:-1 Pred:0  Pred:1")
    print(f"Act:-1  {cm[0][0]:6d}  {cm[0][1]:6d}  {cm[0][2]:6d}")
    print(f"Act:0   {cm[1][0]:6d}  {cm[1][1]:6d}  {cm[1][2]:6d}")
    print(f"Act:1   {cm[2][0]:6d}  {cm[2][1]:6d}  {cm[2][2]:6d}")


def convert_to_onnx(pipeline, X_sample):
    """
    Converts the trained pipeline into ONNX format.
    Disables ZipMap to ensure outputs are raw tensors, compatible with MT5.
    """
    print(f"\nConverting model to ONNX format...")
    
    # Input definition: Float float_input [BatchSize, NumFeatures]
    initial_type = [('float_input', FloatTensorType([None, len(FEATURE_COLS)]))]
    
    # CRITICAL: Disable ZipMap to avoid a list-of-maps output.
    # Disabling ZipMap changes the probabilities output from a list of dicts to a flat float matrix [BatchSize, NumClasses]
    # This is required for MT5 to read probabilities directly.
    options = {id(pipeline): {'zipmap': False}}
    
    onnx_model = convert_sklearn(
        pipeline,
        name="XAUUSD_H1_RF_Pipeline",
        initial_types=initial_type,
        options=options,
        target_opset=13
    )
    
    # Save the model
    os.makedirs(os.path.dirname(MODEL_OUT_PATH), exist_ok=True)
    with open(MODEL_OUT_PATH, "wb") as f:
        f.write(onnx_model.SerializeToString())
        
    print(f"ONNX model saved successfully to: {MODEL_OUT_PATH}")
    
    # Inspect ONNX model features
    print("\nONNX Model Tensor Mapping for MQL5:")
    print("  Inputs:")
    for input_tensor in onnx_model.graph.input:
        shape = [dim.dim_value if dim.dim_value > 0 else 'None' for dim in input_tensor.type.tensor_type.shape.dim]
        print(f"    - Name: '{input_tensor.name}', Type: FLOAT, Shape: {shape}")
    print("  Outputs:")
    for idx, output_tensor in enumerate(onnx_model.graph.output):
        shape = [dim.dim_value if dim.dim_value > 0 else 'None' for dim in output_tensor.type.tensor_type.shape.dim]
        type_str = "INT64 (Class Labels)" if idx == 0 else "FLOAT (Class Probabilities: [Sell(-1), Hold(0), Buy(1)])"
        print(f"    - Name: '{output_tensor.name}', Type: {type_str}, Shape: {shape}")


def print_forest_summary(pipeline, elapsed_time):
    """Prints Random Forest structure and feature importances to console in a beautiful format."""
    classifier = pipeline.named_steps['classifier']
    total_nodes = sum(e.tree_.node_count for e in classifier.estimators_)
    avg_nodes = total_nodes / len(classifier.estimators_)
    max_depth = max(e.tree_.max_depth for e in classifier.estimators_)
    avg_depth = sum(e.tree_.max_depth for e in classifier.estimators_) / len(classifier.estimators_)
    
    print("\n" + "="*70)
    print("      RANDOM FOREST MODEL STRUCTURE & PARAMETERS")
    print("="*70)
    print(f"  Ensemble Algorithm  : Random Forest Classifier")
    print(f"  Number of Trees     : {classifier.n_estimators}")
    print(f"  Max Depth Limit     : {classifier.max_depth}")
    print(f"  Min Samples Leaf    : {classifier.min_samples_leaf}")
    print(f"  Class Weight        : {classifier.class_weight}")
    print(f"  Training Duration   : {elapsed_time:.4f} seconds")
    print("-"*70)
    print(f"  Total Decision Nodes: {total_nodes:,}")
    print(f"  Avg Nodes per Tree  : {avg_nodes:.1f}")
    print(f"  Max Actual Depth    : {max_depth}")
    print(f"  Avg Tree Depth      : {avg_depth:.1f}")
    print("="*70)
    
    # Extract feature importances
    importances = classifier.feature_importances_
    feat_imp = []
    for name, imp in zip(FEATURE_COLS, importances):
        feat_imp.append((name, imp))
    feat_imp.sort(key=lambda x: x[1], reverse=True)
    
    print("\n" + "="*70)
    print("             RANKED FEATURE IMPORTANCES")
    print("="*70)
    print(f"  {'Rank':<4} | {'Feature Name':<20} | {'Importance':<10} | {'Visual Distribution'}")
    print("-"*70)
    
    max_imp = feat_imp[0][1] if feat_imp else 1.0
    for idx, (name, imp) in enumerate(feat_imp):
        percentage = imp * 100
        # Build text-based bar (width 24 chars) using safe ASCII characters
        bar_width = int((imp / max_imp) * 24) if max_imp > 0 else 0
        bar = "=" * bar_width + "." * (24 - bar_width)
        print(f"  #{idx+1:02d} | {name:<20} | {percentage:>9.2f}% | {bar}")
    print("="*70 + "\n")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Phase 2: Machine Learning & ONNX Export")
    parser.add_argument("--n-estimators", type=int, default=150, help="Number of trees in forest")
    parser.add_argument("--max-depth", type=int, default=6, help="Max depth limit of trees")
    parser.add_argument("--min-samples-leaf", type=int, default=15, help="Min samples leaf")
    parser.add_argument("--class-weight", type=str, default="balanced", help="Class weight mode (balanced or none)")
    args, unknown = parser.parse_known_args() # Use parse_known_args to ignore GUI-specific arguments if called from GUI
    
    class_weight = None if args.class_weight.lower() == "none" else args.class_weight
    
    print(f"\nTraining model with parameters:")
    print(f"  n_estimators      : {args.n_estimators}")
    print(f"  max_depth         : {args.max_depth}")
    print(f"  min_samples_leaf  : {args.min_samples_leaf}")
    print(f"  class_weight      : {class_weight}")
    
    # 1. Load and Split Data
    df = load_data()
    X_train, y_train, X_val, y_val, X_test, y_test = split_data(df)
    
    # 2. Define Model Pipeline
    # StandardScaler + RandomForestClassifier
    # Limit max_depth to prevent overfitting and limit complexity of trees in ONNX
    pipeline = Pipeline([
        ('scaler', StandardScaler()),
        ('classifier', RandomForestClassifier(
            n_estimators=args.n_estimators,
            max_depth=args.max_depth,
            min_samples_leaf=args.min_samples_leaf,
            class_weight=class_weight,
            random_state=42,
            n_jobs=-1
        ))
    ])
    
    # 3. Train the Model
    print("\nTraining RandomForest Pipeline (Scaling + Classifier)...")
    import time
    start_time = time.time()
    pipeline.fit(X_train, y_train)
    elapsed_time = time.time() - start_time
    print(f"Training completed in {elapsed_time:.4f} seconds.")
    
    # 4. Evaluate on Train, Val, and Test Splits
    y_train_pred = pipeline.predict(X_train)
    evaluate_model(y_train, y_train_pred, "Train")
    
    y_val_pred = pipeline.predict(X_val)
    evaluate_model(y_val, y_val_pred, "Validation")
    
    y_test_pred = pipeline.predict(X_test)
    evaluate_model(y_test, y_test_pred, "Test")
    
    # 5. Export to ONNX
    convert_to_onnx(pipeline, X_train)
    
    # 5b. Print summary
    print_forest_summary(pipeline, elapsed_time)
    
    # 6. Save JSON Metrics for GUI
    save_metrics_json(pipeline, elapsed_time, df, X_train, y_train, y_train_pred, X_val, y_val, y_val_pred, X_test, y_test, y_test_pred)

    
    print("\nPhase 2 execution finished.")




def save_metrics_json(pipeline, elapsed_time, df, X_train, y_train, y_train_pred, X_val, y_val, y_val_pred, X_test, y_test, y_test_pred):
    """Saves all evaluation metrics to data/model_metrics.json for GUI visualization."""
    metrics_path = os.path.join(BASE_DIR, "data", "model_metrics.json")
    print(f"\nSaving metrics JSON to {metrics_path}...")
    
    # Extract structural details of Random Forest
    classifier = pipeline.named_steps['classifier']
    total_nodes = int(sum(e.tree_.node_count for e in classifier.estimators_))
    avg_nodes_per_tree = float(total_nodes / len(classifier.estimators_))
    max_actual_depth = int(max(e.tree_.max_depth for e in classifier.estimators_))
    avg_actual_depth = float(sum(e.tree_.max_depth for e in classifier.estimators_) / len(classifier.estimators_))
    
    # Extract feature importances
    importances = classifier.feature_importances_
    feat_imp = []
    for name, imp in zip(FEATURE_COLS, importances):
        feat_imp.append({
            "name": name,
            "importance": float(imp)
        })
    feat_imp.sort(key=lambda x: x["importance"], reverse=True)
    
    onnx_size_bytes = 0
    if os.path.exists(MODEL_OUT_PATH):
        onnx_size_bytes = os.path.getsize(MODEL_OUT_PATH)
        
    metrics = {
        "algorithm": {
            "name": "Random Forest",
            "parameters": {
                "n_estimators": 150,
                "max_depth": 6,
                "min_samples_leaf": 15,
                "class_weight": "balanced"
            },
            "training_time_seconds": float(elapsed_time)
        },
        "feature_importances": feat_imp,

        "forest_details": {
            "n_estimators": int(classifier.n_estimators),
            "max_depth_limit": int(classifier.max_depth) if classifier.max_depth else None,
            "total_nodes": total_nodes,
            "avg_nodes_per_tree": avg_nodes_per_tree,
            "max_actual_depth": max_actual_depth,
            "avg_actual_depth": avg_actual_depth,
            "onnx_size_bytes": onnx_size_bytes
        },
        "dataset_size": {
            "total": int(len(df)),
            "train": int(len(X_train)),
            "val": int(len(X_val)),
            "test": int(len(X_test))
        },
        "feature_count": len(FEATURE_COLS),
        "features": FEATURE_COLS,
        "accuracies": {
            "train": float(accuracy_score(y_train, y_train_pred)),
            "val": float(accuracy_score(y_val, y_val_pred)),
            "test": float(accuracy_score(y_test, y_test_pred))
        },
        "classification_reports": {
            "train": classification_report(y_train, y_train_pred, zero_division=0, output_dict=True),
            "val": classification_report(y_val, y_val_pred, zero_division=0, output_dict=True),
            "test": classification_report(y_test, y_test_pred, zero_division=0, output_dict=True)
        },
        "confusion_matrices": {
            "train": confusion_matrix(y_train, y_train_pred, labels=[-1, 0, 1]).tolist(),
            "val": confusion_matrix(y_val, y_val_pred, labels=[-1, 0, 1]).tolist(),
            "test": confusion_matrix(y_test, y_test_pred, labels=[-1, 0, 1]).tolist()
        }
    }
    
    os.makedirs(os.path.dirname(metrics_path), exist_ok=True)
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
    print("Metrics JSON saved successfully.")


if __name__ == "__main__":
    main()

