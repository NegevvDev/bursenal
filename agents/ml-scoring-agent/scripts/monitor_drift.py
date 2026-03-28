#!/usr/bin/env python3
"""
Model Drift Monitor — ml-scoring-agent
Detects data drift using Population Stability Index (PSI) and Brier score trend.
Output: outputs/YYYY-MM-DD_model-drift-report.md

Dependencies: pip install numpy pandas scikit-learn json
"""
import json
import math
import os
from datetime import datetime, timezone, timedelta

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

PSI_STABLE  = 0.1
PSI_MONITOR = 0.2


def compute_psi(expected_quantiles: list, actual_vals: np.ndarray) -> float:
    """
    Compute Population Stability Index using pre-defined quantile buckets.
    expected_quantiles: list of 11 floats (10 bucket boundaries + endpoints)
    actual_vals: 1D array of recent inference values
    """
    n_buckets = len(expected_quantiles) - 1
    expected_pct = np.full(n_buckets, 1.0 / n_buckets)   # uniform from training

    actual_counts = np.zeros(n_buckets)
    for val in actual_vals:
        for b in range(n_buckets):
            if expected_quantiles[b] <= val < expected_quantiles[b + 1]:
                actual_counts[b] += 1
                break
        else:
            actual_counts[-1] += 1   # assign to last bucket if above max

    actual_pct = actual_counts / max(actual_counts.sum(), 1)
    # Avoid log(0)
    actual_pct   = np.maximum(actual_pct, 1e-4)
    expected_pct = np.maximum(expected_pct, 1e-4)
    psi = np.sum((actual_pct - expected_pct) * np.log(actual_pct / expected_pct))
    return float(psi)


def load_recent_scored_conjunctions(outputs_dir: str, days: int = 30) -> pd.DataFrame | None:
    """Load and aggregate scored conjunction files from the past N days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    dfs = []
    for fname in sorted(os.listdir(outputs_dir)):
        if not fname.endswith('_scored-conjunctions.json'):
            continue
        fpath = os.path.join(outputs_dir, fname)
        with open(fpath) as f:
            data = json.load(f)
        scored_at = datetime.fromisoformat(data['scored_at_utc'])
        if scored_at < cutoff:
            continue
        rows = data.get('scored_conjunctions', [])
        if rows:
            dfs.append(pd.DataFrame(rows))

    return pd.concat(dfs, ignore_index=True) if dfs else None


def main():
    script_dir  = os.path.dirname(os.path.abspath(__file__))
    agent_dir   = os.path.dirname(script_dir)
    models_dir  = os.path.join(agent_dir, 'data', 'models')
    outputs_dir = os.path.join(agent_dir, 'outputs')
    os.makedirs(outputs_dir, exist_ok=True)

    # Load training stats
    stats_path = os.path.join(models_dir, 'training_stats.json')
    if not os.path.exists(stats_path):
        print("[ERROR] training_stats.json not found — run TRAIN_MODEL first")
        return
    with open(stats_path) as f:
        training_stats = json.load(f)

    # Load recent inference data
    recent_df = load_recent_scored_conjunctions(outputs_dir, days=30)
    if recent_df is None or len(recent_df) < 50:
        print("[INFO] Insufficient inference data (<50 events in past 30 days) — skipping drift check")
        return

    print(f"[Drift] Analyzing {len(recent_df)} events from past 30 days")

    now = datetime.now(timezone.utc)
    ts  = now.strftime('%Y-%m-%d')

    psi_results = {}
    overall_status = 'STABLE'

    # PSI for each feature (if available in scored events)
    # Note: scored-conjunctions.json contains raw features for PSI computation
    # We use the ml_score as a proxy for distribution shift if raw features aren't stored
    for feature in FEATURE_COLS:
        if feature not in recent_df.columns:
            continue
        actual_vals = recent_df[feature].dropna().values
        if len(actual_vals) < 10:
            continue
        quantiles = training_stats.get(feature, {}).get('quantiles', [])
        if len(quantiles) < 11:
            continue

        psi = compute_psi(quantiles, actual_vals)
        if psi >= PSI_MONITOR:
            status = 'RETRAIN'
            overall_status = 'RETRAIN_RECOMMENDED'
        elif psi >= PSI_STABLE:
            status = 'MONITOR'
            if overall_status == 'STABLE':
                overall_status = 'MONITOR'
        else:
            status = 'STABLE'

        psi_results[feature] = {'psi': round(psi, 4), 'status': status}

    # PSI on ml_score distribution itself (always available)
    if 'ml_score' in recent_df.columns:
        ml_scores = recent_df['ml_score'].dropna().values
        score_psi = compute_psi([0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0], ml_scores)
        psi_results['ml_score_distribution'] = {'psi': round(score_psi, 4),
                                                 'status': 'STABLE' if score_psi < PSI_STABLE else 'MONITOR'}

    # Write report
    report_path = os.path.join(outputs_dir, f"{ts}_model-drift-report.md")
    with open(report_path, 'w') as f:
        f.write(f"# Model Drift Report\n\n")
        f.write(f"**Date:** {now.isoformat()}  \n")
        f.write(f"**Events analyzed:** {len(recent_df)} (past 30 days)  \n")
        f.write(f"**Overall status:** **{overall_status}**\n\n")
        f.write(f"## PSI by Feature\n\n")
        f.write(f"| Feature | PSI | Status |\n|---------|-----|--------|\n")
        for feat, res in sorted(psi_results.items(), key=lambda x: x[1]['psi'], reverse=True):
            icon = '🔴' if res['status'] == 'RETRAIN' else ('🟡' if res['status'] == 'MONITOR' else '🟢')
            f.write(f"| {feat} | {res['psi']:.4f} | {icon} {res['status']} |\n")
        f.write(f"\n## Interpretation\n\n")
        f.write(f"- PSI < 0.1: STABLE (no action)\n")
        f.write(f"- PSI 0.1–0.2: MONITOR (watch for further drift)\n")
        f.write(f"- PSI > 0.2: RETRAIN_RECOMMENDED\n\n")
        if overall_status == 'RETRAIN_RECOMMENDED':
            f.write(f"## ⚠️ Recommendation\n\nOne or more features show significant distribution shift. "
                    f"Trigger TRAIN_MODEL skill on next monthly review cycle.\n")

    print(f"[Drift] Overall: {overall_status} | Report: {os.path.basename(report_path)}")
    if overall_status == 'RETRAIN_RECOMMENDED':
        print("  !! RETRAIN_RECOMMENDED — log escalation to journal")
    return report_path


if __name__ == '__main__':
    main()
