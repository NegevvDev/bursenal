#!/usr/bin/env python3
"""
TLE Fetch Script — tle-ingestion-agent
Fetches Two-Line Element sets from Space-Track.org.
Outputs: agents/tle-ingestion-agent/outputs/YYYY-MM-DD_HHMM_tle-catalog.json

Dependencies: pip install requests
"""
import requests
import json
import os
import math
from datetime import datetime, timezone, timedelta

# ── Turkish satellite NORAD IDs ──────────────────────────────────────────────
TURKISH_SATELLITES = {
    "TURKSAT_4A": 39522,
    "TURKSAT_4B": 40985,
    "TURKSAT_5A": 47790,
    "TURKSAT_5B": 49077,
    "GOKTURK_1":  41875,
    "GOKTURK_2":  38704,
    "RASAT":      37791,
    "IMECE":      55491,
}

# ── Space-Track altitude bands (km) ─────────────────────────────────────────
SPACETRACK_BANDS = {
    "GEO_BAND": (35000, 36500),
    "LEO_BAND": (300, 1200),
}

MU = 3.986004418e14  # m^3/s^2
R_EARTH = 6378.137   # km


def validate_tle_checksum(line: str) -> bool:
    """Validate TLE line checksum (mod-10 sum of digits, minus = 1)."""
    if len(line) < 69:
        return False
    checksum = sum(
        int(c) if c.isdigit() else (1 if c == '-' else 0)
        for c in line[:68]
    )
    try:
        return (checksum % 10) == int(line[68])
    except (ValueError, IndexError):
        return False


def parse_tle_text(text: str) -> list[tuple[str, str, str]]:
    """Parse raw TLE text (2-line or 3-line format) into (name, line1, line2) tuples."""
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    tles = []
    i = 0
    while i < len(lines):
        l = lines[i]
        if not l.startswith('1 ') and not l.startswith('2 '):
            if i + 2 < len(lines) and lines[i+1].startswith('1 ') and lines[i+2].startswith('2 '):
                tles.append((l, lines[i+1], lines[i+2]))
                i += 3
                continue
        if l.startswith('1 ') and i + 1 < len(lines) and lines[i+1].startswith('2 '):
            tles.append(('UNKNOWN', l, lines[i+1]))
            i += 2
            continue
        i += 1
    return tles


