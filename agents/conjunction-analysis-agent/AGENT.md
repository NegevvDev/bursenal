# Conjunction Analysis Agent

## Mission
Compute precise conjunction geometry (TCA, miss distance, relative velocity) and analytic collision probability (Pc) for every screened candidate pair, then extract the ML feature matrix needed by the downstream risk scoring agent.

## Goals & KPIs

| Goal | KPI | Baseline | Target |
|------|-----|----------|--------|
| Geometric accuracy | Miss distance error vs Space-Track CDM data | unknown | <100 m |
| TCA accuracy | TCA timing error vs Space-Track CDMs | unknown | <60 seconds |
| Event completeness | % of Space-Track CDMs reproduced | 0% | >90% |
| Throughput | Conjunction events analyzed per cycle | 0 | >1000 |

## Non-Goals
- Does not fetch TLE data or propagate full catalogs
- Does not train or run ML models (that is `ml-scoring-agent`)
- Does not generate alerts or reports

## Skills

| Skill | File | Serves Goal |
|-------|------|-------------|
| Compute TCA | `skills/COMPUTE_TCA.md` | Geometric accuracy, TCA accuracy |
| Compute Pc | `skills/COMPUTE_PC.md` | Event completeness |
| Extract ML Features | `skills/EXTRACT_ML_FEATURES.md` | Feeds ml-scoring-agent |

## Input Contract

| Source | Path | What it provides |
|--------|------|------------------|
| Conjunction candidates | `agents/orbit-propagation-agent/outputs/` (latest) | Screened object pairs + coarse TCA time index |
| TLE catalog | `agents/tle-ingestion-agent/outputs/` (latest) | TLEs needed for fine re-propagation |
| CDM archive | `data/imports/cdm/` | Real covariance data from Space-Track (optional) |
| Satellite registry | `knowledge/SATELLITE_REGISTRY.md` | Hard-body radii per satellite |

## Output Contract

| Output | Path | Frequency |
|--------|------|-----------|
| TCA results | `outputs/YYYY-MM-DD_HHMM_tca-results.json` | Every 6 hours |
| Conjunction events | `outputs/YYYY-MM-DD_HHMM_conjunction-events.json` | Every 6 hours |
| ML features | `outputs/YYYY-MM-DD_HHMM_ml-features.parquet` | Every 6 hours |
| Journal entry | `journal/entries/` | Each cycle |

## What Success Looks Like
- TCA computed to sub-minute accuracy for all candidate pairs
- Chan Pc values reproduced within an order of magnitude of official CDMs
- ML feature matrix complete with no null fields for any conjunction event
- Severity tier assigned (GREEN/YELLOW/ORANGE/RED) to every event

## What This Agent Should Never Do
- Never skip covariance estimation — use default model if CDM covariance is unavailable
- Never use a hard-body radius below 10 m (physical minimum for tracked objects)
- Never output a feature matrix with unnormalized values — scaler must be applied before writing

## Duplication Notes
To adjust covariance defaults: edit the `DEFAULT_COVARIANCE` dict in `scripts/compute_pc.py`. The diagonal values represent 1-sigma position uncertainty in the RSW frame (radial, in-track, cross-track).
