#!/usr/bin/env python3
"""
Model Training Script — ml-scoring-agent
Trains RF + LSTM ensemble for collision risk scoring.
Outputs: data/models/rf_model.pkl, scaler.pkl, lstm_weights.h5, training_stats.json, model_manifest.json

Dependencies: pip install scikit-learn imbalanced-learn tensorflow numpy pandas pyarrow joblib shap
"""
import json
import math
import os
import time
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score, brier_score_loss, f1_score, precision_recall_curve, auc
from sklearn.model_selection import train_test_split, StratifiedKFold, RandomizedSearchCV
from sklearn.preprocessing import StandardScaler
from imblearn.over_sampling import SMOTE

FEATURE_COLS = [
    'miss_distance_km', 'relative_velocity_km_s', 'radial_miss_km',
    'intrack_miss_km', 'crosstrack_miss_km', 'tca_hours_from_now',
    'log10_pc_analytic', 'primary_sma_km', 'primary_eccentricity',
    'primary_inclination_deg', 'primary_raan_deg', 'secondary_sma_km',
    'secondary_eccentricity', 'secondary_inclination_deg', 'secondary_raan_deg',
    'object_type_encoded', 'tca_urgency', 'velocity_miss_product',
    'delta_inclination_deg', 'delta_sma_km', 'orbital_similarity_score',
]

AUC_THRESHOLD   = 0.92
BRIER_THRESHOLD = 0.05


def load_training_data(data_dir: str) -> tuple[pd.DataFrame, np.ndarray] | None:
    path = os.path.join(data_dir, 'historical_conjunctions.parquet')
    if not os.path.exists(path):
        print(f"[ERROR] Training data not found: {path}")
        print("        Run TRAIN_MODEL skill only after providing historical CDM data.")
        return None
    df = pd.read_parquet(path)
    if 'label' not in df.columns:
        print("[ERROR] Training data missing 'label' column (0=nominal, 1=high-risk)")
        return None
    missing = [c for c in FEATURE_COLS if c not in df.columns]
    if missing:
        print(f"[ERROR] Missing feature columns: {missing}")
        return None
    print(f"[Data] {len(df)} records | {df['label'].sum():.0f} positive ({df['label'].mean()*100:.2f}%)")
    return df


def compute_training_stats(X_train: np.ndarray, feature_cols: list) -> dict:
    """Compute per-feature distribution statistics for drift monitoring."""
    stats = {}
    for i, col in enumerate(feature_cols):
        vals = X_train[:, i]
        quantiles = np.nanpercentile(vals, np.linspace(0, 100, 11)).tolist()
        stats[col] = {
            'mean':      float(np.nanmean(vals)),
            'std':       float(np.nanstd(vals)),
            'min':       float(np.nanmin(vals)),
            'max':       float(np.nanmax(vals)),
            'quantiles': quantiles,  # 10 boundaries for PSI buckets
        }
    return stats


def train_rf(X_train, y_train, X_val, y_val):
    """Train calibrated Random Forest with randomized hyperparameter search."""
    print("[RF] Running RandomizedSearchCV …")
    param_dist = {
        'n_estimators':    [200, 500, 1000],
        'max_features':    ['sqrt', 'log2', 0.3],
        'min_samples_leaf': [1, 5, 10],
        'max_depth':       [None, 20, 50],
    }
    base_rf = RandomForestClassifier(class_weight='balanced', n_jobs=-1, random_state=42)
    search  = RandomizedSearchCV(
        base_rf, param_dist, n_iter=12,
        cv=StratifiedKFold(5, shuffle=True, random_state=42),
        scoring='average_precision', n_jobs=-1, random_state=42, verbose=1,
    )
    search.fit(X_train, y_train)
    best_rf = search.best_estimator_
    print(f"[RF] Best params: {search.best_params_}")

    # Isotonic calibration
    calibrated = CalibratedClassifierCV(best_rf, cv=5, method='isotonic')
    calibrated.fit(X_train, y_train)

    val_proba = calibrated.predict_proba(X_val)[:, 1]
    val_auc   = roc_auc_score(y_val, val_proba)
    print(f"[RF] Val AUC-ROC: {val_auc:.4f}")
    return calibrated, val_auc


