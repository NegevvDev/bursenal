#!/usr/bin/env python3
"""
Compute TCA Script — conjunction-analysis-agent
Computes precise Time of Closest Approach for screened candidate pairs.
Output: outputs/YYYY-MM-DD_HHMM_tca-results.json

Dependencies: pip install sgp4 numpy scipy
"""
import json
import math
import os
from datetime import datetime, timezone, timedelta

import numpy as np
from scipy.optimize import minimize_scalar
from sgp4.api import Satrec, jday

# ── Configuration ────────────────────────────────────────────────────────────
FINE_WINDOW_MIN  = 30    # ± minutes around coarse TCA
FINE_STEP_S      = 5     # seconds for fine grid
BRENT_MARGIN_S   = 60    # ± seconds for Brent refinement


def load_latest_file(directory: str, pattern: str) -> str | None:
    """Return path to the latest file matching a suffix pattern."""
    files = sorted([f for f in os.listdir(directory) if f.endswith(pattern)])
    return os.path.join(directory, files[-1]) if files else None


def tle_catalog_by_norad(catalog_path: str) -> dict[int, tuple[str, str]]:
    """Load TLE catalog and return {norad_id: (line1, line2)}."""
    with open(catalog_path) as f:
        data = json.load(f)
    return {obj['norad_id']: (obj['line1'], obj['line2']) for obj in data['catalog']}


def sgp4_position(satrec: Satrec, jd: float, fr: float) -> tuple[np.ndarray, np.ndarray] | None:
    """Return (pos_km, vel_km_s) or None on error."""
    e, r, v = satrec.sgp4(jd, fr)
    if e != 0:
        return None
    return np.array(r, dtype=np.float64), np.array(v, dtype=np.float64)


def datetime_to_jd(dt: datetime) -> tuple[float, float]:
    """Convert datetime to (jd, fr) Julian date pair."""
    return jday(dt.year, dt.month, dt.day, dt.hour, dt.minute,
                dt.second + dt.microsecond / 1e6)


def jd_to_datetime(jd_full: float) -> datetime:
    """Convert Julian date (float) to UTC datetime (approximate)."""
    # JD epoch: noon Jan 1 4713 BC = JD 0
    jd_unix_epoch = 2440587.5  # JD of 1970-01-01 00:00 UTC
    seconds_since_epoch = (jd_full - jd_unix_epoch) * 86400
    return datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=seconds_since_epoch)


