# Skill: Propagate Orbits

## Purpose
Use SGP4/SDP4 to generate Cartesian ECI state vectors (position + velocity) for all catalog objects over a 72-hour forward window at regular time steps.

## Serves Goals
- Propagation coverage (100% of catalog objects have state vectors)
- Processing latency (<30 min total pipeline)

## Inputs
- Most recent `agents/tle-ingestion-agent/outputs/YYYY-MM-DD_HHMM_tle-catalog.json`
- `knowledge/SATELLITE_REGISTRY.md` — to confirm the 8 Turkish satellite NORAD IDs

## Process
1. Load the TLE catalog JSON. Abort if catalog timestamp is older than 8 hours.
2. Separate objects into two groups:
   - **LEO** (mean motion >= 3.0 rev/day): time step = 60 seconds, window = 72 hours → 4320 steps
   - **GEO** (mean motion < 3.0 rev/day): time step = 300 seconds, window = 72 hours → 864 steps
3. For each TLE, initialize an `sgp4.api.Satrec` object using `Satrec.twoline2rv(line1, line2)`
4. For each object and each time step: compute Julian date as `jd + fr` where `jd` = integer Julian day and `fr` = fractional day offset, then call `satrec.sgp4(jd, fr)` to get ECI position `[x, y, z]` km and velocity `[vx, vy, vz]` km/s
5. Handle SGP4 error codes:
   - Code 0: success
   - Code 1: mean motion < 0 (decayed orbit) — skip object, log NORAD ID
   - Code 2: eccentricity >= 1.0 (hyperbolic, escaped) — skip, log
   - Code 4: orbit decay — skip, log
   - Any other non-zero code: skip, log
6. Store position arrays as `(n_objects, n_timesteps, 3)` numpy float32 arrays
7. Store velocity arrays as `(n_objects, n_timesteps, 3)` numpy float32 arrays
8. Save to compressed numpy format:
   - `outputs/YYYY-MM-DD_HHMM_state-vectors-LEO.npz` containing `positions`, `velocities`, `norad_ids`, `time_grid_jd`
   - `outputs/YYYY-MM-DD_HHMM_state-vectors-GEO.npz` containing same fields for GEO objects
9. Write a JSON sidecar for each: NORAD IDs list, time grid start/stop/step, total objects, error count
10. Log to journal: objects propagated by band, error count and NORAD IDs with errors, processing time

## Outputs
- `outputs/YYYY-MM-DD_HHMM_state-vectors-LEO.npz` + `.json` sidecar
- `outputs/YYYY-MM-DD_HHMM_state-vectors-GEO.npz` + `.json` sidecar
- Journal entry with propagation summary

## Quality Bar
- SGP4 error rate must be below 5% of catalog — abort if exceeded
- All 8 Turkish satellites must have successful state vectors — log as critical if any fail
- Position arrays must cover the full 72-hour window with no gaps

## Tools
- `scripts/propagate_orbits.py` — SGP4 initialization, time grid generation, numpy array construction
- Libraries: `sgp4` (pip install sgp4), `numpy`, `json`, `datetime`

## Integration
- Output directly consumed by `SCREEN_CONJUNCTIONS` skill in the same cycle
- SGP4 error registry updated to `MEMORY.md` after 2+ occurrences of same NORAD ID failing
