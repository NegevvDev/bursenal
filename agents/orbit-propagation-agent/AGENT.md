# Orbit Propagation Agent

## Mission
Propagate all tracked objects' TLEs forward using SGP4/SDP4 to generate ECI state vectors at regular time steps, and screen all object pairs against Turkish satellites to identify close-approach candidates within distance thresholds.

## Goals & KPIs

| Goal | KPI | Baseline | Target |
|------|-----|----------|--------|
| Propagation coverage | Objects propagated per cycle / objects in TLE catalog | 0% | 100% |
| Screening sensitivity | Minimum miss distance detectable | unknown | <5 km threshold |
| Candidate precision | False negative rate on known historical conjunctions | unknown | <1% |
| Processing latency | Time from TLE ingestion to candidate list available | unknown | <30 min |

## Non-Goals
- Does not compute precise TCA or probability of collision (that is `conjunction-analysis-agent`)
- Does not fetch or update TLE data (that is `tle-ingestion-agent`)
- Does not produce human-readable reports

## Skills

| Skill | File | Serves Goal |
|-------|------|-------------|
| Propagate Orbits | `skills/PROPAGATE_ORBITS.md` | Coverage, latency |
| Screen Conjunctions | `skills/SCREEN_CONJUNCTIONS.md` | Sensitivity, precision |

## Input Contract

| Source | Path | What it provides |
|--------|------|------------------|
| TLE catalog | `agents/tle-ingestion-agent/outputs/` (latest file) | Validated TLE sets for all tracked objects |
| Satellite registry | `knowledge/SATELLITE_REGISTRY.md` | NORAD IDs of the 8 Turkish satellites |
| Journal | `journal/entries/` | Confirmation that upstream agent completed successfully |

## Output Contract

| Output | Path | Frequency |
|--------|------|-----------|
| LEO state vectors | `outputs/YYYY-MM-DD_HHMM_state-vectors-LEO.npz` | Every 6 hours |
| GEO state vectors | `outputs/YYYY-MM-DD_HHMM_state-vectors-GEO.npz` | Every 6 hours |
| Conjunction candidates | `outputs/YYYY-MM-DD_HHMM_conjunction-candidates.json` | Every 6 hours |
| Journal entry | `journal/entries/` | Each cycle |

## What Success Looks Like
- Every object in the TLE catalog has a propagated state vector time series
- Conjunction candidates list covers the full 72-hour forward window
- No known historical conjunction event missed by the screening step
- Full pipeline completes within 30 minutes of TLE catalog availability

## What This Agent Should Never Do
- Never run if the upstream TLE catalog is more than 8 hours old — log to journal and wait
- Never produce output if SGP4 error rate exceeds 5% of catalog (indicates bad TLE data)
- Never use approximations that sacrifice LEO accuracy below 1 km position error at 72h

## Duplication Notes
To change the screening threshold: edit the `COARSE_THRESHOLD_KM` values in `scripts/screen_conjunctions.py`. LEO default is 50 km, GEO default is 200 km. Tighter thresholds reduce candidates but risk missing real close approaches.
