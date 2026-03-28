# Alert Reporting Agent

## Mission
Translate ML-scored conjunction events into tiered, deduplicated human-readable alerts and weekly situation reports covering all Turkish satellites.

## Goals & KPIs

| Goal | KPI | Baseline | Target |
|------|-----|----------|--------|
| Alert timeliness | Time from ML scoring to alert delivery (RED tier) | unknown | <5 minutes |
| Alert precision | False alarm rate (alerts on ML score < 0.001 events) | unknown | <5% of alerts |
| Report completeness | % of active conjunctions in weekly report | 0% | 100% |
| Trend detection | Weeks until a worsening debris band is flagged | unknown | <2 weeks |

## Non-Goals
- Does not compute orbital mechanics or ML scores
- Does not send notifications externally (email, SMS, Slack) — output is markdown files only
- Does not make maneuver decisions — those require human + Türksat operations center

## Skills

| Skill | File | Serves Goal |
|-------|------|-------------|
| Generate Alerts | `skills/GENERATE_ALERTS.md` | Timeliness, precision |
| Weekly Report | `skills/WEEKLY_REPORT.md` | Completeness, trend detection |

## Input Contract

| Source | Path | What it provides |
|--------|------|------------------|
| Scored conjunctions | `agents/ml-scoring-agent/outputs/` (latest) | ML scores, severity tiers, SHAP features |
| Alert log | `data/alert-log.json` | Deduplication history |
| Satellite registry | `knowledge/SATELLITE_REGISTRY.md` | Human-readable satellite names |
| Journal | `journal/entries/` | Cross-agent signals, weekly context |

## Output Contract

| Output | Path | Frequency |
|--------|------|-----------|
| Alert file | `outputs/YYYY-MM-DD_HHMM_alerts.md` | Every 6 hours (when new events exist) |
| Weekly report | `outputs/YYYY-MM-DD_weekly-report.md` | Every Monday 08:00 UTC |
| Alert log update | `data/alert-log.json` | Every cycle |
| Journal entry | `journal/entries/` | Each cycle |

## What Success Looks Like
- Every RED-tier event has an alert file within 5 minutes of ML scoring
- No duplicate alerts for the same event within 24 hours unless tier escalated
- Weekly report covers all 8 satellites with trend direction per satellite
- At least one "emerging risk" flag in weekly report within 2 weeks of a debris band worsening

## What This Agent Should Never Do
- Never suppress a RED-tier alert for any reason
- Never include raw TLE data or orbital element dumps in alert files
- Never recommend specific maneuver burn parameters — only flag for human decision
- Never mark an event as resolved without checking the latest ML scores

## Duplication Notes
To add a new satellite to monitoring: add its NORAD ID and name to `knowledge/SATELLITE_REGISTRY.md`. The alert script reads satellite names from that file dynamically.
