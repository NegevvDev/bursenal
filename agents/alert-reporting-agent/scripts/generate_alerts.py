#!/usr/bin/env python3
"""
Generate Alerts Script — alert-reporting-agent
Produces tiered, deduplicated markdown alert files from ML-scored conjunctions.
Output: outputs/YYYY-MM-DD_HHMM_alerts.md

Dependencies: pip install pandas json hashlib
"""
import hashlib
import json
import os
from datetime import datetime, timezone, timedelta

import pandas as pd

TIER_ORDER = {'GREEN': 0, 'YELLOW': 1, 'ORANGE': 2, 'RED': 3}

TURKISH_NAMES = {
    39522: "Türksat 4A", 40985: "Türksat 4B",
    47790: "Türksat 5A", 49077: "Türksat 5B",
    41875: "GÖKTÜRK-1",  38704: "GÖKTÜRK-2",
    37791: "RASAT",       55491: "İMECE",
}

TIER_ICONS = {'RED': '🔴', 'ORANGE': '🟠', 'YELLOW': '🟡', 'GREEN': '🟢'}


def load_satellite_registry(agents_root: str) -> dict:
    """Load satellite display names from knowledge/SATELLITE_REGISTRY.md."""
    path = os.path.join(agents_root, '..', 'knowledge', 'SATELLITE_REGISTRY.md')
    if not os.path.exists(path):
        return {}
    registry = {}
    with open(path) as f:
        for line in f:
            if '|' in line and 'NORAD' not in line and '---' not in line:
                parts = [p.strip() for p in line.split('|') if p.strip()]
                if len(parts) >= 2:
                    try:
                        norad = int(parts[1])
                        name  = parts[0]
                        registry[norad] = name
                    except ValueError:
                        pass
    return registry


def make_event_id(turkish_norad: int, debris_norad: int, tca_utc: str) -> str:
    tca_date = tca_utc[:10] if tca_utc else 'unknown'
    raw = f"{turkish_norad}_{debris_norad}_{tca_date}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def load_alert_log(log_path: str) -> dict:
    if os.path.exists(log_path):
        with open(log_path) as f:
            return json.load(f)
    return {'alerts': []}


def save_alert_log(log_path: str, log: dict):
    with open(log_path, 'w') as f:
        json.dump(log, f, indent=2)


def shap_to_plain_english(top_shap: list) -> str:
    """Convert SHAP feature list to a readable explanation."""
    if not top_shap:
        return "No feature explanation available"
    parts = []
    for feat in top_shap[:3]:
        label = feat.get('label', feat.get('feature', ''))
        shap_v = feat.get('shap', 0)
        direction = "high" if shap_v > 0 else "low"
        parts.append(f"{label} is {direction}")
    return "; ".join(parts)


def format_alert_block(ev: dict, satellite_names: dict, tier: str, is_new: bool) -> str:
    t_norad   = ev.get('turkish_norad_id', 0)
    d_norad   = ev.get('debris_norad_id', 0)
    tca_utc   = ev.get('tca_utc', 'Unknown')
    miss_dist = ev.get('miss_distance_km', 0)
    rel_vel   = ev.get('relative_velocity_km_s', 0)
    ml_score  = ev.get('ml_score', 0)
    shap_expl = shap_to_plain_english(ev.get('top_shap_features', []))
    override  = "Yes — ML overrode analytic tier" if ev.get('tier_override') else "No"

    sat_name = satellite_names.get(t_norad) or TURKISH_NAMES.get(t_norad, f"NORAD {t_norad}")

    # Compute hours to TCA
    try:
        tca_dt = datetime.fromisoformat(tca_utc)
        delta_h = (tca_dt - datetime.now(timezone.utc)).total_seconds() / 3600
        tca_str = f"{tca_utc} UTC (in {delta_h:.1f} hours)"
    except ValueError:
        tca_str = tca_utc

    if tier == 'RED':
        rec_action = "**Coordinate with Türksat operations center for potential maneuver assessment. TCA within window warrants immediate review.**"
    elif tier == 'ORANGE':
        rec_action = "Monitor closely — re-evaluate when TCA < 24h or if ML score increases."
    else:
        rec_action = "Track — escalate to ORANGE review if ML score increases."

    icon = TIER_ICONS[tier]
    badge = "NEW" if is_new else "UPDATED TIER"

    lines = [
        f"---",
        f"## {icon} {tier} — {sat_name} × NORAD {d_norad}  `[{badge}]`",
        f"",
        f"| Field | Value |",
        f"|-------|-------|",
        f"| TCA | {tca_str} |",
        f"| Miss Distance | {miss_dist:.3f} km |",
        f"| Relative Velocity | {rel_vel:.3f} km/s |",
        f"| ML Risk Score | {ml_score:.4f} |",
        f"| Analytic Tier | {ev.get('analytic_tier', 'N/A')} |",
        f"| Tier Override | {override} |",
        f"| Top Risk Factors | {shap_expl} |",
        f"",
        f"**Recommended Action:** {rec_action}",
        f"",
    ]
    return "\n".join(lines)


