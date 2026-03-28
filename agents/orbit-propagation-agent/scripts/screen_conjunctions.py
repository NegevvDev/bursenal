#!/usr/bin/env python3
"""
Conjunction Screening Script — orbit-propagation-agent
Identifies candidate object pairs where minimum distance < threshold.
Output: outputs/YYYY-MM-DD_HHMM_conjunction-candidates.json

Dependencies: pip install numpy
"""
import json
import os
from datetime import datetime, timezone

import numpy as np

# ── Screening thresholds ─────────────────────────────────────────────────────
COARSE_THRESHOLD_KM = {
    'LEO': 50.0,
    'GEO': 200.0,
}

TURKISH_NORAD_IDS = {39522, 40985, 47790, 49077, 41875, 38704, 37791, 55491}

# Friendly names for logging
TURKISH_NAMES = {
    39522: "TURKSAT_4A", 40985: "TURKSAT_4B",
    47790: "TURKSAT_5A", 49077: "TURKSAT_5B",
    41875: "GOKTURK_1",  38704: "GOKTURK_2",
    37791: "RASAT",      55491: "IMECE",
}


def load_latest_state_vectors(outputs_dir: str, band: str) -> tuple[dict, np.ndarray, np.ndarray] | tuple[None, None, None]:
    """Load the most recent state vector .npz and sidecar for a given band."""
    files = sorted([f for f in os.listdir(outputs_dir) if f.endswith(f'_state-vectors-{band}.npz')])
    if not files:
        print(f"[WARN] No {band} state vectors found")
        return None, None, None

    npz_path     = os.path.join(outputs_dir, files[-1])
    sidecar_path = npz_path.replace('.npz', '.json')

    data    = np.load(npz_path)
    sidecar = json.load(open(sidecar_path)) if os.path.exists(sidecar_path) else {}

    return sidecar, data['positions'], data['norad_ids']


def screen_band(positions: np.ndarray, norad_ids: np.ndarray,
                band: str, threshold_km: float) -> list[dict]:
    """
    Vectorized screening: for each Turkish satellite vs all others in the band,
    find minimum distance across the 72h window.

    positions: (N, T, 3) float32 array in ECI km
    norad_ids: (N,) int32 array
    Returns list of candidate pair dicts.
    """
    norad_list = norad_ids.tolist()
    turkish_indices = [
        i for i, nid in enumerate(norad_list) if nid in TURKISH_NORAD_IDS
    ]

    if not turkish_indices:
        print(f"[{band}] No Turkish satellites found in state vector array")
        return []

    candidates = []

    for t_idx in turkish_indices:
        t_norad = norad_list[t_idx]
        t_pos   = positions[t_idx]  # (T, 3)

        # Compute distances to all objects at every time step
        # diff shape: (N, T, 3)
        diff = positions - t_pos[np.newaxis, :, :]           # broadcast
        dist = np.linalg.norm(diff, axis=2)                  # (N, T)

        # Minimum distance across the time window for each object
        min_dist      = np.min(dist, axis=1)                  # (N,)
        min_step_idx  = np.argmin(dist, axis=1)               # (N,)

        # Filter: below threshold, not self
        mask = (min_dist < threshold_km) & (np.arange(len(norad_list)) != t_idx)
        candidate_indices = np.where(mask)[0]

        for c_idx in candidate_indices:
            d_norad = norad_list[c_idx]
            candidates.append({
                'turkish_norad_id':    t_norad,
                'turkish_name':        TURKISH_NAMES.get(t_norad, str(t_norad)),
                'debris_norad_id':     d_norad,
                'coarse_min_dist_km':  float(min_dist[c_idx]),
                'coarse_tca_step_idx': int(min_step_idx[c_idx]),
                'orbital_band':        band,
            })

    return candidates


def main():
    script_dir  = os.path.dirname(os.path.abspath(__file__))
    agent_dir   = os.path.dirname(script_dir)
    outputs_dir = os.path.join(agent_dir, 'outputs')
    os.makedirs(outputs_dir, exist_ok=True)

    now = datetime.now(timezone.utc)
    ts  = now.strftime('%Y-%m-%d_%H%M')

    all_candidates = []
    per_satellite_counts = {}

    for band in ('LEO', 'GEO'):
        threshold = COARSE_THRESHOLD_KM[band]
        sidecar, positions, norad_ids = load_latest_state_vectors(outputs_dir, band)

        if positions is None:
            continue

        print(f"[{band}] Screening {len(norad_ids)} objects at threshold {threshold} km …")
        candidates = screen_band(positions, norad_ids, band, threshold)
        all_candidates.extend(candidates)

        # Log per Turkish satellite
        for cand in candidates:
            key = cand['turkish_name']
            per_satellite_counts[key] = per_satellite_counts.get(key, 0) + 1

    # Warn if unexpectedly large
    if len(all_candidates) > 10000:
        print(f"[WARN] {len(all_candidates)} candidates — threshold may be too wide or catalog polluted")

    # Write output
    output = {
        'screen_timestamp_utc': now.isoformat(),
        'total_candidates':     len(all_candidates),
        'per_satellite_counts': per_satellite_counts,
        'candidates':           all_candidates,
    }
    output_path = os.path.join(outputs_dir, f"{ts}_conjunction-candidates.json")
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"[Done] {len(all_candidates)} candidates written to {os.path.basename(output_path)}")
    for sat, count in per_satellite_counts.items():
        print(f"  {sat}: {count} candidates")

    return output_path


if __name__ == '__main__':
    main()
