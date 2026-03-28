#!/usr/bin/env python3
"""
Weekly Report Script — alert-reporting-agent
Produces a comprehensive 7-day situation report for all Turkish satellites.
Output: outputs/YYYY-MM-DD_weekly-report.md

Dependencies: pip install pandas numpy json
"""
import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

TIER_ORDER  = {'GREEN': 0, 'YELLOW': 1, 'ORANGE': 2, 'RED': 3}
TIER_ICONS  = {0: '🟢', 1: '🟡', 2: '🟠', 3: '🔴', None: '⬜'}

TURKISH_SATELLITES = {
    39522: "Türksat 4A", 40985: "Türksat 4B",
    47790: "Türksat 5A", 49077: "Türksat 5B",
    41875: "GÖKTÜRK-1",  38704: "GÖKTÜRK-2",
    37791: "RASAT",       55491: "İMECE",
}


def load_scored_files(ml_outputs_dir: str, days: int = 7) -> pd.DataFrame:
    """Aggregate scored conjunction files from the past N days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    frames = []
    if not os.path.exists(ml_outputs_dir):
        return pd.DataFrame()
    for fname in sorted(os.listdir(ml_outputs_dir)):
        if not fname.endswith('_scored-conjunctions.json'):
            continue
        fpath = os.path.join(ml_outputs_dir, fname)
        with open(fpath) as f:
            data = json.load(f)
        scored_at = datetime.fromisoformat(data['scored_at_utc'])
        if scored_at < cutoff:
            continue
        rows = data.get('scored_conjunctions', [])
        if rows:
            df = pd.DataFrame(rows)
            df['scored_at'] = scored_at
            frames.append(df)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def load_drift_report(ml_outputs_dir: str) -> str:
    """Load the latest drift report status."""
    files = sorted([f for f in os.listdir(ml_outputs_dir) if f.endswith('_model-drift-report.md')])
    if not files:
        return "No drift report available"
    with open(os.path.join(ml_outputs_dir, files[-1])) as f:
        for line in f:
            if 'Overall status' in line or 'overall status' in line.lower():
                return line.strip().replace('**', '').replace('*', '')
    return "See latest drift report"


def load_manifest(ml_models_dir: str) -> dict:
    path = os.path.join(ml_models_dir, 'model_manifest.json')
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)


def build_heatmap(df: pd.DataFrame, days: int = 7) -> dict:
    """
    For each Turkish satellite × each of the past 7 days,
    find the maximum tier seen.
    Returns {norad_id: {date_str: max_tier_int}}
    """
    now = datetime.now(timezone.utc)
    heatmap = {nid: {} for nid in TURKISH_SATELLITES}

    for day_offset in range(days):
        day = (now - timedelta(days=day_offset)).strftime('%Y-%m-%d')
        for nid in TURKISH_SATELLITES:
            mask = (
                df.get('turkish_norad_id', pd.Series(dtype=int)) == nid
            ) if 'turkish_norad_id' in df.columns else pd.Series(False)
            day_mask = df['scored_at'].dt.strftime('%Y-%m-%d') == day if 'scored_at' in df.columns else pd.Series(False)
            sub = df[mask & day_mask] if not df.empty else pd.DataFrame()
            if sub.empty:
                heatmap[nid][day] = None
            else:
                max_tier = sub['final_tier'].map(TIER_ORDER).max()
                heatmap[nid][day] = int(max_tier) if not np.isnan(max_tier) else None

    return heatmap


def main():
    script_dir  = os.path.dirname(os.path.abspath(__file__))
    agent_dir   = os.path.dirname(script_dir)
    agents_root = os.path.dirname(agent_dir)
    outputs_dir = os.path.join(agent_dir, 'outputs')
    os.makedirs(outputs_dir, exist_ok=True)

    ml_outputs = os.path.join(agents_root, 'ml-scoring-agent', 'outputs')
    ml_models  = os.path.join(agents_root, 'ml-scoring-agent', 'data', 'models')

    now = datetime.now(timezone.utc)
    ts  = now.strftime('%Y-%m-%d')

    df = load_scored_files(ml_outputs, days=7)
    manifest   = load_manifest(ml_models)
    drift_status = load_drift_report(ml_outputs)

    # Date columns for heatmap
    day_columns = [(now - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(6, -1, -1)]

    # Heatmap
    heatmap = build_heatmap(df, days=7) if not df.empty else {nid: {} for nid in TURKISH_SATELLITES}

    # Top 10 events this week
    top10 = pd.DataFrame()
    if not df.empty and 'ml_score' in df.columns:
        top10 = (df.sort_values('ml_score', ascending=False)
                   .drop_duplicates('event_id')
                   .head(10))

    # New debris objects vs previous week
    prev_df = load_scored_files(ml_outputs, days=14)
    prev_norads = set()
    this_norads = set()
    if not prev_df.empty and 'debris_norad_id' in prev_df.columns:
        prev_week_mask = prev_df['scored_at'] < (now - timedelta(days=7))
        prev_norads = set(prev_df[prev_week_mask]['debris_norad_id'].dropna().astype(int).tolist())
        this_norads = set(prev_df[~prev_week_mask]['debris_norad_id'].dropna().astype(int).tolist())
    new_debris = this_norads - prev_norads

    # Week-over-week max tier per satellite
    wow = {}
    if not df.empty and 'turkish_norad_id' in df.columns and 'final_tier' in df.columns:
        for nid, name in TURKISH_SATELLITES.items():
            sub = df[df['turkish_norad_id'] == nid]
            max_t = sub['final_tier'].map(TIER_ORDER).max() if not sub.empty else 0
            wow[nid] = {'name': name, 'max_tier': int(max_t) if not np.isnan(max_t) else 0}

    # Executive summary
    if df.empty:
        exec_summary = "No conjunction data available this week. Upstream pipeline may not have run."
        highest_event_line = "N/A"
    else:
        max_overall = df['final_tier'].map(TIER_ORDER).max() if 'final_tier' in df.columns else 0
        max_tier_name = {v: k for k, v in TIER_ORDER.items()}.get(int(max_overall), 'GREEN')
        n_events = len(df.drop_duplicates('event_id')) if 'event_id' in df.columns else len(df)
        exec_summary = (
            f"Overall risk level this week: **{max_tier_name}**. "
            f"{n_events} unique conjunction events analyzed across {len(TURKISH_SATELLITES)} Turkish satellites."
        )
        if not top10.empty:
            r = top10.iloc[0]
            t_name = TURKISH_SATELLITES.get(int(r.get('turkish_norad_id', 0)), 'Unknown')
            highest_event_line = (
                f"{t_name} × NORAD {r.get('debris_norad_id', 'N/A')} | "
                f"TCA: {r.get('tca_utc', 'N/A')} | "
                f"ML Score: {r.get('ml_score', 0):.4f} | Tier: {r.get('final_tier', 'N/A')}"
            )
        else:
            highest_event_line = "No high-risk events"

    # ── Build report ───────────────────────────────────────────────────────────
    lines = [
        f"# Weekly Conjunction Situation Report",
        f"",
        f"**Week ending:** {ts}  ",
        f"**Generated:** {now.isoformat()} UTC",
        f"",
        f"## Executive Summary",
        f"",
        f"{exec_summary}",
        f"",
        f"**Highest-risk event:** {highest_event_line}",
        f"",
        f"## Risk Heatmap (Past 7 Days)",
        f"",
        "| Satellite | " + " | ".join(d[-5:] for d in day_columns) + " | Max |",
        "|-----------|" + "|".join(["-------"] * 7) + "|-----|",
    ]

    for nid, name in TURKISH_SATELLITES.items():
        row_tiers = [heatmap.get(nid, {}).get(d) for d in day_columns]
        row_icons = [TIER_ICONS.get(t, '⬜') for t in row_tiers]
        max_t     = max((t for t in row_tiers if t is not None), default=None)
        max_icon  = TIER_ICONS.get(max_t, '⬜')
        lines.append(f"| {name} | " + " | ".join(row_icons) + f" | {max_icon} |")

    lines += ["", "## Week-over-Week Trend", ""]
    for nid, info in wow.items():
        tier_name = {v: k for k, v in TIER_ORDER.items()}.get(info['max_tier'], 'GREEN')
        lines.append(f"- **{info['name']}**: max tier {TIER_ICONS.get(info['max_tier'], '⬜')} {tier_name}")

    lines += ["", "## Top 10 Highest-Risk Events This Week", ""]
    if top10.empty:
        lines.append("No events with ML score data this week.")
    else:
        lines += [
            "| # | Satellite | Debris NORAD | TCA | Miss (km) | Vel (km/s) | ML Score | Tier |",
            "|---|-----------|-------------|-----|-----------|------------|----------|------|",
        ]
        for rank, (_, r) in enumerate(top10.iterrows(), 1):
            t_name = TURKISH_SATELLITES.get(int(r.get('turkish_norad_id', 0)), 'Unknown')
            lines.append(
                f"| {rank} | {t_name} | {r.get('debris_norad_id', 'N/A')} | "
                f"{r.get('tca_utc', 'N/A')[:16]} | "
                f"{r.get('miss_distance_km', 0):.3f} | "
                f"{r.get('relative_velocity_km_s', 0):.2f} | "
                f"{r.get('ml_score', 0):.4f} | "
                f"{TIER_ICONS.get(TIER_ORDER.get(r.get('final_tier', 'GREEN'), 0), '⬜')} {r.get('final_tier', 'N/A')} |"
            )

    lines += ["", f"## New Debris Objects Detected ({len(new_debris)})", ""]
    if new_debris:
        for nid in sorted(new_debris)[:20]:
            lines.append(f"- NORAD {nid}")
        if len(new_debris) > 20:
            lines.append(f"- … and {len(new_debris) - 20} more")
    else:
        lines.append("No newly cataloged debris objects this week.")

    model_ver = manifest.get('version', 'Unknown')
    model_auc = manifest.get('test_auc_roc', 'N/A')
    lines += [
        "", "## Model Health", "",
        f"- **Active model version:** {model_ver}",
        f"- **Test AUC-ROC:** {model_auc}",
        f"- **Drift status:** {drift_status}",
        "",
        "## Recommended Actions", "",
        "- Review any RED or ORANGE events with TCA within 72 hours",
        "- Cross-reference with Türksat operations for GEO conjunctions",
        "- Provide updated CDM files to `conjunction-analysis-agent/data/imports/cdm/` if Space-Track CDMs are available",
        "- Approve or reject pending model retrains in `ml-scoring-agent/data/models/model_manifest.json`",
    ]

    report_content = "\n".join(lines)
    report_path = os.path.join(outputs_dir, f"{ts}_weekly-report.md")
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report_content)

    print(f"[Done] Weekly report written: {os.path.basename(report_path)}")
    return report_path


if __name__ == '__main__':
    main()
