# Skill: Screen Conjunctions

## Purpose
Identify candidate object pairs where the minimum inter-object distance during the 72-hour window falls below a conservative screening threshold, without computing precise geometry.

## Serves Goals
- Screening sensitivity (no genuine close approach missed)
- Candidate precision (false negative rate <1%)

## Inputs
- `outputs/YYYY-MM-DD_HHMM_state-vectors-LEO.npz` and `.npz` sidecar (from `PROPAGATE_ORBITS` skill)
- `outputs/YYYY-MM-DD_HHMM_state-vectors-GEO.npz` and `.npz` sidecar
- `knowledge/SATELLITE_REGISTRY.md` — NORAD IDs of the 8 Turkish satellites

## Process
1. Load state vector arrays and sidecar files for both LEO and GEO
2. Identify the array indices for the 8 Turkish satellites by matching NORAD IDs from the sidecar
3. Apply conservative screening thresholds:
   - LEO objects: **50 km** between any debris object and a Turkish LEO satellite
   - GEO objects: **200 km** between any debris object and a Turkish GEO satellite
4. For each Turkish satellite and each time step, compute Euclidean distance to every other object in the same orbital band using vectorized numpy operations:
   ```
   diff = positions[all_objects, t, :] - positions[turkish_sat, t, :]  # (N, 3)
   dist = np.linalg.norm(diff, axis=1)  # (N,)
   ```
5. Across all time steps, take the minimum distance per (Turkish satellite, debris object) pair:
   ```
   min_dist = np.min(distances, axis=1)  # min over time axis
   ```
6. Collect all pairs where `min_dist < threshold`
7. For each candidate pair, record:
   - `turkish_norad_id`: NORAD ID of the Turkish satellite
   - `debris_norad_id`: NORAD ID of the debris object
   - `coarse_min_dist_km`: minimum distance found in screening
   - `coarse_tca_step_index`: time step index where minimum occurred
   - `orbital_band`: LEO or GEO
8. Write all candidate pairs to `outputs/YYYY-MM-DD_HHMM_conjunction-candidates.json`
9. Log to journal: total candidates, breakdown per Turkish satellite, processing duration

## Outputs
- `outputs/YYYY-MM-DD_HHMM_conjunction-candidates.json` — all screened candidate pairs

## Quality Bar
- No candidate where `min_dist < threshold/2` should be missing from the output (zero tolerance for missed close approaches)
- Cross-band screening is not required (LEO and GEO are processed independently)
- If screening produces >10,000 candidates, log a warning: may indicate catalog pollution or threshold too wide

## Tools
- `scripts/screen_conjunctions.py` — vectorized numpy distance computation
- Libraries: `numpy`, `json`, `datetime`

## Integration
- Output feeds directly into `conjunction-analysis-agent`'s `COMPUTE_TCA` skill
- Candidate count trends logged to `MEMORY.md` after 10+ cycles
