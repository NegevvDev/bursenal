#!/usr/bin/env python3
"""
Score Conjunctions Script — ml-scoring-agent
Runs ML inference on conjunction feature matrix, produces calibrated risk scores + SHAP explanations.
Output: outputs/YYYY-MM-DD_HHMM_scored-conjunctions.json

Dependencies: pip install scikit-learn joblib shap numpy pandas pyarrow tensorflow
"""
import json
import os
import time
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd

FEATURE_COLS = [
    'miss_distance_km', 'relative_velocity_km_s', 'radial_miss_km',
    'intrack_miss_km', 'crosstrack_miss_km', 'tca_hours_from_now',
    'log10_pc_analytic', 'primary_sma_km', 'primary_eccentricity',
    'primary_inclination_deg', 'primary_raan_deg', 'secondary_sma_km',
    'secondary_eccentricity', 'secondary_inclination_deg', 'secondary_raan_deg',
    'object_type_encoded', 'tca_urgency', 'velocity_miss_product',
    'delta_inclination_deg', 'delta_sma_km', 'orbital_similarity_score',
]

FEATURE_LABELS = {
    'miss_distance_km':       'miss distance',
    'relative_velocity_km_s': 'relative velocity',
    'tca_hours_from_now':     'time to closest approach',
    'log10_pc_analytic':      'analytic collision probability',
    'tca_urgency':            'approach urgency',
    'velocity_miss_product':  'encounter energy',
    'orbital_similarity_score': 'orbital similarity',
    'object_type_encoded':    'debris object type',
    'delta_inclination_deg':  'orbital inclination difference',
    'delta_sma_km':           'orbital altitude difference',
}

ML_TIER_THRESHOLDS = [
    ('RED',    0.80),
    ('ORANGE', 0.50),
    ('YELLOW', 0.15),
    ('GREEN',  0.0),
]

ANALYTIC_TIER_ORDER = {'GREEN': 0, 'YELLOW': 1, 'ORANGE': 2, 'RED': 3}


def ml_score_to_tier(score: float) -> str:
    for tier, threshold in ML_TIER_THRESHOLDS:
        if score >= threshold:
            return tier
    return 'GREEN'


def load_latest_file(directory: str, suffix: str) -> str | None:
    if not os.path.exists(directory):
        return None
    files = sorted([f for f in os.listdir(directory) if f.endswith(suffix)])
    return os.path.join(directory, files[-1]) if files else None


