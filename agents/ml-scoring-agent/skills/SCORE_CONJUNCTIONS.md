# Skill: Score Conjunctions

## Purpose
Run trained ML model inference on the current conjunction feature matrix to produce calibrated collision risk scores, generate SHAP explanations, and assign final severity tiers.

## Serves Goals
- All KPIs at inference time: accuracy, calibration, recall, latency

## Inputs
- Most recent `agents/conjunction-analysis-agent/outputs/YYYY-MM-DD_HHMM_ml-features.parquet`
- `data/models/rf_model.pkl`, `scaler.pkl`, `lstm_weights.h5`, `model_manifest.json`

## Process
1. Load feature parquet file. Verify all 20 feature columns are present.
2. Load `model_manifest.json` to confirm a human-approved model is available. If `status != "approved"`: fall back to analytic Pc tier only, log warning.
3. Load `rf_model.pkl` and `scaler.pkl`. If scaler was not applied during feature extraction (check `normalized` flag column): apply scaler now.
4. Run Random Forest inference: `rf_proba = rf_model.predict_proba(X)[:, 1]` — calibrated probabilities
5. If `lstm_weights.h5` exists and the feature parquet contains temporal sequence columns: load LSTM model, run inference, get `lstm_proba`. Else set `lstm_available = False`.
6. Compute ensemble score:
   - If LSTM available: `final_score = 0.7 × rf_proba + 0.3 × lstm_proba`
   - If LSTM unavailable: `final_score = rf_proba`
7. Assign ML severity tier using the same Pc thresholds mapped to ML score: GREEN < 0.001, YELLOW 0.001–0.1, ORANGE 0.1–0.5, RED ≥ 0.5 (these thresholds are calibrated to match the Pc tier boundaries based on training data)
8. Compare ML tier vs analytic tier from feature matrix. If they differ by ≥ 1 tier level:
   - Flag as `tier_override: true`
   - Set `final_tier` = ML tier (ML takes precedence — it uses more features than analytic Pc)
   - Log override reason: "ML score {score:.3f} exceeds analytic tier boundary"
9. Compute SHAP values using `shap.TreeExplainer(rf_model)`. For each event, identify the top 3 features by absolute SHAP value. Store as `top_shap_features: [{feature, value, shap_value}]`.
10. Build output record per event: `event_id`, `turkish_satellite_name`, `debris_norad_id`, `tca_utc`, `miss_distance_km`, `relative_velocity_km_s`, `analytic_pc`, `ml_score`, `final_tier`, `tier_override`, `lstm_used`, `model_version`, `top_shap_features`
11. Write to `outputs/YYYY-MM-DD_HHMM_scored-conjunctions.json`
12. Log to journal: tier distribution (RED/ORANGE/YELLOW/GREEN counts), override count, inference latency, model version

## Outputs
- `outputs/YYYY-MM-DD_HHMM_scored-conjunctions.json` — fully scored events ready for alerting

## Quality Bar
- Every event must have a `final_tier` assignment — no null tiers
- SHAP explanation must be present for every ORANGE and RED event
- Latency must be <60 seconds for up to 1000 events
- Any RED events must also appear in the journal log entry for this cycle

## Tools
- `scripts/score_conjunctions.py`
- Libraries: `scikit-learn`, `joblib`, `shap`, `tensorflow`/`keras`, `numpy`, `pandas`, `json`, `pyarrow`

## Integration
- Output consumed by `alert-reporting-agent`'s `GENERATE_ALERTS` skill
- RED events in journal trigger out-of-schedule alert generation
