# Skill: Monitor Model Drift

## Purpose
Detect when incoming feature distributions shift relative to the training distribution (data drift) or when model calibration degrades (concept drift), and signal when retraining is needed.

## Serves Goals
- Long-term accuracy maintenance
- Prevents silent model degradation

## Inputs
- All `outputs/YYYY-MM-DD_HHMM_scored-conjunctions.json` files from the past 30 days
- `data/models/training_stats.json` — per-feature distribution statistics from training
- `data/imports/cdm/` in `conjunction-analysis-agent` — post-TCA outcomes for Brier score computation (if available)

## Process
1. Load and aggregate all scored conjunction JSON files from the past 30 days into a single DataFrame
2. Load `training_stats.json` — contains per-feature: mean, std, min, max, and 10 quantile bucket boundaries

3. **Population Stability Index (PSI) per feature:**
   For each of the 20 features:
   a. Bin the training data into 10 buckets using the stored quantile boundaries
   b. Map the recent inference data into those same buckets (count % in each bucket)
   c. Compute PSI:
      ```
      PSI = Σ (actual_pct - expected_pct) × ln(actual_pct / expected_pct)
      ```
      Handle zero-count buckets by substituting 0.001
   d. Interpret: PSI < 0.1 → STABLE; 0.1–0.2 → MONITOR; > 0.2 → RETRAIN

4. **Brier score trend (if outcome data available):**
   - Load any CDM files from `agents/conjunction-analysis-agent/data/imports/cdm/` with TCA that has already passed
   - For each historical event where TCA occurred and an official Pc is available, compare ML score vs realized outcome
   - Compute rolling 30-day Brier score
   - Compare vs `model_manifest.json` baseline Brier
   - If Brier increased by >0.02: flag as RETRAIN

5. Compile drift report:
   - Table of all 20 features with PSI values and stability status
   - Overall drift level: STABLE (all PSI < 0.1), MONITOR (any 0.1–0.2), RETRAIN_RECOMMENDED (any > 0.2)
   - Brier trend: STABLE / DEGRADING
   - Final recommendation: NO_ACTION / MONITOR / RETRAIN_RECOMMENDED

6. Write to `outputs/YYYY-MM-DD_model-drift-report.md`
7. Update `MEMORY.md` with PSI trend data
8. If RETRAIN_RECOMMENDED: write to journal with escalation flag

## Outputs
- `outputs/YYYY-MM-DD_model-drift-report.md` — full drift analysis with recommendation

## Quality Bar
- PSI must be computed for all 20 features
- Report must include a clear STABLE / MONITOR / RETRAIN_RECOMMENDED verdict
- Cannot recommend retrain based on <7 days of inference data (too little signal)

## Tools
- `scripts/monitor_drift.py`
- Libraries: `numpy`, `pandas`, `json`, `scikit-learn`

## Integration
- Run weekly by heartbeat (Monday 03:30 UTC)
- RETRAIN_RECOMMENDED in journal triggers `TRAIN_MODEL` skill on next monthly review
