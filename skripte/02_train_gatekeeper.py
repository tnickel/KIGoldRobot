import os
import sys
import time
import json
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix, precision_score, accuracy_score
from skl2onnx import convert_sklearn
from skl2onnx.common.data_types import FloatTensorType

def save_metrics_json(clf, train_time, df, X_train, y_train, y_train_pred, X_test, y_test, y_test_pred, feature_cols, onnx_path, repo_dir):
    metrics_path = os.path.join(repo_dir, "data", "model_metrics.json")
    print(f"\nSaving metrics JSON to {metrics_path}...")
    
    total_nodes = int(sum(e.tree_.node_count for e in clf.estimators_))
    avg_nodes_per_tree = float(total_nodes / len(clf.estimators_))
    max_actual_depth = int(max(e.tree_.max_depth for e in clf.estimators_))
    avg_actual_depth = float(sum(e.tree_.max_depth for e in clf.estimators_) / len(clf.estimators_))
    
    importances = clf.feature_importances_
    feat_imp = []
    for name, imp in zip(feature_cols, importances):
        feat_imp.append({
            "name": name,
            "importance": float(imp)
        })
    feat_imp.sort(key=lambda x: x["importance"], reverse=True)
    
    onnx_size_bytes = 0
    if os.path.exists(onnx_path):
        onnx_size_bytes = os.path.getsize(onnx_path)
        
    metrics = {
        "algorithm": {
            "name": "Random Forest Classifier",
            "parameters": {
                "n_estimators": int(clf.n_estimators),
                "max_depth": int(clf.max_depth) if clf.max_depth else None,
                "min_samples_leaf": int(clf.min_samples_leaf) if clf.min_samples_leaf else None,
                "class_weight": "balanced"
            },
            "training_time_seconds": float(train_time)
        },
        "feature_importances": feat_imp,
        "forest_details": {
            "n_estimators": int(clf.n_estimators),
            "max_depth_limit": int(clf.max_depth) if clf.max_depth else None,
            "total_nodes": total_nodes,
            "avg_nodes_per_tree": avg_nodes_per_tree,
            "max_actual_depth": max_actual_depth,
            "avg_actual_depth": avg_actual_depth,
            "onnx_size_bytes": onnx_size_bytes
        },
        "dataset_size": {
            "total": int(len(df)),
            "train": int(len(X_train)),
            "val": 0,
            "test": int(len(X_test))
        },
        "feature_count": len(feature_cols),
        "features": feature_cols,
        "accuracies": {
            "train": float(accuracy_score(y_train, y_train_pred)),
            "val": 0.0,
            "test": float(accuracy_score(y_test, y_test_pred))
        },
        "classification_reports": {
            "train": classification_report(y_train, y_train_pred, zero_division=0, output_dict=True),
            "val": {},
            "test": classification_report(y_test, y_test_pred, zero_division=0, output_dict=True)
        },
        "confusion_matrices": {
            "train": confusion_matrix(y_train, y_train_pred, labels=[0, 1]).tolist(),
            "val": [[0, 0], [0, 0]],
            "test": confusion_matrix(y_test, y_test_pred, labels=[0, 1]).tolist()
        }
    }
    
    os.makedirs(os.path.dirname(metrics_path), exist_ok=True)
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
    print("Metrics JSON saved successfully.")

