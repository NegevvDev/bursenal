#!/usr/bin/env python3
"""
TLE Validate Script — tle-ingestion-agent
Performs physical plausibility checks and epoch freshness audit on the TLE catalog.
Outputs: agents/tle-ingestion-agent/outputs/YYYY-MM-DD_tle-validation-report.md

Dependencies: pip install numpy pandas
"""
import json
import os
import math
from datetime import datetime, timezone, timedelta

MU = 3.986004418e14   # m^3/s^2
R_EARTH = 6378.137    # km
TWO_PI = 2 * math.pi

# Freshness thresholds
TURKISH_MAX_AGE_HOURS = 48    # escalation if exceeded
CATALOG_MAX_AGE_DAYS  = 7     # flag for general catalog objects

# Physical limits
MIN_MEAN_MOTION = 0.002   # rev/day (very high GEO)
MAX_MEAN_MOTION = 17.0    # rev/day (ISS-like LEO)
MIN_ALTITUDE_KM = 100.0   # below this → imminent reentry
MAX_ALTITUDE_KM = 100000  # above this → escape trajectory


def parse_epoch(line1: str) -> datetime | None:
    """Parse TLE epoch from line 1 into UTC datetime."""
    try:
        year_2d = int(line1[18:20])
        year = 2000 + year_2d if year_2d < 57 else 1900 + year_2d
        day_frac = float(line1[20:32])
        day = int(day_frac)
        frac = day_frac - day
        epoch = datetime(year, 1, 1, tzinfo=timezone.utc) + timedelta(days=day - 1 + frac)
        return epoch
    except (ValueError, IndexError):
        return None


def parse_mean_motion(line2: str) -> float | None:
    """Parse mean motion (rev/day) from TLE line 2."""
    try:
        return float(line2[52:63])
    except (ValueError, IndexError):
        return None


def parse_bstar(line1: str) -> float | None:
    """Parse BSTAR drag coefficient from TLE line 1."""
    try:
        bstar_str = line1[53:61].strip()
        # Format: ±NNNNN±N (e.g., 12345-3 means 0.12345e-3)
        if len(bstar_str) < 6:
            return None
        mantissa = float(bstar_str[:-2]) * 1e-5
        exponent = int(bstar_str[-2:])
        return mantissa * (10 ** exponent)
    except (ValueError, IndexError):
        return None


def mean_motion_to_altitude(n_rev_day: float) -> float:
    """Convert mean motion (rev/day) to approximate orbital altitude (km)."""
    n_rad_s = n_rev_day * TWO_PI / 86400
    a_m = (MU / n_rad_s**2) ** (1/3)
    return (a_m / 1000) - R_EARTH


def load_latest_catalog(outputs_dir: str) -> dict | None:
    """Load the most recent TLE catalog JSON from outputs directory."""
    files = sorted([
        f for f in os.listdir(outputs_dir)
        if f.endswith('_tle-catalog.json')
    ])
    if not files:
        print("[ERROR] No TLE catalog found in outputs/")
        return None
    path = os.path.join(outputs_dir, files[-1])
    with open(path) as f:
        return json.load(f)


def validate_catalog(catalog_data: dict) -> dict:
    """Run all validation checks. Returns a validation summary dict."""
    now = datetime.now(timezone.utc)
    entries = catalog_data.get('catalog', [])

    flags = []
    turkish_status = {}
    stats = {
        'total': len(entries),
        'epoch_stale_7d': 0,
        'low_mean_motion': 0,
        'high_mean_motion': 0,
        'reentry_risk': 0,
        'zero_bstar_leo': 0,
        'epoch_parse_fail': 0,
    }

    for obj in entries:
        norad_id = obj.get('norad_id')
        line1    = obj.get('line1', '')
        line2    = obj.get('line2', '')
        band     = obj.get('orbital_band', 'UNKNOWN')
        name     = obj.get('name', str(norad_id))
        is_turkish = obj.get('is_turkish_satellite', False)
        sat_name   = obj.get('satellite_name', '')

        obj_flags = []

        # 1. Epoch freshness
        epoch = parse_epoch(line1)
        if epoch is None:
            obj_flags.append("EPOCH_PARSE_FAIL")
            stats['epoch_parse_fail'] += 1
        else:
            age_hours = (now - epoch).total_seconds() / 3600
            if is_turkish:
                status = 'FRESH' if age_hours <= 48 else 'STALE'
                turkish_status[sat_name] = {
                    'norad_id': norad_id,
                    'epoch_utc': epoch.isoformat(),
                    'age_hours': round(age_hours, 1),
                    'status': status,
                }
                if age_hours > 48:
                    obj_flags.append(f"TURKISH_STALE ({age_hours:.0f}h old)")
            if age_hours > CATALOG_MAX_AGE_DAYS * 24:
                obj_flags.append(f"STALE_7D ({age_hours/24:.1f} days)")
                stats['epoch_stale_7d'] += 1

        # 2. Mean motion plausibility
        n = parse_mean_motion(line2)
        if n is not None:
            if n < MIN_MEAN_MOTION:
                obj_flags.append(f"LOW_MEAN_MOTION ({n:.4f})")
                stats['low_mean_motion'] += 1
            elif n > MAX_MEAN_MOTION:
                obj_flags.append(f"HIGH_MEAN_MOTION ({n:.2f})")
                stats['high_mean_motion'] += 1
            else:
                alt = mean_motion_to_altitude(n)
                if alt < MIN_ALTITUDE_KM:
                    obj_flags.append(f"REENTRY_RISK (alt={alt:.1f} km)")
                    stats['reentry_risk'] += 1
                elif alt > MAX_ALTITUDE_KM:
                    obj_flags.append(f"ESCAPE_TRAJECTORY (alt={alt:.0f} km)")

        # 3. BSTAR check for LEO objects
        if band == 'LEO':
            bstar = parse_bstar(line1)
            if bstar is not None and bstar == 0.0:
                obj_flags.append("ZERO_BSTAR_LEO")
                stats['zero_bstar_leo'] += 1

        if obj_flags:
            flags.append({
                'norad_id': norad_id,
                'name': name,
                'flags': obj_flags,
            })

    # Mark any Turkish satellites completely missing from catalog
    from scripts_context import TURKISH_SATELLITES  # noqa: imported for reference below
    # Re-check which Turkish sats are in catalog
    catalog_norads = {obj['norad_id'] for obj in entries}
    # (Import not possible in standalone script — inline the dict)
    TURKISH_NORAD_IDS = {
        "TURKSAT_4A": 39522, "TURKSAT_4B": 40985,
        "TURKSAT_5A": 47790, "TURKSAT_5B": 49077,
        "GOKTURK_1":  41875, "GOKTURK_2":  38704,
        "RASAT":      37791, "IMECE":       55491,
    }
    for sat_name, norad_id in TURKISH_NORAD_IDS.items():
        if sat_name not in turkish_status:
            turkish_status[sat_name] = {
                'norad_id': norad_id,
                'epoch_utc': None,
                'age_hours': None,
                'status': 'MISSING',
            }

    # Escalation flags
    escalations = []
    for sat_name, info in turkish_status.items():
        if info['status'] in ('STALE', 'MISSING'):
            escalations.append(f"Turkish satellite {sat_name} is {info['status']}")
    rejection_rate = (stats['epoch_parse_fail'] + stats['low_mean_motion']) / max(stats['total'], 1)
    if rejection_rate > 0.02:
        escalations.append(f"High rejection rate: {rejection_rate*100:.1f}%")

    return {
        'validated_at_utc': now.isoformat(),
        'catalog_timestamp': catalog_data.get('fetch_timestamp_utc'),
        'stats': stats,
        'turkish_satellite_status': turkish_status,
        'flagged_objects': flags,
        'flagged_count': len(flags),
        'escalations': escalations,
    }


