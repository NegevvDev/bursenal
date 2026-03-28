# How to Export Training Data

The ML model requires labeled historical conjunction data. This file explains how to obtain and format it.

## Required Files

### 1. `historical_conjunctions.parquet`

A table of historical CDM (Conjunction Data Message) records, one row per conjunction event.

**Minimum required columns:**

| Column | Type | Description |
|--------|------|-------------|
| `miss_distance_km` | float | Miss distance at TCA (km) |
| `relative_velocity_km_s` | float | Relative velocity magnitude (km/s) |
| `radial_miss_km` | float | Radial component of miss vector (km) |
| `intrack_miss_km` | float | In-track component (km) |
| `crosstrack_miss_km` | float | Cross-track component (km) |
| `tca_hours_from_now` | float | Hours until TCA at time of CDM issuance |
| `log10_pc_analytic` | float | log10 of analytic Pc (e.g., -5 for Pc=1e-5) |
| `primary_sma_km` | float | Primary satellite semi-major axis (km) |
| `primary_eccentricity` | float | Primary eccentricity |
| `primary_inclination_deg` | float | Primary inclination (degrees) |
| `primary_raan_deg` | float | Primary RAAN (degrees) |
| `secondary_sma_km` | float | Secondary object SMA (km) |
| `secondary_eccentricity` | float | Secondary eccentricity |
| `secondary_inclination_deg` | float | Secondary inclination (degrees) |
| `secondary_raan_deg` | float | Secondary RAAN (degrees) |
| `object_type_encoded` | int | 0=active, 1=rocket body, 2=debris |
| `tca_urgency` | float | 1/(tca_hours+1) |
| `velocity_miss_product` | float | rel_vel × miss_dist |
| `delta_inclination_deg` | float | abs(primary_inc - secondary_inc) |
| `delta_sma_km` | float | abs(primary_sma - secondary_sma) |
| `orbital_similarity_score` | float | 1/(1 + delta_inc/90 + delta_sma/10000) |
| **`label`** | int | **1 = high-risk event (Pc > 1e-4), 0 = nominal** |

**How to obtain:**
1. Log in to Space-Track.org
2. Go to: https://www.space-track.org/basicspacedata/query/class/cdm_public/
3. Filter for events involving Turkish satellite NORAD IDs (see SATELLITE_REGISTRY.md)
4. Export as JSON or CSV
5. Process with a script to compute orbital elements from TLE data at CDM epoch
6. Set `label = 1` where `PC > 1e-4` (use Space-Track's reported Pc as proxy)
7. Save as parquet: `df.to_parquet('historical_conjunctions.parquet')`

**Minimum viable dataset:** 500 records (sufficient for initial training). More is better.
For first training with limited history, accept lower AUC threshold of 0.85 and improve as data accumulates.

### 2. `historical_sequences.npz` (Optional — for LSTM)

Temporal approach sequences: 6 snapshots at 1-hour intervals before TCA.

**Format:**
```python
np.savez(
    'historical_sequences.npz',
    sequences=np.array(...),   # shape: (N, 6, 3) — N events, 6 hours, 3 features
    labels=np.array(...)        # shape: (N,) — same labels as parquet
)
```

The 3 features per time step are:
1. `miss_distance_km` at that hour (re-propagated from TLE at each time step)
2. `relative_velocity_km_s` at that hour
3. `log10_pc_analytic` at that hour (using Chan formula)

This requires running SGP4 for each historical event at 6 time steps — use `conjunction-analysis-agent` scripts to compute these retroactively.

If this file is absent, TRAIN_MODEL will train RF only (still fully functional).