def main():
    # Resolve ToTheMoonKI paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_dir = os.path.dirname(script_dir)
    data_path = os.path.join(repo_dir, "data", "grid_entries.csv")
    exports_dir = os.path.join(repo_dir, "exports")
    os.makedirs(exports_dir, exist_ok=True)
    
    if not os.path.exists(data_path):
        print(f"Error: Dataset not found at {data_path}. Please run data extraction first.")
        sys.exit(1)
        
    print(f"Loading dataset from {data_path}...")
    df = pd.read_csv(data_path)
    df['time'] = pd.to_datetime(df['time'])
    df.set_index('time', inplace=True)
    
    # Define features and target (49 features total)
    feature_cols = [
        'is_buy', 'dist_ema250_h4', 'rsi_m5', 'rsi_m15', 'rsi_h1',
        'adx_h1', 'efficiency_ratio_h1', 'atr_ratio_m15', 'atr_ratio_h1',
        'spread_points', 'sin_hour', 'cos_hour', 'sin_day', 'cos_day',
        'dist_env_up', 'dist_env_down',
        'macd_h1', 'macd_sig_h1', 'macd_hist_h1', 'stoch_k_m15', 'stoch_d_m15',
        'cci_h1', 'ema50_ema200_dist_h1',
        'vix_close', 'rsi_us500_h1', 'rsi_xauusd_h1',
        'minutes_to_usd_news', 'minutes_to_aud_news',
        'dxy_close', 'rsi_dxy_h1', 'rsi_audjpy_h1', 'rsi_euraud_h1',
        'rsi_gbpaud_h1', 'rsi_usdjpy_h1',
        'is_asian_session', 'is_london_session', 'is_ny_session',
        'consec_bars_m5', 'vol_ratio_m5',
        'rsi_h4', 'rsi_d1', 'dist_sma200_h1', 'dist_sma200_h4',
        'bb_width_h1', 'bb_width_h4', 'dist_bb_upper_h1', 'dist_bb_lower_h1',
        'dist_bb_upper_h4', 'dist_bb_lower_h4'
    ]
    target_col = 'target'
    
    X = df[feature_cols]
    y = df[target_col]
    
    # Chronological Split
    split_date = '2025-01-01'
    X_train = X[X.index < split_date]
    y_train = y[y.index < split_date]
    X_test = X[X.index >= split_date]
    y_test = y[y.index >= split_date]
    
    print(f"Dataset split completed at {split_date}:")
    print(f"  Train samples: {len(X_train)} (Class 1: {sum(y_train == 1)}, Class 0: {sum(y_train == 0)})")
    print(f"  Test samples:  {len(X_test)} (Class 1: {sum(y_test == 1)}, Class 0: {sum(y_test == 0)})")
    
    # Train RandomForestClassifier
    print("Training RandomForestClassifier...")
    clf = RandomForestClassifier(
        n_estimators=100,
        max_depth=6,
        min_samples_leaf=50,
        class_weight='balanced',
        random_state=42,
        n_jobs=-1
    )
    
    t0 = time.time()
    clf.fit(X_train, y_train)
    elapsed_time = time.time() - t0
    print(f"Training completed in {elapsed_time:.2f} seconds.")
    
    # Evaluate model
    print("\nEvaluating model on training set (In-Sample):")
    y_train_pred = clf.predict(X_train)
    print(classification_report(y_train, y_train_pred))
    
    print("Evaluating model on test set (Out-of-Sample):")
    y_test_pred = clf.predict(X_test)
    print(classification_report(y_test, y_test_pred))
    
    # Show feature importances
    importances = clf.feature_importances_
    indices = np.argsort(importances)[::-1]
    print("\nFeature Importances:")
    for f in range(X.shape[1]):
        print(f"{f + 1:2d}. {feature_cols[indices[f]]:25s}: {importances[indices[f]]:.4f}")
        
    # Test high probability threshold (e.g. threshold = 0.65)
    print("\nEvaluating performance with probability threshold Inp_Min_ONNX_Probability = 0.65:")
    y_test_prob = clf.predict_proba(X_test)[:, 1]
    y_test_pred_thresh = (y_test_prob >= 0.65).astype(int)
    
    trades_taken = sum(y_test_pred_thresh == 1)
    if trades_taken > 0:
        precision_thresh = precision_score(y_test, y_test_pred_thresh, pos_label=1)
        print(f"  Trades taken: {trades_taken} out of {len(X_test)} potential triggers ({trades_taken / len(X_test) * 100:.1f}%)")
        print(f"  Class 1 (Safe) Precision at 0.65 threshold: {precision_thresh:.4f}")
    else:
        print("  Warning: No trades taken at 0.65 probability threshold!")
        
    # Export to ONNX
    print("\nExporting model to ONNX...")
    initial_type = [('float_input', FloatTensorType([None, 49]))]
    onnx_path = os.path.join(exports_dir, "gatekeeper.onnx")
    
    try:
        onnx_model = convert_sklearn(
            clf, 
            initial_types=initial_type,
            target_opset=15,
            options={'zipmap': False}
        )
        
        with open(onnx_path, "wb") as f:
            f.write(onnx_model.SerializeToString())
            
        print(f"Model successfully saved to {onnx_path}")
        
        # Verify ONNX model output shapes
        import onnxruntime as ort
        sess = ort.InferenceSession(onnx_path)
        input_name = sess.get_inputs()[0].name
        output_names = [o.name for o in sess.get_outputs()]
        print(f"ONNX Input Name: {input_name}, Input Shape: {sess.get_inputs()[0].shape}")
        print(f"ONNX Outputs: {output_names}")
        for idx, o in enumerate(sess.get_outputs()):
            print(f"  Output {idx} name: {o.name}, Shape: {o.shape}, Type: {o.type}")
            
        # Save metrics to JSON for the GUI
        save_metrics_json(clf, elapsed_time, df, X_train, y_train, y_train_pred, X_test, y_test, y_test_pred, feature_cols, onnx_path, repo_dir)
            
    except Exception as e:
        print(f"Error exporting to ONNX: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
