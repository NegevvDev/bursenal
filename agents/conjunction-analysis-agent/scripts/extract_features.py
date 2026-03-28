#!/usr/bin/env python3
"""
Feature Extraction Script — conjunction-analysis-agent
Builds the ML feature matrix from conjunction events + orbital elements.
Output: outputs/YYYY-MM-DD_HHMM_ml-features.parquet

Dependencies: pip install numpy pandas pyarrow scikit-learn sgp4 joblib
"""
import hashlib
import json
import math
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sgp4.api import Satrec

MU = 3.986004418e14   # m^3/s^2

TURKISH_NORAD_IDS = {39522, 40985, 47790, 49077, 41875, 38704, 37791, 55491}


def mean_elements_from_tle(line1: str, line2: str) -> dict:
    """Extract mean Keplerian elements from TLE line 2."""
    try:
        satrec = Satrec.twoline2rv(line1, line2)
        # SGP4 stores mean elements in SI units internally
        # Mean motion: satrec.no_kozai in rad/min → convert to rad/s
        n_rad_s = satrec.no_kozai / 60.0
        a_m = (MU / n_rad_s**2) ** (1/3) if n_rad_s > 0 else 0.0
        return {
            'sma_km':         a_m / 1000.0,
            'eccentricity':   satrec.ecco,
            'inclination_deg': math.degrees(satrec.inclo),
            'raan_deg':        math.degrees(satrec.nodeo),
            'arg_perigee_deg': math.degrees(satrec.argpo),
            'mean_motion_revday': satrec.no_kozai * (1440 / (2 * math.pi)),
        }
    except Exception:
        return {k: 0.0 for k in ['sma_km', 'eccentricity', 'inclination_deg',
                                   'raan_deg', 'arg_perigee_deg', 'mean_motion_revday']}


def encode_object_type(name: str) -> int:
    """Heuristic object type from name: 0=active sat, 1=rocket body, 2=debris."""
    name_upper = name.upper()
    if 'DEB' in name_upper or 'DEBRIS' in name_upper or 'FRAG' in name_upper:
        return 2
    if 'R/B' in name_upper or 'ROCKET' in name_upper or 'BOOSTER' in name_upper:
        return 1
    return 0


def make_event_id(turkish_norad: int, debris_norad: int, tca_utc: str) -> str:
    """Deterministic SHA-256 event ID."""
    tca_date = tca_utc[:10] if tca_utc else 'unknown'
    raw = f"{turkish_norad}_{debris_norad}_{tca_date}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def load_latest_file(directory: str, suffix: str) -> str | None:
    files = sorted([f for f in os.listdir(directory) if f.endswith(suffix)])
    return os.path.join(directory, files[-1]) if files else None


