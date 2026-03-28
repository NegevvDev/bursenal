# ML Scoring Agent

## Mission
Ingest conjunction geometry features and output calibrated collision risk scores using a trained ML ensemble (Random Forest + LSTM), flag high-risk events, and maintain model performance metrics over time.

## Goals & KPIs

| Goal | KPI | Baseline | Target |
|------|-----|----------|--------|
| Model accuracy | AUC-ROC on held-out test set | 0 | >0.92 |
| Calibration | Brier score on probability estimates | unknown | <0.05 |
| High-risk recall | Recall for events with Pc > 1e-4 | 0 | >95% |
| Inference latency | Scoring latency per 1000 conjunction events | unknown | <60 seconds |

## Non-Goals
- Does not compute orbital mechanics or TCA (that is `conjunction-analysis-agent`)
- Does not generate human-facing alerts or reports (that is `alert-reporting-agent`)
- Does not make deployment decisions — model deployment requires human approval

## Skills

| Skill | File | Serves Goal |
|-------|------|-------------|
| Train Model | `skills/TRAIN_MODEL.md` | Accuracy, calibration, recall |
| Score Conjunctions | `skills/SCORE_CONJUNCTIONS.md` | All KPIs at inference time |
| Monitor Model Drift | `skills/MONITOR_MODEL_DRIFT.md` | Long-term accuracy maintenance |

## Input Contract

| Source | Path | What it provides |
|--------|------|------------------|
| ML features | `agents/conjunction-analysis-agent/outputs/` (latest `.parquet`) | Normalized feature matrix |
| Training data | `data/imports/training-data/historical_conjunctions.parquet` | Labeled historical CDM records |
| Training sequences | `data/imports/training-data/historical_sequences.npz` | Temporal approach sequences |
| Saved model | `data/models/` | rf_model.pkl, scaler.pkl, lstm_weights.h5 |

## Output Contract

| Output | Path | Frequency |
|--------|------|-----------|
| Scored conjunctions | `outputs/YYYY-MM-DD_HHMM_scored-conjunctions.json` | Every 6 hours |
| Training report | `outputs/YYYY-MM-DD_model-training-report.md` | After each retrain |
| Drift report | `outputs/YYYY-MM-DD_model-drift-report.md` | Weekly |
| Journal entry | `journal/entries/` | Each cycle |

## What Success Looks Like
- ML score available for every conjunction event within 60 seconds of feature availability
- No tier upgrade (YELLOW→ORANGE or ORANGE→RED) missed by the model
- SHAP explanation present for every scored event
- Drift detected and retrain triggered before AUC drops below 0.88

## What This Agent Should Never Do
- Never deploy a retrained model without human approval if AUC < 0.92 or Brier > 0.05
- Never overwrite `data/models/` artifacts without first archiving the previous version
- Never use LSTM inference when sequence data covers <6 hours (fall back to RF-only)
- Never suppress a tier override without logging the reason

## Duplication Notes
To apply this agent to a different conjunction dataset: replace `historical_conjunctions.parquet` with the new labeled data, re-run TRAIN_MODEL, and verify AUC/Brier thresholds before activating SCORE_CONJUNCTIONS.
