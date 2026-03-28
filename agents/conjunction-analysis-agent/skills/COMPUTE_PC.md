# Skill: Compute Pc

## Purpose
Compute analytic probability of collision (Pc) for each conjunction event using the Chan formula with position uncertainty covariance, and assign a severity tier (GREEN/YELLOW/ORANGE/RED).

## Serves Goals
- Event completeness (>90% of Space-Track CDMs reproduced)
- Feeds ml-scoring-agent with analytic baseline for comparison

## Inputs
- `outputs/YYYY-MM-DD_HHMM_tca-results.json` (from `COMPUTE_TCA` skill)
- `data/imports/cdm/` — Space-Track CDM files (if available; provides real covariance)
- `knowledge/SATELLITE_REGISTRY.md` — hard-body radius per satellite

## Process
1. Load TCA results and satellite registry
2. For each conjunction event, determine covariance source:
   - If a CDM file exists in `data/imports/cdm/` for this object pair with TCA within 6 hours of the CDM event time: extract covariance components from the CDM
   - Otherwise: use default diagonal covariance model (1-sigma values in RSW frame):
     - LEO debris: σ_radial = 0.1 km, σ_intrack = 1.0 km, σ_crosstrack = 0.1 km
     - GEO debris: σ_radial = 0.5 km, σ_intrack = 5.0 km, σ_crosstrack = 0.5 km
3. Combine primary and secondary covariances: `C_combined = C_primary + C_secondary` in RSW frame
4. Rotate combined covariance to the miss plane (plane perpendicular to relative velocity at TCA):
   - Compute miss plane axes: `ê_miss = (r2-r1)/|r2-r1|`, `ê_vel = (v2-v1)/|v2-v1|`, `ê_perp = ê_vel × ê_miss`
   - Project `C_combined` onto (ê_miss, ê_perp) plane to get 2×2 covariance matrix `C_2d`
5. Compute eigenvalues `λ1, λ2` of `C_2d`, set `σ_u = √λ1`, `σ_v = √λ2`
6. Project miss vector onto miss plane eigenvectors to get `(x_miss, y_miss)` in standard basis
7. Retrieve hard-body radius (HBR) from satellite registry: GEO Türksat satellites: 30 m; LEO GÖKTÜRK/RASAT/İMECE: 20 m
8. Compute Chan analytic Pc:
   ```
   Pc = (π × HBR²) / (2π × σ_u × σ_v) × exp(-0.5 × ((x_miss/σ_u)² + (y_miss/σ_v)²))
   ```
   Note: this is the Gaussian approximation, valid when HBR << σ (true for all typical conjunction geometries)
9. Assign severity tier:
   - GREEN: Pc < 1e-6
   - YELLOW: 1e-6 ≤ Pc < 1e-4
   - ORANGE: 1e-4 ≤ Pc < 1e-3
   - RED: Pc ≥ 1e-3
10. Write conjunction events to `outputs/YYYY-MM-DD_HHMM_conjunction-events.json` including: all TCA fields, Pc, severity_tier, covariance_source (CDM or DEFAULT), HBR used
11. Log to journal: event counts by tier, any RED/ORANGE events with brief details

## Outputs
- `outputs/YYYY-MM-DD_HHMM_conjunction-events.json` — full conjunction event records with Pc and tier

## Quality Bar
- Pc must be computed for 100% of TCA results — no null values allowed
- Every RED event must appear in the journal entry for this cycle (not just in the file)
- Chan formula accuracy: reproduce CDM Pc within one order of magnitude for events with real covariance data

## Tools
- `scripts/compute_pc.py` — covariance loading, miss plane projection, Chan Pc computation, tier assignment
- Libraries: `numpy`, `scipy`, `json`, `datetime`

## Integration
- Output feeds into `EXTRACT_ML_FEATURES` in same cycle
- RED/ORANGE events trigger immediate journal notification for `alert-reporting-agent`
