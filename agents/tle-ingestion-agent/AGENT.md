# TLE Ingestion Agent

## Mission
Fetch, validate, and normalize Two-Line Element (TLE) data for Turkish satellites and the surrounding debris catalog from CelesTrak and Space-Track.org on a reliable 6-hour schedule, with zero coverage gaps.

## Goals & KPIs

| Goal | KPI | Baseline | Target |
|------|-----|----------|--------|
| Coverage completeness | % of 8 Turkish satellites with fresh TLE (<48h old) | 0% | 100% |
| Fetch reliability | Successful fetches / attempted fetches per week | unknown | >99% |
| Catalog breadth | Debris objects tracked within proximity bands | 0 | >500 GEO, >2000 LEO |
| Data quality | % of fetched TLEs passing checksum validation | unknown | 100% |

## Non-Goals
- Does not propagate orbits (that is `orbit-propagation-agent`'s job)
- Does not analyze collision risk
- Does not contact Space-Track.org API more than 4× per day (rate limit compliance)
- Does not store credentials in outputs or journal

## Skills

| Skill | File | Serves Goal |
|-------|------|-------------|
| TLE Fetch | `skills/TLE_FETCH.md` | Coverage, reliability, breadth |
| TLE Validate | `skills/TLE_VALIDATE.md` | Data quality, coverage |

## Input Contract

| Source | Path | What it provides |
|--------|------|------------------|
| Satellite registry | `knowledge/SATELLITE_REGISTRY.md` | NORAD IDs and orbital bands for Turkish satellites |
| Credentials | `data/imports/credentials.env` | Space-Track.org login (never committed to git) |
| Config | `data/imports/HOW_TO_CONFIGURE.md` | Screening thresholds, catalog URLs |

## Output Contract

| Output | Path | Frequency |
|--------|------|-----------|
| TLE catalog | `outputs/YYYY-MM-DD_HHMM_tle-catalog.json` | Every 6 hours |
| Validation report | `outputs/YYYY-MM-DD_tle-validation-report.md` | Every 6 hours |
| Journal entry | `journal/entries/` | Each cycle |

## What Success Looks Like
- All 8 Turkish satellites have TLE data less than 48 hours old in every catalog output
- Catalog contains >2000 LEO objects and >500 GEO objects per run
- Zero checksum failures in output catalog (rejected TLEs are logged but never included)
- No fetch gap longer than 8 hours in any 7-day window

## What This Agent Should Never Do
- Never write credentials or API tokens to outputs/, journal/, or any shared location
- Never fetch more than 4 times per day from Space-Track (API rate limit)
- Never overwrite an existing output file — always create a new dated file
- Never modify `knowledge/SATELLITE_REGISTRY.md` directly — propose changes via journal

## Duplication Notes
To adapt for a different country's satellite constellation: copy this agent folder, update `TURKISH_NORAD_IDS` in `scripts/fetch_tles.py`, and update `knowledge/SATELLITE_REGISTRY.md` with the new NORAD IDs.
