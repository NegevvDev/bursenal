# Agent Registry

Master list of all agents in this workspace.

## Yörünge Temizliği — Space Debris Tracking Pipeline

Sub-agent system for detecting conjunction risks near Turkish satellites using ML.

| Agent | Folder | Mission | Skills | Heartbeat | Status |
|-------|--------|---------|--------|-----------|--------|
| TLE Ingestion | `agents/tle-ingestion-agent/` | Fetch & validate TLE data from CelesTrak and Space-Track | TLE_FETCH, TLE_VALIDATE | Every 6h (00:00 UTC) | NOT_ACTIVATED |
| Orbit Propagation | `agents/orbit-propagation-agent/` | SGP4 propagation + coarse conjunction screening | PROPAGATE_ORBITS, SCREEN_CONJUNCTIONS | Every 6h (00:15 UTC) | NOT_ACTIVATED |
| Conjunction Analysis | `agents/conjunction-analysis-agent/` | Precise TCA, analytic Pc, ML feature extraction | COMPUTE_TCA, COMPUTE_PC, EXTRACT_ML_FEATURES | Every 6h (00:30 UTC) | NOT_ACTIVATED |
| ML Scoring | `agents/ml-scoring-agent/` | RF+LSTM risk scoring, SHAP explanations, drift monitoring | TRAIN_MODEL, SCORE_CONJUNCTIONS, MONITOR_MODEL_DRIFT | Every 6h (00:45 UTC) | NOT_ACTIVATED |
| Alert Reporting | `agents/alert-reporting-agent/` | Tiered alerts + weekly situation reports | GENERATE_ALERTS, WEEKLY_REPORT | Every 6h (01:00 UTC) + Monday 08:00 weekly | NOT_ACTIVATED |

Pipeline: `tle-ingestion-agent → orbit-propagation-agent → conjunction-analysis-agent → ml-scoring-agent → alert-reporting-agent`

See `orchestrator/YORUNGE-TEMIZLIGI-STATUS.md` for activation checklist.

## Template Agents

| Agent | Folder | Purpose |
|-------|--------|---------|
| Standard Template | `agents/standard-agent/` | Copy this to create any new agent |