def train_lstm(sequences_path: str, y_train: np.ndarray, y_val: np.ndarray) -> tuple | None:
    """Train LSTM on temporal approach sequences if data is available."""
    if not os.path.exists(sequences_path):
        print("[LSTM] No sequence data found — skipping LSTM training")
        return None

    try:
        import tensorflow as tf
        from tensorflow import keras
    except ImportError:
        print("[LSTM] TensorFlow not installed — skipping")
        return None

    data = np.load(sequences_path)
    X_seq = data['sequences']   # expected shape: (N, 6, 3)
    y_seq = data['labels']

    if len(X_seq) != len(y_train):
        print(f"[LSTM] Sequence count mismatch ({len(X_seq)} vs {len(y_train)}) — skipping")
        return None

    split = int(0.85 * len(X_seq))
    X_seq_tr, X_seq_val = X_seq[:split], X_seq[split:]
    y_seq_tr, y_seq_val = y_seq[:split], y_seq[split:]

    pos = int(y_seq_tr.sum()); neg = len(y_seq_tr) - pos
    class_weight = {0: 1.0, 1: neg / max(pos, 1)}

    model = keras.Sequential([
        keras.layers.LSTM(64, input_shape=(6, 3)),
        keras.layers.Dropout(0.2),
        keras.layers.Dense(32, activation='relu'),
        keras.layers.Dense(1, activation='sigmoid'),
    ])
    model.compile(optimizer=keras.optimizers.Adam(1e-3), loss='binary_crossentropy',
                  metrics=[keras.metrics.AUC(name='auc_pr', curve='PR')])

    callbacks = [
        keras.callbacks.EarlyStopping(patience=10, monitor='val_auc_pr',
                                       restore_best_weights=True, mode='max'),
        keras.callbacks.ReduceLROnPlateau(patience=5, factor=0.5, min_lr=1e-5),
    ]
    model.fit(X_seq_tr, y_seq_tr, validation_data=(X_seq_val, y_seq_val),
              epochs=100, batch_size=64, class_weight=class_weight,
              callbacks=callbacks, verbose=1)

    val_proba = model.predict(X_seq_val, verbose=0).flatten()
    val_auc   = roc_auc_score(y_seq_val, val_proba)
    print(f"[LSTM] Val AUC-ROC: {val_auc:.4f}")
    return model, val_auc