def fetch_spacetrack(credentials_path: str, bands: dict, turkish_norad_ids: list) -> list[tuple[str, str, str]]:
    """Fetch TLEs from Space-Track.org for altitude bands + Turkish satellites by NORAD ID."""
    if not os.path.exists(credentials_path):
        print("[INFO] credentials.env not found — skipping Space-Track fetch")
        return []

    creds = {}
    with open(credentials_path) as f:
        for line in f:
            line = line.strip()
            if '=' in line and not line.startswith('#'):
                k, v = line.split('=', 1)
                creds[k.strip()] = v.strip()

    user = creds.get('SPACETRACK_USER', '')
    pwd  = creds.get('SPACETRACK_PASS', '')
    if not user or not pwd:
        print("[WARN] credentials.env missing SPACETRACK_USER or SPACETRACK_PASS")
        return []

    session = requests.Session()
    try:
        resp = session.post(
            "https://www.space-track.org/ajaxauth/login",
            data={'identity': user, 'password': pwd},
            timeout=30,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[ERROR] Space-Track login failed: {e}")
        return []

    all_tles = []

    # 1. Altitude band queries
    for band_name, (alt_min, alt_max) in bands.items():
        a_min = (R_EARTH + alt_min) * 1000  # m
        a_max = (R_EARTH + alt_max) * 1000  # m
        n_max = math.sqrt(MU / a_min**3) * 86400 / (2 * math.pi)
        n_min = math.sqrt(MU / a_max**3) * 86400 / (2 * math.pi)
        url = (
            f"https://www.space-track.org/basicspacedata/query/class/gp/"
            f"MEAN_MOTION/{n_min:.4f}--{n_max:.4f}/"
            f"EPOCH/%3Enow-2/orderby/NORAD_CAT_ID/format/tle"
        )
        try:
            r = session.get(url, timeout=60)
            r.raise_for_status()
            tles = parse_tle_text(r.text)
            print(f"[SpaceTrack/{band_name}] {len(tles)} objects fetched")
            all_tles.extend(tles)
        except requests.RequestException as e:
            print(f"[WARN] SpaceTrack/{band_name} failed: {e}")

    # 2. Direct query for Turkish satellites by NORAD ID
    norad_str = ','.join(str(n) for n in turkish_norad_ids)
    url = (
        f"https://www.space-track.org/basicspacedata/query/class/gp/"
        f"NORAD_CAT_ID/{norad_str}/orderby/NORAD_CAT_ID/format/tle"
    )
    try:
        r = session.get(url, timeout=30)
        r.raise_for_status()
        tles = parse_tle_text(r.text)
        print(f"[SpaceTrack/Turkish] {len(tles)} objects fetched")
        all_tles.extend(tles)
    except requests.RequestException as e:
        print(f"[WARN] SpaceTrack/Turkish query failed: {e}")

    return all_tles


def parse_tle_epoch(line1: str) -> str:
    """Parse epoch from TLE line 1 and return ISO 8601 UTC string."""
    try:
        year_2d = int(line1[18:20])
        year = 2000 + year_2d if year_2d < 57 else 1900 + year_2d
        day_frac = float(line1[20:32])
        day = int(day_frac)
        frac = day_frac - day
        epoch_dt = datetime(year, 1, 1, tzinfo=timezone.utc) + timedelta(days=day - 1 + frac)
        return epoch_dt.isoformat()
    except (ValueError, IndexError):
        return "1900-01-01T00:00:00+00:00"


def determine_band(line2: str) -> str:
    """Determine orbital band from mean motion in TLE line 2."""
    try:
        mean_motion = float(line2[52:63])
        return 'GEO' if mean_motion < 3.0 else 'LEO'
    except (ValueError, IndexError):
        return 'UNKNOWN'


def build_catalog(all_tles: list[tuple[str, str, str]]) -> dict:
    """Deduplicate by NORAD ID (keep most recent epoch), validate checksums, annotate Turkish satellites."""
    catalog = {}
    rejected = 0

    for name, line1, line2 in all_tles:
        if not validate_tle_checksum(line1) or not validate_tle_checksum(line2):
            rejected += 1
            continue
        try:
            norad_id = int(line1[2:7])
        except ValueError:
            rejected += 1
            continue

        epoch_utc = parse_tle_epoch(line1)
        existing = catalog.get(norad_id)
        if existing is None or epoch_utc > existing['epoch_utc']:
            catalog[norad_id] = {
                'norad_id':     norad_id,
                'name':         name.strip(),
                'line1':        line1,
                'line2':        line2,
                'epoch_utc':    epoch_utc,
                'orbital_band': determine_band(line2),
            }

    turkish_nids = {v: k for k, v in TURKISH_SATELLITES.items()}
    for norad_id, entry in catalog.items():
        if norad_id in turkish_nids:
            entry['is_turkish_satellite'] = True
            entry['satellite_name'] = turkish_nids[norad_id]

    print(f"[Catalog] {len(catalog)} objects | {rejected} rejected (bad checksum/format)")
    return catalog


def main():
    script_dir  = os.path.dirname(os.path.abspath(__file__))
    agent_dir   = os.path.dirname(script_dir)
    outputs_dir = os.path.join(agent_dir, 'outputs')
    os.makedirs(outputs_dir, exist_ok=True)

    credentials_path = os.path.join(agent_dir, 'data', 'imports', 'credentials.env')
    turkish_norad_ids = list(TURKISH_SATELLITES.values())

    all_tles = fetch_spacetrack(credentials_path, SPACETRACK_BANDS, turkish_norad_ids)
    catalog  = build_catalog(all_tles)

    missing = [name for name, nid in TURKISH_SATELLITES.items() if nid not in catalog]
    if missing:
        print(f"[WARN] Missing Turkish satellites: {missing}")

    now = datetime.now(timezone.utc)
    ts  = now.strftime('%Y-%m-%d_%H%M')
    output = {
        'fetch_timestamp_utc':        now.isoformat(),
        'total_objects':              len(catalog),
        'turkish_satellites_found':   sum(1 for v in catalog.values() if v.get('is_turkish_satellite')),
        'missing_turkish_satellites': missing,
        'geo_object_count':           sum(1 for v in catalog.values() if v['orbital_band'] == 'GEO'),
        'leo_object_count':           sum(1 for v in catalog.values() if v['orbital_band'] == 'LEO'),
        'catalog':                    list(catalog.values()),
    }
    output_path = os.path.join(outputs_dir, f"{ts}_tle-catalog.json")
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"[Done] Written: {output_path}")
    print(f"       {len(catalog)} objects | GEO: {output['geo_object_count']} | LEO: {output['leo_object_count']}")
    if missing:
        print(f"       MISSING Turkish satellites: {missing}")
    return output_path


if __name__ == '__main__':
    main()
