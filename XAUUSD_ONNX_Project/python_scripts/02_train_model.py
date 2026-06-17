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
    'volume_ratio'
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


def main():
    # 1. Load and Split Data
    df = load_data()
    X_train, y_train, X_val, y_val, X_test, y_test = split_data(df)
    
    # 2. Define Model Pipeline
    # StandardScaler + RandomForestClassifier
    # Limit max_depth to prevent overfitting and limit complexity of trees in ONNX
    pipeline = Pipeline([
        ('scaler', StandardScaler()),
        ('classifier', RandomForestClassifier(
            n_estimators=150,
            max_depth=6,
            min_samples_leaf=15,
            class_weight='balanced',
            random_state=42,
            n_jobs=-1
        ))
    ])
    
    # 3. Train the Model
    print("\nTraining RandomForest Pipeline (Scaling + Classifier)...")
    pipeline.fit(X_train, y_train)
    print("Training completed.")
    
    # 4. Evaluate on Train, Val, and Test Splits
    y_train_pred = pipeline.predict(X_train)
    evaluate_model(y_train, y_train_pred, "Train")
    
    y_val_pred = pipeline.predict(X_val)
    evaluate_model(y_val, y_val_pred, "Validation")
    
    y_test_pred = pipeline.predict(X_test)
    evaluate_model(y_test, y_test_pred, "Test")
    
    # 5. Export to ONNX
    convert_to_onnx(pipeline, X_train)
    
    print("\nPhase 2 execution finished.")


if __name__ == "__main__":
    main()
