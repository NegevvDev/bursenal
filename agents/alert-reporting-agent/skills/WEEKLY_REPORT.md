# Skill: Weekly Report

## Purpose
Produce a comprehensive weekly situation report on Turkish satellite conjunction risk, covering all 8 satellites, tier trends, model health, and recommended actions.

## Serves Goals
- Report completeness (100% of active conjunctions covered)
- Trend detection (worsening debris bands flagged within 2 weeks)

## Inputs
- All `agents/ml-scoring-agent/outputs/YYYY-MM-DD_HHMM_scored-conjunctions.json` files from past 7 days
- All `outputs/YYYY-MM-DD_HHMM_alerts.md` from past 7 days
- Most recent `agents/ml-scoring-agent/outputs/YYYY-MM-DD_model-drift-report.md`
- `knowledge/SATELLITE_REGISTRY.md` — satellite names and orbital bands
- `journal/entries/` — cross-agent signals from the past week

## Process
1. Load and aggregate all scored conjunction files from past 7 days into a DataFrame indexed by `(event_id, timestamp)`
2. Load satellite registry for display names

3. **Risk heatmap:** For each of the 8 Turkish satellites × 7 days, find the maximum `final_tier` score seen in any 6-hour cycle. Map tiers to numbers (GREEN=0, YELLOW=1, ORANGE=2, RED=3). Build a heatmap table:
   ```
   | Satellite     | Mon | Tue | Wed | Thu | Fri | Sat | Sun | Max |
   |---------------|-----|-----|-----|-----|-----|-----|-----|-----|
   | Türksat 4A    | 🟡  | 🟡  | 🟢  | 🟢  | 🟡  | 🟢  | 🟢  | YEL |
   ```

4. **Top 10 highest-risk events of the week:** Sort all conjunction events by `ml_score` descending, take top 10. For each: satellite name, debris NORAD ID, TCA, miss distance, velocity, ML score, tier, SHAP top 3 features.

5. **New debris objects:** Identify NORAD IDs appearing in this week's scored events that were NOT in any scored event from the previous week. These may be newly cataloged objects.

6. **Week-over-week trend per satellite:** Compare max tier this week vs last week (read last week's weekly report from `outputs/` for comparison). Flag any satellite with tier escalation (e.g., GREEN→YELLOW or YELLOW→ORANGE across weeks).

7. **Model health:** Read most recent drift report. Report model health status: STABLE / MONITOR / RETRAIN_RECOMMENDED, active model version, test AUC-ROC.

8. **Executive summary (3 sentences max):** State the overall risk level, the highest-risk event of the week, and one recommended action.

9. Assemble the full weekly report in `outputs/YYYY-MM-DD_weekly-report.md`:
   - Executive Summary
   - Risk Heatmap Table
   - Week-over-Week Trend (with escalation flags)
   - Top 10 High-Risk Events (detailed table)
   - New Debris Objects Detected This Week
   - Model Health Summary
   - Recommended Actions (bullet list, max 5 items)

10. Log weekly summary to journal: highest-risk event, tier distribution for the week, any trend flags

## Outputs
- `outputs/YYYY-MM-DD_weekly-report.md` — full situation report

## Quality Bar
- All 8 Turkish satellites must appear in the heatmap (missing satellite = upstream data gap, escalate)
- Executive summary must name the single highest-risk event explicitly
- Report must be self-contained: a reader with no other context must understand the risk level
- Trend comparison must reference the specific previous weekly report file used

## Tools
- `scripts/weekly_report.py`
- Libraries: `pandas`, `json`, `datetime`, `numpy`

## Integration
- Triggered every Monday 08:00 UTC
- Feeds human operator with consolidated view for decision-making
- Journal entry after report published so orchestrator can track system health
