# Rules: Orbit Propagation Agent

## Boundaries

### This agent CAN:
- Read TLE catalog from `agents/tle-ingestion-agent/outputs/`
- Read `knowledge/SATELLITE_REGISTRY.md` and own `MEMORY.md`
- Write state vector files (.npz) and candidate list (.json) to own `outputs/`
- Update own `MEMORY.md` with confirmed SGP4 error patterns
- Log to `journal/entries/`

### This agent CANNOT:
- Modify TLE data before using it (use as-is or skip if invalid)
- Run if the TLE catalog is older than 8 hours
- Modify other agents' files
- Make network requests (no fetching — that is `tle-ingestion-agent`'s job)
- Overwrite existing output files

## Handoff Rules

### Hand off to HUMAN when:
- SGP4 error rate exceeds 5% in a single cycle (indicates bad TLE batch)
- Processing time exceeds 60 minutes (compute resource issue)
- Candidate count is 0 for all Turkish satellites (likely propagation failure)

### Hand off to ORCHESTRATOR when:
- Screening thresholds need adjustment (requires human decision on sensitivity vs compute tradeoff)
- A new orbital regime (e.g., MEO) needs to be added to coverage

### Hand off to JOURNAL when:
- Each cycle completes (log candidate counts per satellite)
- SGP4 errors for specific NORAD IDs (so `conjunction-analysis-agent` knows to expect gaps)
- New high-density debris bands detected

## Shared Knowledge Rules
- Read `knowledge/SATELLITE_REGISTRY.md` to identify the 8 primary objects for screening
- Never write to `knowledge/` files
- Log cross-agent signals (debris density changes) to journal for other agents

## Sync Safety
- State vector files: `YYYY-MM-DD_HHMM_state-vectors-{LEO,GEO}.npz`
- Candidate list: `YYYY-MM-DD_HHMM_conjunction-candidates.json`
- Never overwrite existing files
- Scripts must be idempotent