def compute_rsw_frame(pos: np.ndarray, vel: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Compute RSW (Radial-Along-track-Cross-track) unit vectors."""
    r_hat = pos / np.linalg.norm(pos)
    w_hat = np.cross(pos, vel)
    w_hat = w_hat / np.linalg.norm(w_hat)
    s_hat = np.cross(w_hat, r_hat)
    return r_hat, s_hat, w_hat


def compute_tca_for_pair(
    sat1: Satrec, sat2: Satrec,
    coarse_jd: float, coarse_fr: float,
    fine_step_s: float = FINE_STEP_S,
    brent_margin_s: float = BRENT_MARGIN_S,
) -> dict | None:
    """
    Compute TCA for a (primary, secondary) satellite pair.
    coarse_jd/coarse_fr: Julian date of the coarse minimum found during screening.
    Returns dict with TCA geometry or None on failure.
    """
    # Build fine time grid: ± FINE_WINDOW_MIN around coarse TCA
    fine_offsets_s = np.arange(-FINE_WINDOW_MIN * 60, FINE_WINDOW_MIN * 60 + fine_step_s, fine_step_s)
    coarse_jd_full = coarse_jd + coarse_fr

    distances = []
    jd_fulls  = []

    for offset_s in fine_offsets_s:
        jd_full = coarse_jd_full + offset_s / 86400.0
        jd_int  = int(jd_full)
        jd_frac = jd_full - jd_int
        r1v1 = sgp4_position(sat1, jd_int, jd_frac)
        r2v2 = sgp4_position(sat2, jd_int, jd_frac)
        if r1v1 is None or r2v2 is None:
            distances.append(np.inf)
        else:
            distances.append(np.linalg.norm(r2v2[0] - r1v1[0]))
        jd_fulls.append(jd_full)

    distances = np.array(distances)
    min_idx = np.argmin(distances)
    refined_coarse_jd = jd_fulls[min_idx]

    # Brent minimization for sub-second precision
    def distance_at_offset(offset_s: float) -> float:
        jd_f = refined_coarse_jd + offset_s / 86400.0
        jd_i = int(jd_f)
        jd_r = jd_f - jd_i
        r1v1 = sgp4_position(sat1, jd_i, jd_r)
        r2v2 = sgp4_position(sat2, jd_i, jd_r)
        if r1v1 is None or r2v2 is None:
            return 1e9
        return float(np.linalg.norm(r2v2[0] - r1v1[0]))

    try:
        result = minimize_scalar(
            distance_at_offset,
            bounds=(-brent_margin_s, brent_margin_s),
            method='bounded',
            options={'xatol': 0.1},  # 0.1 second tolerance
        )
        tca_jd_full = refined_coarse_jd + result.x / 86400.0
    except Exception:
        tca_jd_full = refined_coarse_jd

    # Final state at TCA
    tca_jd_int  = int(tca_jd_full)
    tca_jd_frac = tca_jd_full - tca_jd_int
    r1v1 = sgp4_position(sat1, tca_jd_int, tca_jd_frac)
    r2v2 = sgp4_position(sat2, tca_jd_int, tca_jd_frac)

    if r1v1 is None or r2v2 is None:
        return None

    r1, v1 = r1v1
    r2, v2 = r2v2
    miss_vec  = r2 - r1
    miss_dist = float(np.linalg.norm(miss_vec))
    rel_vel   = float(np.linalg.norm(v2 - v1))

    # Project miss vector onto RSW frame of primary (Turkish satellite)
    r_hat, s_hat, w_hat = compute_rsw_frame(r1, v1)
    radial_miss    = float(np.dot(miss_vec, r_hat))
    intrack_miss   = float(np.dot(miss_vec, s_hat))
    crosstrack_miss = float(np.dot(miss_vec, w_hat))

    tca_utc = jd_to_datetime(tca_jd_full)

    return {
        'tca_utc':             tca_utc.isoformat(),
        'miss_distance_km':    miss_dist,
        'relative_velocity_km_s': rel_vel,
        'radial_miss_km':      radial_miss,
        'intrack_miss_km':     intrack_miss,
        'crosstrack_miss_km':  crosstrack_miss,
        'tca_jd':              tca_jd_full,
    }


def main():
    script_dir  = os.path.dirname(os.path.abspath(__file__))
    agent_dir   = os.path.dirname(script_dir)
    outputs_dir = os.path.join(agent_dir, 'outputs')
    os.makedirs(outputs_dir, exist_ok=True)

    agents_root = os.path.dirname(agent_dir)

    # Load candidates
    candidates_path = load_latest_file(
        os.path.join(agents_root, 'orbit-propagation-agent', 'outputs'),
        '_conjunction-candidates.json'
    )
    if not candidates_path:
        print("[ERROR] No conjunction candidates file found")
        return

    # Load TLE catalog
    catalog_path = load_latest_file(
        os.path.join(agents_root, 'tle-ingestion-agent', 'outputs'),
        '_tle-catalog.json'
    )
    if not catalog_path:
        print("[ERROR] No TLE catalog found")
        return

    with open(candidates_path) as f:
        candidates_data = json.load(f)
    tle_map = tle_catalog_by_norad(catalog_path)

    candidates = candidates_data['candidates']
    print(f"[TCA] Processing {len(candidates)} candidates …")

    now = datetime.now(timezone.utc)
    ts  = now.strftime('%Y-%m-%d_%H%M')

    # TLE ingestion timestamp → base Julian date for step index conversion
    cat_ts_str = json.load(open(catalog_path))['fetch_timestamp_utc']
    cat_ts = datetime.fromisoformat(cat_ts_str)

    tca_results = []
    failures    = 0

    for cand in candidates:
        t_norad = cand['turkish_norad_id']
        d_norad = cand['debris_norad_id']
        band    = cand.get('orbital_band', 'LEO')
        step_s  = 60 if band == 'LEO' else 300

        if t_norad not in tle_map or d_norad not in tle_map:
            failures += 1
            continue

        sat1 = Satrec.twoline2rv(*tle_map[t_norad])
        sat2 = Satrec.twoline2rv(*tle_map[d_norad])

        # Convert step index to coarse Julian date
        coarse_offset_s = cand['coarse_tca_step_idx'] * step_s
        coarse_dt = cat_ts + timedelta(seconds=coarse_offset_s)
        coarse_jd, coarse_fr = datetime_to_jd(coarse_dt)

        geometry = compute_tca_for_pair(sat1, sat2, coarse_jd, coarse_fr)
        if geometry is None:
            failures += 1
            continue

        record = {
            'turkish_norad_id':      t_norad,
            'turkish_name':          cand.get('turkish_name', str(t_norad)),
            'debris_norad_id':       d_norad,
            'orbital_band':          band,
            'coarse_min_dist_km':    cand['coarse_min_dist_km'],
            **geometry,
        }
        tca_results.append(record)

    # Write output
    output = {
        'computed_at_utc': now.isoformat(),
        'total_computed':  len(tca_results),
        'failures':        failures,
        'tca_results':     tca_results,
    }
    output_path = os.path.join(outputs_dir, f"{ts}_tca-results.json")
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"[Done] {len(tca_results)} TCA results | {failures} failures")
    print(f"       Written: {os.path.basename(output_path)}")
    return output_path


if __name__ == '__main__':
    main()