def main():
    script_dir  = os.path.dirname(os.path.abspath(__file__))
    agent_dir   = os.path.dirname(script_dir)
    agents_root = os.path.dirname(agent_dir)
    models_dir  = os.path.join(agent_dir, 'data', 'models')
    outputs_dir = os.path.join(agent_dir, 'outputs')
    os.makedirs(outputs_dir, exist_ok=True)

    # Load manifest — check model is approved
    manifest_path = os.path.join(models_dir, 'model_manifest.json')
    if not os.path.exists(manifest_path):
        print("[WARN] No model manifest — using analytic Pc tiers only")
        use_ml = False
    else:
        with open(manifest_path) as f:
            manifest = json.load(f)
        if manifest.get('status') != 'approved':
            print(f"[WARN] Model status '{manifest.get('status')}' — using analytic Pc tiers only")
            use_ml = False
        else:
            use_ml = True
            print(f"[Model] {manifest['version']} | AUC={manifest['test_auc_roc']:.4f}")

    # Load feature matrix
    features_path = load_latest_file(
        os.path.join(agents_root, 'conjunction-analysis-agent', 'outputs'),
        '_ml-features.parquet'
    )
    if not features_path:
        print("[ERROR] No feature file found")
        return
    df = pd.read_parquet(features_path)
    print(f"[Score] {len(df)} events to score")

    now = datetime.now(timezone.utc)
    ts  = now.strftime('%Y-%m-%d_%H%M')

    if not use_ml or len(df) == 0:
        # Fall back: use analytic tier directly
        records = []
        for _, row in df.iterrows():
            records.append({
                'event_id':          row['event_id'],
                'turkish_satellite': row.get('turkish_norad_id', 0),
                'debris_norad_id':   row.get('debris_norad_id', 0),
                'tca_utc':           row.get('tca_utc', ''),
                'ml_score':          None,
                'analytic_tier':     row.get('severity_tier', 'GREEN'),
                'final_tier':        row.get('severity_tier', 'GREEN'),
                'tier_override':     False,
                'lstm_used':         False,
                'model_version':     'ANALYTIC_ONLY',
                'top_shap_features': [],
            })
        output = {
            'scored_at_utc': now.isoformat(), 'model_version': 'ANALYTIC_ONLY',
            'total_scored': len(records), 'tier_counts': {},
            'tier_overrides': 0, 'scored_conjunctions': records,
        }
        output_path = os.path.join(outputs_dir, f"{ts}_scored-conjunctions.json")
        with open(output_path, 'w') as f:
            json.dump(output, f, indent=2)
        print(f"[Done] Written (analytic-only): {os.path.basename(output_path)}")
        return

    # Load model artifacts
    rf_model = joblib.load(os.path.join(models_dir, 'rf_model.pkl'))
    scaler   = joblib.load(os.path.join(models_dir, 'scaler.pkl'))

    # Apply scaler if not already normalized
    X = df[FEATURE_COLS].fillna(df[FEATURE_COLS].median()).values
    if not df['normalized'].iloc[0]:
        X = scaler.transform(X)

    t_start = time.time()
    rf_proba_all = rf_model.predict_proba(X)
    # P(class=2) = P(RED/ORANGE) — daha keskin sinif ayirimi icin
    rf_proba = rf_proba_all[:, -1] if rf_proba_all.shape[1] > 2 else rf_proba_all[:, 1]

    # LSTM (optional) — lstm_model.h5 (seq_len=5, 21 features, 3 classes)
    lstm_used  = False
    lstm_proba = np.zeros(len(df))
    lstm_path  = os.path.join(models_dir, 'lstm_model.h5')
    if os.path.exists(lstm_path):
        try:
            import tensorflow as tf
            lstm_model = tf.keras.models.load_model(lstm_path)
            # Her event'i seq_len=5 kez tekrarla (tek snapshot -> sequence)
            seq_len   = 5
            n_feat    = len(FEATURE_COLS)
            seq_input = np.tile(X[:, np.newaxis, :], (1, seq_len, 1)).astype(np.float32)
            lstm_out  = lstm_model.predict(seq_input, verbose=0)  # (N, 3)
            # P(class=2) — RED/ORANGE olasılığı
            lstm_proba = lstm_out[:, -1] if lstm_out.shape[1] > 1 else lstm_out.flatten()
            lstm_used  = True
            print(f"[LSTM] Yuklendi: {lstm_path}")
        except Exception as e:
            print(f"[WARN] LSTM inference basarisiz: {e} — sadece RF+XGB")

    final_scores = 0.85 * rf_proba + 0.15 * lstm_proba if lstm_used else rf_proba
    # Probability calibration: RF underestimates high-risk scores (conservative)
    final_scores = np.clip(final_scores * 1.55, 0.0, 1.0)
    inference_ms = (time.time() - t_start) * 1000

    # SHAP explanations
    try:
        import shap
        explainer  = shap.TreeExplainer(rf_model.base_estimator if hasattr(rf_model, 'base_estimator') else rf_model)
        sv = explainer.shap_values(X)
        sv_arr = np.array(sv) if isinstance(sv, list) else sv
        # Normalize to (N, F): mean abs across classes
        if sv_arr.ndim == 3:
            if sv_arr.shape[0] == len(X):   # (N, F, n_classes)
                shap_values = np.abs(sv_arr).mean(axis=2)
            else:                            # (n_classes, N, F)
                shap_values = np.abs(sv_arr).mean(axis=0)
        else:
            shap_values = np.abs(sv_arr)
        shap_available = True
    except Exception as e:
        print(f"[WARN] SHAP computation failed: {e}")
        shap_values   = np.zeros_like(X)
        shap_available = False

    # Build output records
    tier_counts = {'RED': 0, 'ORANGE': 0, 'YELLOW': 0, 'GREEN': 0}
    tier_overrides = 0
    records = []

    for i, row in df.iterrows():
        idx          = df.index.get_loc(i)
        ml_score     = float(final_scores[idx])
        ml_tier      = ml_score_to_tier(ml_score)
        analytic_tier = row.get('severity_tier', 'GREEN')

        # Final tier = ML ile analitik tier'in KÖTÜSÜ (yüksek risk olanı)
        _order = ['GREEN', 'YELLOW', 'ORANGE', 'RED']
        final_tier = _order[max(
            _order.index(ml_tier) if ml_tier in _order else 0,
            _order.index(analytic_tier) if analytic_tier in _order else 0
        )]
        tier_override = final_tier != analytic_tier
        if tier_override:
            tier_overrides += 1

        tier_counts[final_tier] = tier_counts.get(final_tier, 0) + 1

        # Top 3 SHAP features
        top_shap = []
        if shap_available:
            abs_shap = np.abs(shap_values[idx])
            top_idxs = [int(x) for x in np.argsort(abs_shap)[::-1][:3]]
            for fi in top_idxs:
                fname = FEATURE_COLS[fi]
                label = FEATURE_LABELS.get(fname, fname.replace('_', ' '))
                top_shap.append({
                    'feature': fname,
                    'label':   label,
                    'value':   float(X[idx, fi]),
                    'shap':    float(shap_values[idx, fi]),
                })

        records.append({
            'event_id':          row['event_id'],
            'turkish_norad_id':  int(row['turkish_norad_id']),
            'debris_norad_id':   int(row['debris_norad_id']),
            'tca_utc':           row['tca_utc'],
            'miss_distance_km':  float(row.get('miss_distance_km', 0)),
            'relative_velocity_km_s': float(row.get('relative_velocity_km_s', 0)),
            'analytic_tier':     analytic_tier,
            'ml_score':          ml_score,
            'final_tier':        final_tier,
            'tier_override':     tier_override,
            'lstm_used':         lstm_used,
            'model_version':     manifest['version'],
            'top_shap_features': top_shap,
        })

    output = {
        'scored_at_utc':   now.isoformat(),
        'model_version':   manifest['version'],
        'total_scored':    len(records),
        'tier_counts':     tier_counts,
        'tier_overrides':  tier_overrides,
        'inference_ms':    round(inference_ms, 1),
        'lstm_used':       lstm_used,
        'scored_conjunctions': records,
    }

    output_path = os.path.join(outputs_dir, f"{ts}_scored-conjunctions.json")
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"[Done] {len(records)} scored | RED:{tier_counts.get('RED',0)} ORANGE:{tier_counts.get('ORANGE',0)} YELLOW:{tier_counts.get('YELLOW',0)} | {inference_ms:.0f}ms")
    print(f"       Overrides: {tier_overrides} | Written: {os.path.basename(output_path)}")

    for rec in records:
        if rec['final_tier'] == 'RED':
            print(f"  !! RED: NORAD {rec['turkish_norad_id']} × {rec['debris_norad_id']} | TCA {rec['tca_utc']} | ML={rec['ml_score']:.3f}")

    return output_path


if __name__ == '__main__':
    main()
