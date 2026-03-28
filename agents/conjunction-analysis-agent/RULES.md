# Rules: Conjunction Analysis Agent

## Boundaries

### This agent CAN:
- Read from `agents/orbit-propagation-agent/outputs/` and `agents/tle-ingestion-agent/outputs/`
- Read CDM files from own `data/imports/cdm/`
- Read `knowledge/SATELLITE_REGISTRY.md` and own `MEMORY.md`
- Write TCA results, conjunction events, and ML feature files to own `outputs/`
- Update own `MEMORY.md` with covariance model and convergence learnings
- Log to `journal/entries/`

### This agent CANNOT:
- Fetch data from external sources (Space-Track CDMs must be provided by human to `data/imports/cdm/`)
- Skip covariance estimation — must use default model if CDM not available
- Use a hard-body radius below 10 m
- Modify other agents' files
- Overwrite existing output files

## Handoff Rules

### Hand off to HUMAN when:
- Any RED-tier event detected (Pc >= 1e-3) — log to journal immediately within same cycle
- TCA minimization fails to converge for >1% of candidates
- CDM cross-validation error is systematically >500 m (covariance model needs expert review)
- More than 3 simultaneous RED-tier events (unusual debris environment)

### Hand off to ORCHESTRATOR when:
- A new satellite class (e.g., CubeSat constellation) requires different hard-body radius
- Analytic Pc model needs upgrade (e.g., from Chan to Monte Carlo)

### Hand off to JOURNAL when:
- Each cycle completes (log tier distribution)
- Any RED or ORANGE event (downstream agents monitor journal for these)
- Covariance model used per object (CDM vs default)

## Shared Knowledge Rules
- Read `knowledge/SATELLITE_REGISTRY.md` for hard-body radii and satellite names
- Never write to `knowledge/` files
- Log RED/ORANGE events to journal immediately — do not wait for end-of-cycle summary

## Sync Safety
- All outputs date-prefixed: `YYYY-MM-DD_HHMM_*.{json,parquet}`
- Never overwrite
- Scripts must be idempotent
