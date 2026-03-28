# Skill: Compute TCA

## Purpose
For each screened candidate pair, compute the Time of Closest Approach (TCA) with sub-minute accuracy by numerically minimizing the inter-object distance function over a fine time grid.

## Serves Goals
- Geometric accuracy (miss distance error <100 m)
- TCA accuracy (<60 seconds timing error)

## Inputs
- Most recent `agents/orbit-propagation-agent/outputs/YYYY-MM-DD_HHMM_conjunction-candidates.json`
- Most recent `agents/tle-ingestion-agent/outputs/YYYY-MM-DD_HHMM_tle-catalog.json` (for re-propagation)

## Process
1. Load the candidate pairs JSON and the TLE catalog
2. For each candidate pair:
   a. Retrieve TLE line1 and line2 for both objects from the catalog
   b. Initialize two `sgp4.api.Satrec` objects
   c. From the candidate's `coarse_tca_step_index`, compute the coarse TCA time as a Julian date
   d. Define a fine time grid: ±30 minutes around the coarse TCA, step = 5 seconds (720 steps)
   e. Propagate both objects at every fine time step
   f. Compute inter-object distance at each step: `dist = norm(r1 - r2)` in ECI frame
   g. Find the index of minimum distance → this is the refined coarse TCA
   h. Further refine using `scipy.optimize.minimize_scalar` with Brent's method, bounds = `(tca_coarse − 60s, tca_coarse + 60s)`, objective = inter-object distance function (calls SGP4 at each evaluation)
   i. This gives TCA precision to <1 second
3. At the refined TCA, compute:
   - `miss_distance_km`: Euclidean distance between positions in ECI
   - `relative_velocity_km_s`: magnitude of `v2 - v1` in ECI
   - RSW frame vectors for the Turkish satellite: R = r/|r| (radial), W = r×v/|r×v| (cross-track), S = W×R (in-track)
   - Project miss vector `(r2 - r1)` onto R, S, W to get:
     - `radial_miss_km`
     - `intrack_miss_km`
     - `crosstrack_miss_km`
4. Record `tca_utc` as ISO 8601 UTC string
5. Write all TCA results to `outputs/YYYY-MM-DD_HHMM_tca-results.json`
6. Log to journal: total TCA computations, any failures to converge, processing time

## Outputs
- `outputs/YYYY-MM-DD_HHMM_tca-results.json` — one record per candidate pair with full TCA geometry

## Quality Bar
- TCA minimization must converge for >99% of candidates
- RSW miss vector components must sum (in quadrature) to the total miss distance within 1 m numerical error
- Processing must complete within 20 minutes for up to 1000 candidates

## Tools
- `scripts/compute_tca.py` — fine grid propagation, Brent minimization, RSW frame computation
- Libraries: `sgp4`, `numpy`, `scipy`, `json`, `datetime`

## Integration
- Output feeds into `COMPUTE_PC` skill in same cycle
- Non-converging cases logged to `MEMORY.md` for investigation