def evaluate(model, X_test, y_test, label: str) -> dict:
    """Evaluate a model on the test set."""
    proba = model.predict_proba(X_test)[:, 1]
    auc_roc = roc_auc_score(y_test, proba)
    brier   = brier_score_loss(y_test, proba)

    precision, recall, thresholds = precision_recall_curve(y_test, proba)
    auc_pr = auc(recall, precision)

    # F1-maximizing threshold
    f1_scores = [f1_score(y_test, (proba >= t).astype(int)) for t in thresholds]
    best_t = float(thresholds[np.argmax(f1_scores)])

    # Recall for high-risk events (Pc > 1e-4 proxy: top 10% of scores)
    high_risk_mask = proba >= np.percentile(proba, 90)
    high_risk_recall = float(recall[np.searchsorted(thresholds, np.percentile(proba, 90))])

    print(f"[{label}] AUC-ROC={auc_roc:.4f} | AUC-PR={auc_pr:.4f} | Brier={brier:.4f} | Best-threshold={best_t:.3f}")
    return {'auc_roc': auc_roc, 'brier': brier, 'auc_pr': auc_pr,
            'best_threshold': best_t, 'high_risk_recall': high_risk_recall}


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    agent_dir  = os.path.dirname(script_dir)
    models_dir = os.path.join(agent_dir, 'data', 'models')
    data_dir   = os.path.join(agent_dir, 'data', 'imports', 'training-data')
    outputs_dir = os.path.join(agent_dir, 'outputs')
    os.makedirs(models_dir, exist_ok=True)
    os.makedirs(outputs_dir, exist_ok=True)

    df = load_training_data(data_dir)
    if df is None:
        return

    X = df[FEATURE_COLS].fillna(df[FEATURE_COLS].median()).values
    y = df['label'].values.astype(int)

    # Train/val/test split
    X_tv, X_test, y_tv, y_test = train_test_split(X, y, test_size=0.15, stratify=y, random_state=42)
    X_train, X_val, y_train, y_val = train_test_split(X_tv, y_tv, test_size=0.176, stratify=y_tv, random_state=42)
    # 0.176 ≈ 15% of total

    # Fit scaler on training data
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_val_scaled   = scaler.transform(X_val)
    X_test_scaled  = scaler.transform(X_test)

    # SMOTE oversampling
    smote = SMOTE(sampling_strategy=0.1, random_state=42)
    X_train_resampled, y_train_resampled = smote.fit_resample(X_train_scaled, y_train)
    print(f"[SMOTE] After resampling: {len(X_train_resampled)} samples | {y_train_resampled.sum()} positive")

    # Training stats for drift monitoring
    training_stats = compute_training_stats(X_train_scaled, FEATURE_COLS)

    # Train RF
    rf_model, rf_val_auc = train_rf(X_train_resampled, y_train_resampled, X_val_scaled, y_val)

    # Train LSTM (optional)
    sequences_path = os.path.join(data_dir, 'historical_sequences.npz')
    lstm_result = train_lstm(sequences_path, y_train, y_val)

    # Evaluate on test set
    rf_metrics = evaluate(rf_model, X_test_scaled, y_test, 'RF')

    now = datetime.now(timezone.utc)
    ts  = now.strftime('%Y-%m-%d')

    # Quality gate
    passes = rf_metrics['auc_roc'] >= AUC_THRESHOLD and rf_metrics['brier'] <= BRIER_THRESHOLD
    if not passes:
        print(f"[FAIL] Quality thresholds not met (AUC={rf_metrics['auc_roc']:.4f} need ≥{AUC_THRESHOLD}, Brier={rf_metrics['brier']:.4f} need ≤{BRIER_THRESHOLD})")
        print("       Existing model NOT replaced. Logging failure to journal.")
        report = {'status': 'FAILED', 'metrics': rf_metrics, 'date': now.isoformat()}
        report_path = os.path.join(outputs_dir, f"{ts}_model-training-report.md")
        with open(report_path, 'w') as f:
            f.write(f"# Model Training Report — FAILED\n\n**Date:** {now.isoformat()}\n\n")
            f.write(f"**Status:** Quality thresholds not met\n\n")
            f.write(f"| Metric | Value | Threshold | Pass? |\n|--------|-------|-----------|-------|\n")
            f.write(f"| AUC-ROC | {rf_metrics['auc_roc']:.4f} | ≥{AUC_THRESHOLD} | ❌ |\n")
            f.write(f"| Brier | {rf_metrics['brier']:.4f} | ≤{BRIER_THRESHOLD} | ❌ |\n")
        return

    # Archive existing model artifacts
    archive_dir = os.path.join(models_dir, 'archive')
    os.makedirs(archive_dir, exist_ok=True)
    for fname in ['rf_model.pkl', 'scaler.pkl', 'lstm_weights.h5', 'training_stats.json']:
        src = os.path.join(models_dir, fname)
        if os.path.exists(src):
            import shutil
            shutil.copy2(src, os.path.join(archive_dir, f"{ts}_{fname}"))

    # Save new artifacts
    joblib.dump(rf_model, os.path.join(models_dir, 'rf_model.pkl'))
    joblib.dump(scaler,   os.path.join(models_dir, 'scaler.pkl'))
    with open(os.path.join(models_dir, 'training_stats.json'), 'w') as f:
        json.dump(training_stats, f, indent=2)

    if lstm_result is not None:
        lstm_model, _ = lstm_result
        lstm_model.save_weights(os.path.join(models_dir, 'lstm_weights.h5'))

    # Model manifest — status PENDING_APPROVAL until human approves
    manifest = {
        'version':            ts,
        'training_date':      now.isoformat(),
        'train_set_size':     len(X_train_resampled),
        'test_auc_roc':       rf_metrics['auc_roc'],
        'test_auc_pr':        rf_metrics['auc_pr'],
        'test_brier':         rf_metrics['brier'],
        'test_recall_high_risk': rf_metrics['high_risk_recall'],
        'lstm_included':      lstm_result is not None,
        'status':             'PENDING_APPROVAL',   # human must approve before inference
    }
    with open(os.path.join(models_dir, 'model_manifest.json'), 'w') as f:
        json.dump(manifest, f, indent=2)

    # Write training report
    report_path = os.path.join(outputs_dir, f"{ts}_model-training-report.md")
    with open(report_path, 'w') as f:
        f.write(f"# Model Training Report\n\n")
        f.write(f"**Date:** {now.isoformat()}  \n**Status:** PENDING_APPROVAL\n\n")
        f.write(f"## Test Set Performance\n\n")
        f.write(f"| Metric | Value | Threshold | Pass? |\n|--------|-------|-----------|-------|\n")
        f.write(f"| AUC-ROC | {rf_metrics['auc_roc']:.4f} | ≥{AUC_THRESHOLD} | ✅ |\n")
        f.write(f"| AUC-PR | {rf_metrics['auc_pr']:.4f} | — | — |\n")
        f.write(f"| Brier | {rf_metrics['brier']:.4f} | ≤{BRIER_THRESHOLD} | ✅ |\n")
        f.write(f"| High-Risk Recall | {rf_metrics['high_risk_recall']:.4f} | ≥0.95 | {'✅' if rf_metrics['high_risk_recall'] >= 0.95 else '⚠️'} |\n")
        f.write(f"\n## Model Artifacts\n\n- `rf_model.pkl` — calibrated Random Forest\n")
        f.write(f"- `scaler.pkl` — StandardScaler fitted on training data\n")
        if lstm_result:
            f.write(f"- `lstm_weights.h5` — LSTM approach sequence model\n")
        f.write(f"\n## Action Required\n\n")
        f.write(f"Set `status` to `approved` in `data/models/model_manifest.json` to activate for inference.\n")

    print(f"[Done] Model training complete. AWAITING HUMAN APPROVAL.")
    print(f"       Update data/models/model_manifest.json status to 'approved' to activate.")
    print(f"       Report: {os.path.basename(report_path)}")


if __name__ == '__main__':
    main()