def load_latest_scored(ml_outputs_dir: str) -> list:
    files = sorted([f for f in os.listdir(ml_outputs_dir) if f.endswith('_scored-conjunctions.json')])
    if not files:
        return []
    with open(os.path.join(ml_outputs_dir, files[-1])) as f:
        data = json.load(f)
    return data.get('scored_conjunctions', [])


def main():
    script_dir  = os.path.dirname(os.path.abspath(__file__))
    agent_dir   = os.path.dirname(script_dir)
    agents_root = os.path.dirname(agent_dir)
    outputs_dir = os.path.join(agent_dir, 'outputs')
    os.makedirs(outputs_dir, exist_ok=True)

    ml_outputs = os.path.join(agents_root, 'ml-scoring-agent', 'outputs')
    scored_events = load_latest_scored(ml_outputs)
    if not scored_events:
        print("[INFO] No scored conjunction events found")
        return

    satellite_names = load_satellite_registry(agent_dir)
    log_path  = os.path.join(agent_dir, 'data', 'alert-log.json')
    alert_log = load_alert_log(log_path)

    # Build lookup: event_id → most recent alert
    log_lookup = {}
    for entry in alert_log['alerts']:
        eid = entry['event_id']
        if eid not in log_lookup or entry['alert_timestamp_utc'] > log_lookup[eid]['alert_timestamp_utc']:
            log_lookup[eid] = entry

    now = datetime.now(timezone.utc)
    ts  = now.strftime('%Y-%m-%d_%H%M')

    new_alert_blocks = {'RED': [], 'ORANGE': [], 'YELLOW': []}
    new_log_entries  = []
    dedup_count      = 0

    for ev in scored_events:
        tier = ev.get('final_tier', 'GREEN')
        if tier == 'GREEN':
            continue

        t_norad = ev.get('turkish_norad_id', 0)
        d_norad = ev.get('debris_norad_id', 0)
        tca_utc = ev.get('tca_utc', '')
        event_id = make_event_id(t_norad, d_norad, tca_utc)

        prev = log_lookup.get(event_id)
        if prev:
            # Skip if same tier alerted within 24h
            prev_ts = datetime.fromisoformat(prev['alert_timestamp_utc'])
            age_h   = (now - prev_ts).total_seconds() / 3600
            prev_tier_order = TIER_ORDER.get(prev.get('final_tier', 'GREEN'), 0)
            curr_tier_order = TIER_ORDER.get(tier, 0)
            if age_h < 24 and curr_tier_order <= prev_tier_order:
                dedup_count += 1
                continue

        is_new = prev is None
        block  = format_alert_block(ev, satellite_names, tier, is_new)
        new_alert_blocks[tier].append(block)
        new_log_entries.append({
            'event_id':            event_id,
            'alert_timestamp_utc': now.isoformat(),
            'final_tier':          tier,
            'tca_utc':             tca_utc,
            'turkish_norad_id':    t_norad,
            'debris_norad_id':     d_norad,
        })

    total_new = sum(len(v) for v in new_alert_blocks.values())
    print(f"[Alerts] New: RED={len(new_alert_blocks['RED'])} ORANGE={len(new_alert_blocks['ORANGE'])} YELLOW={len(new_alert_blocks['YELLOW'])} | Dedup: {dedup_count}")

    if total_new == 0:
        print("[Info] No new alerts to generate")
        # Update log even if no new alerts
        alert_log['alerts'].extend(new_log_entries)
        save_alert_log(log_path, alert_log)
        return

    # Build alert file
    header_rows = [
        f"# Conjunction Alert Report",
        f"",
        f"**Generated:** {now.isoformat()} UTC  ",
        f"**Total new alerts:** {total_new}",
        f"",
        f"## Summary",
        f"",
        f"| Tier | Count |",
        f"|------|-------|",
        f"| 🔴 RED | {len(new_alert_blocks['RED'])} |",
        f"| 🟠 ORANGE | {len(new_alert_blocks['ORANGE'])} |",
        f"| 🟡 YELLOW | {len(new_alert_blocks['YELLOW'])} |",
        f"| (deduplicated) | {dedup_count} |",
        f"",
        f"## Alerts",
        f"",
    ]

    all_blocks = (new_alert_blocks['RED'] + new_alert_blocks['ORANGE'] + new_alert_blocks['YELLOW'])
    content = "\n".join(header_rows) + "\n".join(all_blocks)

    output_path = os.path.join(outputs_dir, f"{ts}_alerts.md")
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)

    # Update alert log
    alert_log['alerts'].extend(new_log_entries)
    save_alert_log(log_path, alert_log)

    print(f"[Done] Written: {os.path.basename(output_path)}")
    return output_path


if __name__ == '__main__':
    main()
