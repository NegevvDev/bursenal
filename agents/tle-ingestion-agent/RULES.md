# Rules: TLE Ingestion Agent

## Boundaries

### This agent CAN:
- Read from `knowledge/SATELLITE_REGISTRY.md` and own `MEMORY.md`
- Fetch from CelesTrak and Space-Track.org (max 4 requests/day to Space-Track)
- Write dated TLE catalog and validation reports to own `outputs/`
- Update own `MEMORY.md` with confirmed source reliability patterns
- Log to `journal/entries/`
- Read credentials from `data/imports/credentials.env`

### This agent CANNOT:
- Write credentials or tokens to any shared location
- Exceed 4 Space-Track.org API requests per 24-hour period
- Modify `knowledge/` files directly
- Modify other agents' files
- Overwrite an existing output file (always create new dated file)
- Publish or forward data to external systems

## Handoff Rules

### Hand off to HUMAN when:
- Any Turkish satellite TLE is older than 72 hours (Space-Track failure or satellite maneuver)
- Space-Track authentication fails for 2+ consecutive cycles
- Catalog size drops >20% vs previous week (unusual — possible source outage)
- `credentials.env` file is missing or has invalid format

### Hand off to ORCHESTRATOR when:
- New satellite is added to the Turkish fleet and NORAD ID must be sourced
- A different data source (e.g., ESA DISCOS) needs to be integrated

### Hand off to JOURNAL when:
- Fetch succeeds (log catalog summary every cycle)
- A source had degraded reliability this cycle (so downstream agents are warned)
- A Turkish satellite appears to be maneuver-active (TLE epoch jumps)

## Shared Knowledge Rules
- Read `knowledge/SATELLITE_REGISTRY.md` at every cycle start
- Never write to `knowledge/` — propose NORAD ID corrections via journal entry
- Only update own `MEMORY.md` for agent-local learnings

## Sync Safety
- All output files: `YYYY-MM-DD_HHMM_tle-catalog.json` and `YYYY-MM-DD_tle-validation-report.md`
- Never overwrite — always create a new dated file
- `MEMORY.md` is the only file this agent updates in-place
- `fetch_tles.py` and `validate_tles.py` must be idempotent (safe to re-run any time)
