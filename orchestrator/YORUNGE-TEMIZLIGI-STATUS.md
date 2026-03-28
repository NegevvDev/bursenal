# Yörünge Temizliği — Pipeline Status

Cross-agent pipeline status tracker for the space debris tracking system.
Updated by the orchestrator after reviewing journal entries each week.

## System Overview

```
[tle-ingestion-agent]
    ↓ outputs/YYYY-MM-DD_HHMM_tle-catalog.json
[orbit-propagation-agent]
    ↓ outputs/YYYY-MM-DD_HHMM_conjunction-candidates.json
[conjunction-analysis-agent]
    ↓ outputs/YYYY-MM-DD_HHMM_ml-features.parquet
[ml-scoring-agent]
    ↓ outputs/YYYY-MM-DD_HHMM_scored-conjunctions.json
[alert-reporting-agent]
    ↓ outputs/YYYY-MM-DD_HHMM_alerts.md + weekly-report.md
```

## Agent Status

| Agent | Status | Last Run | Notes |
|-------|--------|----------|-------|
| tle-ingestion-agent | NOT_ACTIVATED | — | Awaiting first run |
| orbit-propagation-agent | NOT_ACTIVATED | — | Awaiting first run |
| conjunction-analysis-agent | NOT_ACTIVATED | — | Awaiting first run |
| ml-scoring-agent | NOT_ACTIVATED | — | Awaiting training data |
| alert-reporting-agent | NOT_ACTIVATED | — | Awaiting upstream data |

## Activation Checklist

Before first run:
- [ ] Space-Track credentials added to `agents/tle-ingestion-agent/data/imports/credentials.env`
- [ ] NORAD IDs verified in `knowledge/SATELLITE_REGISTRY.md`
- [ ] Python dependencies installed: `pip install sgp4 numpy scipy scikit-learn imbalanced-learn tensorflow joblib shap pandas pyarrow requests`
- [ ] Training data sourced and placed in `agents/ml-scoring-agent/data/imports/training-data/`
- [ ] Model trained and human-approved (set `status: approved` in `model_manifest.json`)

## Phase 1 (Manual Operation)
Run agents manually in order:
1. `python agents/tle-ingestion-agent/scripts/fetch_tles.py`
2. `python agents/tle-ingestion-agent/scripts/validate_tles.py`
3. `python agents/orbit-propagation-agent/scripts/propagate_orbits.py`
4. `python agents/orbit-propagation-agent/scripts/screen_conjunctions.py`
5. `python agents/conjunction-analysis-agent/scripts/compute_tca.py`
6. `python agents/conjunction-analysis-agent/scripts/compute_pc.py`
7. `python agents/conjunction-analysis-agent/scripts/extract_features.py`
8. `python agents/ml-scoring-agent/scripts/score_conjunctions.py`
9. `python agents/alert-reporting-agent/scripts/generate_alerts.py`

## Current Priorities

1. Activate `tle-ingestion-agent` and confirm full Turkish satellite TLE coverage
2. Validate SGP4 propagation for GÖKTÜRK-2 and Türksat 4A (one LEO + one GEO)
3. Source historical CDM data for initial ML training
4. Run first end-to-end pipeline test