def main():
    script_dir  = os.path.dirname(os.path.abspath(__file__))
    agent_dir   = os.path.dirname(script_dir)
    outputs_dir = os.path.join(agent_dir, 'outputs')
    agents_root = os.path.dirname(agent_dir)
    os.makedirs(outputs_dir, exist_ok=True)

    # Load conjunction events
    events_path = load_latest_file(outputs_dir, '_conjunction-events.json')
    if not events_path:
        print("[ERROR] No conjunction events found")
        return
    with open(events_path) as f:
        events_data = json.load(f)

    # Load TLE catalog for orbital elements
    catalog_path = load_latest_file(
        os.path.join(agents_root, 'tle-ingestion-agent', 'outputs'),
        '_tle-catalog.json'
    )
    if not catalog_path:
        print("[ERROR] No TLE catalog found")
        return
    with open(catalog_path) as f:
        catalog_data = json.load(f)
    tle_map = {obj['norad_id']: obj for obj in catalog_data['catalog']}

    now = datetime.now(timezone.utc)
    ts  = now.strftime('%Y-%m-%d_%H%M')

    rows = []

    for ev in events_data['conjunction_events']:
        t_norad = ev['turkish_norad_id']
        d_norad = ev['debris_norad_id']
        tca_utc = ev['tca_utc']

        # TCA hours from now
        try:
            tca_dt = datetime.fromisoformat(tca_utc)
            tca_hours = (tca_dt - now).total_seconds() / 3600
        except ValueError:
            tca_hours = 24.0

        # Orbital elements
        t_obj = tle_map.get(t_norad, {})
        d_obj = tle_map.get(d_norad, {})

        t_elems = mean_elements_from_tle(t_obj.get('line1', ''), t_obj.get('line2', ''))
        d_elems = mean_elements_from_tle(d_obj.get('line1', ''), d_obj.get('line2', ''))

        d_name = d_obj.get('name', '')
        obj_type = encode_object_type(d_name)

        pc_analytic = ev.get('analytic_pc', 1e-12)
        log_pc = math.log10(max(pc_analytic, 1e-12))

        miss_dist  = ev['miss_distance_km']
        rel_vel    = ev['relative_velocity_km_s']
        tca_urgency = 1.0 / (abs(tca_hours) + 1.0)

        # Interaction features
        velocity_miss_product = rel_vel * miss_dist
        delta_inc = abs(t_elems['inclination_deg'] - d_elems['inclination_deg'])
        delta_sma = abs(t_elems['sma_km'] - d_elems['sma_km'])
        orbital_similarity = 1.0 / (1.0 + delta_inc / 90.0 + delta_sma / 10000.0)

        row = {
            # Metadata (not features)
            'event_id':            make_event_id(t_norad, d_norad, tca_utc),
            'turkish_norad_id':    t_norad,
            'debris_norad_id':     d_norad,
            'tca_utc':             tca_utc,
            'severity_tier':       ev.get('severity_tier', 'GREEN'),

            # Features
            'miss_distance_km':        miss_dist,
            'relative_velocity_km_s':  rel_vel,
            'radial_miss_km':          ev.get('radial_miss_km', 0.0),
            'intrack_miss_km':         ev.get('intrack_miss_km', 0.0),
            'crosstrack_miss_km':      ev.get('crosstrack_miss_km', 0.0),
            'tca_hours_from_now':      tca_hours,
            'log10_pc_analytic':       log_pc,
            'primary_sma_km':          t_elems['sma_km'],
            'primary_eccentricity':    t_elems['eccentricity'],
            'primary_inclination_deg': t_elems['inclination_deg'],
            'primary_raan_deg':        t_elems['raan_deg'],
            'secondary_sma_km':        d_elems['sma_km'],
            'secondary_eccentricity':  d_elems['eccentricity'],
            'secondary_inclination_deg': d_elems['inclination_deg'],
            'secondary_raan_deg':      d_elems['raan_deg'],
            'object_type_encoded':     obj_type,
            'tca_urgency':             tca_urgency,
            'velocity_miss_product':   velocity_miss_product,
            'delta_inclination_deg':   delta_inc,
            'delta_sma_km':            delta_sma,
            'orbital_similarity_score': orbital_similarity,

            # Normalization flag
            'normalized': False,
        }
        rows.append(row)

    df = pd.DataFrame(rows)

    # Apply scaler if available
    ml_agent_models = os.path.join(agents_root, 'ml-scoring-agent', 'data', 'models')
    scaler_path = os.path.join(ml_agent_models, 'scaler.pkl')

    feature_cols = [
        'miss_distance_km', 'relative_velocity_km_s', 'radial_miss_km',
        'intrack_miss_km', 'crosstrack_miss_km', 'tca_hours_from_now',
        'log10_pc_analytic', 'primary_sma_km', 'primary_eccentricity',
        'primary_inclination_deg', 'primary_raan_deg', 'secondary_sma_km',
        'secondary_eccentricity', 'secondary_inclination_deg', 'secondary_raan_deg',
        'object_type_encoded', 'tca_urgency', 'velocity_miss_product',
        'delta_inclination_deg', 'delta_sma_km', 'orbital_similarity_score',
    ]

    if os.path.exists(scaler_path):
        try:
            import joblib
            scaler = joblib.load(scaler_path)
            df[feature_cols] = scaler.transform(df[feature_cols])
            df['normalized'] = True
            print("[Features] StandardScaler applied")
        except Exception as e:
            print(f"[WARN] Scaler load failed ({e}) — writing un-normalized features")
    else:
        print("[Features] No scaler found — writing un-normalized features")

    # Fill any NaN values with column median
    df[feature_cols] = df[feature_cols].fillna(df[feature_cols].median())

    # Write parquet
    output_path = os.path.join(outputs_dir, f"{ts}_ml-features.parquet")
    df.to_parquet(output_path, index=False)

    print(f"[Features] {len(df)} events | {len(feature_cols)} features | Written: {os.path.basename(output_path)}")
    return output_path


if __name__ == '__main__':
    main()
