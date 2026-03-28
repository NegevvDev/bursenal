#!/usr/bin/env python3
"""
Orbit Propagation Script — orbit-propagation-agent
Propagates all TLE catalog objects using SGP4/SDP4 over a 72-hour window.
Outputs:
  outputs/YYYY-MM-DD_HHMM_state-vectors-LEO.npz + .json sidecar
  outputs/YYYY-MM-DD_HHMM_state-vectors-GEO.npz + .json sidecar

Dependencies: pip install sgp4 numpy
"""
import json
import os
import time
from datetime import datetime, timezone, timedelta

import numpy as np
from sgp4.api import Satrec, jday

# ── Configuration ────────────────────────────────────────────────────────────
WINDOW_HOURS   = 72          # forward propagation window
LEO_STEP_S     = 60          # seconds between LEO time steps
GEO_STEP_S     = 300         # seconds between GEO time steps
MAX_CATALOG_AGE_HOURS = 8    # abort if catalog is older than this

TURKISH_NORAD_IDS = {39522, 40985, 47790, 49077, 41875, 38704, 37791, 55491}


def load_latest_catalog(outputs_dir: str) -> dict | None:
    """Load the most recent tle-catalog.json from tle-ingestion-agent outputs."""
    catalog_dir = os.path.join(
        os.path.dirname(os.path.dirname(outputs_dir)),
        'tle-ingestion-agent', 'outputs'
    )
    if not os.path.exists(catalog_dir):
        print(f"[ERROR] TLE ingestion outputs not found: {catalog_dir}")
        return None

    files = sorted([f for f in os.listdir(catalog_dir) if f.endswith('_tle-catalog.json')])
    if not files:
        print("[ERROR] No TLE catalog found")
        return None

    path = os.path.join(catalog_dir, files[-1])
    with open(path) as f:
        data = json.load(f)

    # Check catalog freshness
    fetch_ts = datetime.fromisoformat(data['fetch_timestamp_utc'])
    age_hours = (datetime.now(timezone.utc) - fetch_ts).total_seconds() / 3600
    if age_hours > MAX_CATALOG_AGE_HOURS:
        print(f"[ABORT] TLE catalog is {age_hours:.1f}h old (max: {MAX_CATALOG_AGE_HOURS}h)")
        return None

    print(f"[Catalog] Loaded {data['total_objects']} objects from {files[-1]}")
    return data


def build_time_grid(start_utc: datetime, window_hours: int, step_s: int) -> tuple[np.ndarray, np.ndarray]:
    """Build Julian date arrays (jd integer, fr fractional) for each time step."""
    n_steps = int(window_hours * 3600 / step_s) + 1
    jd_list, fr_list = [], []
    for i in range(n_steps):
        t = start_utc + timedelta(seconds=i * step_s)
        jd_val, fr_val = jday(t.year, t.month, t.day, t.hour, t.minute, t.second + t.microsecond/1e6)
        jd_list.append(jd_val)
        fr_list.append(fr_val)
    return np.array(jd_list), np.array(fr_list)


def propagate_band(entries: list[dict], band: str, now: datetime) -> dict | None:
    """
    Propagate all objects in a given orbital band.
    Returns dict with positions, velocities, norad_ids, or None on failure.
    """
    step_s = LEO_STEP_S if band == 'LEO' else GEO_STEP_S
    jd_arr, fr_arr = build_time_grid(now, WINDOW_HOURS, step_s)
    n_steps = len(jd_arr)

    norad_ids = []
    positions  = []   # (n_objects, n_steps, 3)
    velocities = []
    errors     = []

    t0 = time.time()
    for obj in entries:
        norad_id = obj['norad_id']
        try:
            satrec = Satrec.twoline2rv(obj['line1'], obj['line2'])
        except Exception as e:
            errors.append({'norad_id': norad_id, 'error': f'init_fail: {e}'})
            continue

        pos_series = np.full((n_steps, 3), np.nan, dtype=np.float32)
        vel_series = np.full((n_steps, 3), np.nan, dtype=np.float32)
        obj_error  = None

        for t_idx in range(n_steps):
            e, r, v = satrec.sgp4(jd_arr[t_idx], fr_arr[t_idx])
            if e == 0:
                pos_series[t_idx] = r
                vel_series[t_idx] = v
            else:
                obj_error = e
                break

        if obj_error is not None:
            errors.append({'norad_id': norad_id, 'error': f'sgp4_code_{obj_error}'})
            continue

        norad_ids.append(norad_id)
        positions.append(pos_series)
        velocities.append(vel_series)

    elapsed = time.time() - t0
    error_rate = len(errors) / max(len(entries), 1)

    print(f"[{band}] {len(norad_ids)} propagated | {len(errors)} errors ({error_rate*100:.1f}%) | {elapsed:.1f}s")

    if error_rate > 0.05:
        print(f"[WARN] {band} error rate {error_rate*100:.1f}% exceeds 5% threshold")

    if not norad_ids:
        return None

    return {
        'norad_ids':    np.array(norad_ids, dtype=np.int32),
        'positions':    np.array(positions,  dtype=np.float32),   # (N, T, 3) km
        'velocities':   np.array(velocities, dtype=np.float32),   # (N, T, 3) km/s
        'time_grid_jd': jd_arr + fr_arr,                          # (T,) Julian dates
        'step_s':       step_s,
        'n_steps':      n_steps,
        'errors':       errors,
        'error_rate':   error_rate,
    }


