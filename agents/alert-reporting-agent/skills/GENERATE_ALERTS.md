# Skill: Generate Alerts

## Purpose
Produce tiered, deduplicated, human-readable alert files for active conjunction events, updating the alert deduplication log.

## Serves Goals
- Alert timeliness (RED tier alert <5 minutes after ML scoring)
- Alert precision (false alarm rate <5%)

## Inputs
- Most recent `agents/ml-scoring-agent/outputs/YYYY-MM-DD_HHMM_scored-conjunctions.json`
- `data/alert-log.json` — deduplication history (maintained in-place by this skill)
- `knowledge/SATELLITE_REGISTRY.md` — human-readable satellite names

## Process
1. Load scored conjunctions and satellite registry
2. Load `data/alert-log.json`. If file doesn't exist: create empty structure `{"alerts": []}`.
3. For each scored event, compute `event_id` = SHA256 of `{turkish_norad_id}_{debris_norad_id}_{tca_date}` (where tca_date = YYYY-MM-DD of TCA UTC)
4. Deduplication check: if `event_id` already exists in `alert-log.json` with an alert issued <24 hours ago AND `final_tier` has not escalated since last alert → skip (already alerted)
5. For events needing an alert, build alert records by tier:

   **RED tier alert body:**
   ```
   ## 🔴 RED — COLLISION RISK: [Satellite Name] × [Debris Name] (NORAD [ID])
   - TCA: [tca_utc] UTC (in [X] hours)
   - Miss Distance: [X.XX] km
   - Relative Velocity: [X.XX] km/s
   - ML Risk Score: [0.XXX]
   - Analytic Pc: [X.XXe-X]
   - Tier Override: [yes/no]
   - Top Risk Factors: [top_shap_features listed in plain English]
   - Recommended Action: Coordinate with Türksat operations center for potential maneuver assessment. TCA in <24h warrants immediate review.
   ```

   **ORANGE tier alert body:** same fields, Recommended Action: "Monitor closely — re-evaluate when TCA < 24h"

   **YELLOW tier alert body:** condensed fields (satellite, debris, TCA, miss distance, ML score), Recommended Action: "Track — escalate to ORANGE review if ML score increases"

   **GREEN:** no alert generated

6. Combine all new alerts into a single output file: `outputs/YYYY-MM-DD_HHMM_alerts.md` with a header summary table (count by tier) followed by individual alert blocks ordered RED → ORANGE → YELLOW
7. Append each new alert to `data/alert-log.json` with: `event_id`, `alert_timestamp_utc`, `final_tier`, `tca_utc`, `turkish_satellite`, `debris_norad_id`
8. Log to journal: total new alerts by tier, total deduplicated, output file path

## Outputs
- `outputs/YYYY-MM-DD_HHMM_alerts.md` — formatted alert file (only created if new alerts exist)
- `data/alert-log.json` — updated deduplication log (in-place update)

## Quality Bar
- Every RED event must generate an alert — no exceptions
- Alert file header must include a summary table before individual alerts
- SHAP explanation must be in plain English, not raw feature names (`"miss distance is very close"` not `"miss_distance_km SHAP=-2.1"`)
- Deduplication must never suppress a tier escalation (YELLOW→ORANGE or ORANGE→RED always re-alerts)

## Tools
- `scripts/generate_alerts.py`
- Libraries: `json`, `hashlib`, `datetime`, `pandas`

## Integration
- Triggered every 6 hours by heartbeat
- Also triggered out-of-schedule when journal contains a RED event from `ml-scoring-agent`
- Alert log consumed by `WEEKLY_REPORT` skill for trend analysis
