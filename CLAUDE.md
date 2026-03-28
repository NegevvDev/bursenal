# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This System Is

**Yörünge Temizliği** — a space debris collision risk tracking system for 8 Turkish satellites. Built as a markdown-native multi-agent framework: agents are defined in markdown files, share context through a shared journal, and are executed manually or on a 6-hour cron schedule.

Monitored satellites (from `knowledge/SATELLITE_REGISTRY.md`):

| Satellite | NORAD | Orbit | Operator |
|-----------|-------|-------|----------|
| Türksat 4A/4B/5A/5B | 39522, 40985, 47790, 49077 | GEO ~35,786 km | Türksat A.Ş. |
| GÖKTÜRK-1 | 41875 | LEO ~681 km | Milli Savunma |
| GÖKTÜRK-2 | 38704 | LEO ~686 km | TÜBİTAK UZAY |
| RASAT | 37791 | LEO ~689 km | TÜBİTAK UZAY |
| İMECE | 55491 | LEO ~680 km | ROKETSAN |

## Pipeline Execution Order

Scripts must run in this order each cycle. Each script auto-discovers the latest output file from the previous step via `glob` + `max(key=mtime)`.

```bash
# 1. Fetch TLE catalog from Space-Track.org
python agents/tle-ingestion-agent/scripts/fetch_tles.py
# → agents/tle-ingestion-agent/outputs/YYYY-MM-DD_HHMM_tle-catalog.json

# 2. SGP4 propagation (72h window) + coarse conjunction screening
python agents/orbit-propagation-agent/scripts/propagate_orbits.py
python agents/orbit-propagation-agent/scripts/screen_conjunctions.py
# → conjunction-candidates.json (pairs within 50 km LEO / 200 km GEO)

# 3. TCA refinement + Chan analytic Pc + ML feature extraction
python agents/conjunction-analysis-agent/scripts/compute_tca.py
python agents/conjunction-analysis-agent/scripts/compute_pc.py
python agents/conjunction-analysis-agent/scripts/extract_features.py
# → conjunction-events.json, ml-features.parquet

# 4. ML ensemble scoring + SHAP explanations
python agents/ml-scoring-agent/scripts/score_conjunctions.py
# → scored-conjunctions.json

# 5. Tiered alerts + weekly report
python agents/alert-reporting-agent/scripts/generate_alerts.py
python agents/alert-reporting-agent/scripts/weekly_report.py  # Mondays only
# → alerts.md, weekly-report.md
```

## Credentials Setup

`agents/tle-ingestion-agent/data/imports/credentials.env` — **never committed**:
```
SPACETRACK_USER=email@example.com
SPACETRACK_PASS=password
```
Free account at https://www.space-track.org/auth/createAccount. Without this file the TLE fetch fails (CelesTrak was removed due to 403 errors).

## Python Environment

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
```

Key packages: `sgp4`, `numpy`, `scipy`, `scikit-learn`, `xgboost`, `tensorflow`, `joblib`, `shap`, `pandas`, `pyarrow`, `requests`.

## ML Pipeline

### Feature Set (21 features)

Defined in `agents/ml-scoring-agent/data/models/model_meta.json` → `feature_keys`. Computed by two separate scripts with **different** feature sets:

- **`extract_features.py`** (conjunction-analysis-agent): 20 features including `log10_pc_analytic`, `primary_sma_km`, `tca_urgency`, `velocity_miss_product`, `orbital_similarity_score` — outputs to `.parquet`, used by `score_conjunctions.py`
- **`generate_training_data.py`** (ml-scoring-agent): 21 features using TLE line2 parsing directly (`tk_inclination`, `tk_eccentricity`, `tk_altitude_km`, etc.) — used only for training data generation

These two feature sets are **not interchangeable**. `score_conjunctions.py` reads the `.parquet` from `extract_features.py`.

### Models

All stored in `agents/ml-scoring-agent/data/models/`:

| File | Description |
|------|-------------|
| `rf_model.pkl` | Random Forest (200 trees, max_depth=7) — primary model |
| `xgb_model.pkl` | XGBoost (300 trees, lr=0.05) |
| `scaler.pkl` | StandardScaler fit on training data |
| `lstm_model.h5` | Keras LSTM (64→32→3 classes, seq_len=5) — trained on Colab GPU |
| `model_meta.json` | Feature keys, AUC scores, trained_at timestamp |
| `model_manifest.json` | Must have `"status": "approved"` for inference to run |

Ensemble weights: RF×0.6 + XGB×0.4 (tabular), then ×0.7 + LSTM×0.3 (if LSTM available).

### Training

```bash
# Generate training data from latest conjunction-events + tle-catalog
python agents/ml-scoring-agent/scripts/generate_training_data.py
# → rf_training_data.json (5445 records: 445 real + 5000 synthetic)
# → lstm_sequences.json (3970 sequences, seq_len=5)

