# Skill: Extract ML Features

## Purpose
Build the normalized feature matrix for ML scoring from raw conjunction geometry and orbital element data, engineering domain-specific interaction features.

## Serves Goals
- Enables `ml-scoring-agent` to score all conjunction events

## Inputs
- `outputs/YYYY-MM-DD_HHMM_conjunction-events.json` (from `COMPUTE_PC` skill)
- Most recent TLE catalog from `agents/tle-ingestion-agent/outputs/` (for orbital elements)
- `data/models/scaler.pkl` in `agents/ml-scoring-agent/data/models/` (for normalization; skip if not yet available)

## Process
1. Load conjunction events and TLE catalog
2. For each conjunction event, extract raw features:

   **Geometry features:**
   - `miss_distance_km`: from TCA computation
   - `relative_velocity_km_s`: from TCA computation
   - `radial_miss_km`, `intrack_miss_km`, `crosstrack_miss_km`: RSW miss components
   - `tca_hours_from_now`: `(tca_utc − current_utc).total_seconds() / 3600`
   - `pc_analytic`: Chan Pc from COMPUTE_PC (log10-transformed: `log10(max(Pc, 1e-12))`)

   **Turkish satellite orbital elements (re-computed from TLE using sgp4 mean elements):**
   - `primary_sma_km`: semi-major axis (km)
   - `primary_eccentricity`: eccentricity (0–1)
   - `primary_inclination_deg`: inclination (degrees)
   - `primary_raan_deg`: RAAN (degrees)

   **Debris object orbital elements:**
   - `secondary_sma_km`, `secondary_eccentricity`, `secondary_inclination_deg`, `secondary_raan_deg`

   **Object metadata:**
   - `object_type_encoded`: 0 = active satellite, 1 = rocket body, 2 = debris fragment (from SATCAT name heuristics: names containing "DEB" → 2, "R/B" → 1, else 0)
   - `tca_urgency`: `1 / (tca_hours_from_now + 1)` (higher = more imminent)

3. Engineer interaction features:
   - `velocity_miss_product`: `relative_velocity_km_s × miss_distance_km`
   - `delta_inclination_deg`: `abs(primary_inclination_deg − secondary_inclination_deg)`
   - `delta_sma_km`: `abs(primary_sma_km − secondary_sma_km)`
   - `orbital_similarity_score`: `1 / (1 + delta_inclination_deg/90 + delta_sma_km/10000)` — higher score means more similar orbital regime → persistent risk

4. Assemble feature matrix as pandas DataFrame with one row per conjunction event, columns = all features listed above (20 features total)
5. If `scaler.pkl` exists in `ml-scoring-agent/data/models/`: apply `StandardScaler.transform()` to normalize all features
6. If no scaler available: write un-normalized features with a flag column `normalized: false`
7. Write feature matrix to `outputs/YYYY-MM-DD_HHMM_ml-features.parquet` using pyarrow
8. Include metadata columns: `event_id` (hash of turkish_norad + debris_norad + tca_date), `turkish_norad_id`, `debris_norad_id`, `tca_utc`, `severity_tier`
9. Log to journal: features written, normalization applied (yes/no), count of events

## Outputs
- `outputs/YYYY-MM-DD_HHMM_ml-features.parquet` — normalized feature matrix ready for ML inference

## Quality Bar
- No null values in any feature column — fill missing orbital elements with orbital band median
- Feature matrix must include all 20 base + interaction features
- Each row must have a unique `event_id`

## Tools
- `scripts/extract_features.py` — feature engineering, scaler application, parquet output
- Libraries: `numpy`, `pandas`, `scikit-learn`, `pyarrow`, `sgp4`, `json`, `hashlib`

## Integration
- Output read by `ml-scoring-agent`'s `SCORE_CONJUNCTIONS` skill
- If scaler is missing, `ml-scoring-agent` must provide it after first model training