def main():
    script_dir  = os.path.dirname(os.path.abspath(__file__))
    agent_dir   = os.path.dirname(script_dir)
    outputs_dir = os.path.join(agent_dir, 'outputs')
    os.makedirs(outputs_dir, exist_ok=True)

    catalog_data = load_latest_catalog(outputs_dir)
    if catalog_data is None:
        return

    entries = catalog_data['catalog']
    leo_entries = [e for e in entries if e['orbital_band'] == 'LEO']
    geo_entries = [e for e in entries if e['orbital_band'] == 'GEO']
    print(f"[Split] LEO: {len(leo_entries)} | GEO: {len(geo_entries)}")

    now = datetime.now(timezone.utc)
    ts  = now.strftime('%Y-%m-%d_%H%M')

    results_meta = {'timestamp_utc': now.isoformat(), 'bands': {}}

    for band, band_entries in [('LEO', leo_entries), ('GEO', geo_entries)]:
        if not band_entries:
            print(f"[{band}] No objects — skipping")
            continue

        result = propagate_band(band_entries, band, now)
        if result is None:
            print(f"[{band}] Propagation returned no valid objects")
            continue

        # Verify Turkish satellites
        turkish_in_band = [e['norad_id'] for e in band_entries if e['norad_id'] in TURKISH_NORAD_IDS]
        propagated_set  = set(result['norad_ids'].tolist())
        turkish_missing = [nid for nid in turkish_in_band if nid not in propagated_set]
        if turkish_missing:
            print(f"[WARN] Turkish satellites failed SGP4 in {band}: {turkish_missing}")

        # Save .npz
        npz_path = os.path.join(outputs_dir, f"{ts}_state-vectors-{band}.npz")
        np.savez_compressed(
            npz_path,
            positions=result['positions'],
            velocities=result['velocities'],
            norad_ids=result['norad_ids'],
            time_grid_jd=result['time_grid_jd'],
        )

        # Save JSON sidecar
        sidecar = {
            'band':             band,
            'timestamp_utc':    now.isoformat(),
            'n_objects':        len(result['norad_ids']),
            'n_steps':          result['n_steps'],
            'step_s':           result['step_s'],
            'window_hours':     WINDOW_HOURS,
            'norad_ids':        result['norad_ids'].tolist(),
            'turkish_norad_ids_in_band': turkish_in_band,
            'turkish_missing':  turkish_missing,
            'error_rate':       result['error_rate'],
            'errors':           result['errors'][:50],  # cap for readability
        }
        sidecar_path = os.path.join(outputs_dir, f"{ts}_state-vectors-{band}.json")
        with open(sidecar_path, 'w') as f:
            json.dump(sidecar, f, indent=2)

        results_meta['bands'][band] = {
            'n_objects': len(result['norad_ids']),
            'error_rate': result['error_rate'],
            'npz_file': os.path.basename(npz_path),
        }
        print(f"[{band}] Written: {os.path.basename(npz_path)}")

    print(f"[Done] Propagation complete")
    return results_meta


if __name__ == '__main__':
    main()