# Train RF + XGBoost ensemble locally
python agents/ml-scoring-agent/scripts/train_model.py
# → rf_model.pkl, xgb_model.pkl, scaler.pkl, model_meta.json

# Train LSTM on Colab GPU (use train_lstm.py, BASE_DIR='/content/bursenal')
# → lstm_model.h5 (place in agents/ml-scoring-agent/data/models/)
```

After training, set `"status": "approved"` in `model_manifest.json` to enable inference.

### Tier Thresholds

Severity tiers are assigned by **worst of** analytic Pc tier and miss distance tier:

| Tier | Analytic Pc | Miss Distance |
|------|-------------|---------------|
| RED | ≥ 1e-3 | < 1 km AND velocity ≥ 1 km/s |
| ORANGE | ≥ 1e-4 | < 3 km AND velocity ≥ 1 km/s |
| YELLOW | ≥ 1e-6 | < 8 km |
| GREEN | < 1e-6 | ≥ 8 km |

ML tier thresholds (score = 1 − P(GREEN)): RED≥0.50, ORANGE≥0.10, YELLOW≥0.001.

## How Agents Work

Each agent under `agents/` has:

| File | Purpose |
|------|---------|
| `AGENT.md` | Mission, KPIs, skills, input/output contracts |
| `HEARTBEAT.md` | 6h schedule + 4-step cycle: read → assess → execute → log |
| `MEMORY.md` | Agent-local learnings, updated in-place only |
| `RULES.md` | Boundaries and escalation triggers |
| `skills/SKILL_NAME.md` | Step-by-step process per skill |

To run an agent manually: read its `HEARTBEAT.md`, follow the cycle, write a dated entry to `journal/entries/`.

## Key Conventions

- Output files: `YYYY-MM-DD_HHMM_description.json` — never overwrite, always new dated file
- Journal entries: `YYYY-MM-DD_HHMM.md` → `journal/entries/`
- **Agents never write to `knowledge/`** — propose changes via journal entry
- **`MEMORY.md` is the only file agents update in-place**
- Scripts discover input files automatically — no hardcoded paths except `BASE_DIR` in Colab scripts

## Data Flow

```
Space-Track.org
    └─▶ fetch_tles.py → tle-catalog.json
            └─▶ propagate_orbits.py + screen_conjunctions.py → conjunction-candidates.json
                    └─▶ compute_tca.py + compute_pc.py + extract_features.py → ml-features.parquet
                                └─▶ score_conjunctions.py → scored-conjunctions.json
                                            └─▶ generate_alerts.py → alerts.md

knowledge/           ← static, read-only
journal/entries/     ← shared, append-only
agents/*/MEMORY.md   ← private per-agent, in-place updates only
agents/*/outputs/    ← dated output files
agents/*/data/imports/ ← human-provided input (credentials, CDMs, training data)
```

## Creating a New Agent

Follow `NEW_AGENT_BOOTSTRAP.md` (9 steps): copy `agents/standard-agent/`, fill `AGENT.md`, write skill files, define heartbeat, set `RULES.md`, register in `AGENT_REGISTRY.md`, verify with `AGENT_CREATION_CHECKLIST.md`.

## Parallel History Fetch (Space-Track Rate Limits)

For fetching historical GP data at scale, 4 separate scripts split the NORAD ID range across 4 Space-Track accounts:

```
scripts/fetch_history_part1.py  → NORAD 634–30826    (negevvdev@gmail.com)
scripts/fetch_history_part2.py  → NORAD 30827–53934  (22kirimliumut@gmail.com)
scripts/fetch_history_part3.py  → NORAD 53935–61977  (egekaya804@gmail.com)
scripts/fetch_history_part4.py  → NORAD 61978–89494  (mericardavaran@gmail.com)
scripts/merge_history.py        → merges 4 outputs into gp_history_merged.json
```

Each script sleeps 1s between requests; backs off 60s on HTTP 429.