def write_report(result: dict, outputs_dir: str) -> str:
    """Write validation report as markdown."""
    ts = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    path = os.path.join(outputs_dir, f"{ts}_tle-validation-report.md")

    lines = [
        f"# TLE Validation Report",
        f"",
        f"**Validated:** {result['validated_at_utc']}  ",
        f"**Catalog timestamp:** {result['catalog_timestamp']}",
        f"",
        f"## Summary Statistics",
        f"",
        f"| Metric | Count |",
        f"|--------|-------|",
        f"| Total objects | {result['stats']['total']} |",
        f"| Stale >7 days | {result['stats']['epoch_stale_7d']} |",
        f"| Reentry risk (<100 km) | {result['stats']['reentry_risk']} |",
        f"| Zero BSTAR (LEO) | {result['stats']['zero_bstar_leo']} |",
        f"| Epoch parse failures | {result['stats']['epoch_parse_fail']} |",
        f"| Flagged objects total | {result['flagged_count']} |",
        f"",
        f"## Turkish Satellite Status",
        f"",
        f"| Satellite | NORAD ID | Epoch UTC | Age (h) | Status |",
        f"|-----------|----------|-----------|---------|--------|",
    ]
    for sat_name, info in result['turkish_satellite_status'].items():
        epoch = info['epoch_utc'] or 'N/A'
        age   = f"{info['age_hours']:.1f}" if info['age_hours'] is not None else 'N/A'
        status = info['status']
        icon  = '✅' if status == 'FRESH' else ('⚠️' if status == 'STALE' else '❌')
        lines.append(f"| {sat_name} | {info['norad_id']} | {epoch} | {age} | {icon} {status} |")

    if result['escalations']:
        lines += ["", "## ⚠️ Escalation Flags", ""]
        for esc in result['escalations']:
            lines.append(f"- {esc}")

    if result['flagged_objects']:
        lines += ["", f"## Flagged Objects ({result['flagged_count']})", ""]
        for obj in result['flagged_objects'][:50]:  # cap at 50 for readability
            lines.append(f"- NORAD {obj['norad_id']} ({obj['name']}): {', '.join(obj['flags'])}")
        if result['flagged_count'] > 50:
            lines.append(f"- ... and {result['flagged_count'] - 50} more (see JSON output for full list)")

    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    return path


def main():
    script_dir  = os.path.dirname(os.path.abspath(__file__))
    agent_dir   = os.path.dirname(script_dir)
    outputs_dir = os.path.join(agent_dir, 'outputs')

    catalog_data = load_latest_catalog(outputs_dir)
    if catalog_data is None:
        return

    result = validate_catalog(catalog_data)
    report_path = write_report(result, outputs_dir)

    # Console summary
    print(f"[Validation] {result['stats']['total']} objects | {result['flagged_count']} flagged")
    print(f"[Turkish Satellites]")
    for sat, info in result['turkish_satellite_status'].items():
        print(f"  {sat}: {info['status']} (age: {info['age_hours']}h)")
    if result['escalations']:
        print("[ESCALATION FLAGS]")
        for esc in result['escalations']:
            print(f"  !! {esc}")
    print(f"[Report] {report_path}")


if __name__ == '__main__':
    main()
