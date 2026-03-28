# Orbital Mechanics Reference

Static reference for agents using orbital mechanics concepts.
Agents read this file; they never write to it.

## Physical Constants

| Constant | Symbol | Value | Units |
|----------|--------|-------|-------|
| Earth's gravitational parameter | μ | 3.986004418×10¹⁴ | m³/s² |
| Earth's equatorial radius | R_E | 6378.137 | km |
| Earth's rotation rate | ω_E | 7.2921150×10⁻⁵ | rad/s |
| Speed of light | c | 2.99792458×10⁸ | m/s |

## SGP4/SDP4 Notes

- **SGP4**: Used for near-Earth objects (period < 225 min, semi-major axis < ~8000 km)
- **SDP4**: Used for deep-space objects (period ≥ 225 min, i.e., GEO, MEO). The `sgp4` Python library selects SDP4 automatically for deep-space objects.
- TLE epoch validity: SGP4 accuracy degrades beyond ±7 days from epoch. For conjunction analysis, TLEs older than 48 hours may introduce position errors of several km for LEO objects.
- SGP4 error codes: 0=success, 1=mean motion<0 (decayed), 2=eccentricity>=1.0, 4=orbit decayed

## Keplerian Elements from Mean Motion

Mean motion n (rev/day) → semi-major axis a (km):
```
n_rad_s = n_rev_day × 2π / 86400    (rad/s)
a = (μ / n_rad_s²)^(1/3) / 1000     (km)
altitude = a - R_Earth               (km)
```

## RSW Frame (Radial-Along-Track-Cross-Track)

Standard reference frame for conjunction geometry:
- **R** (Radial): along position vector r̂ = r/|r|
- **S** (Along-Track/In-Track): S = W × R
- **W** (Cross-Track): W = (r × v) / |r × v|

Used for: covariance representation, miss vector decomposition, collision probability computation.

## Chan Analytic Collision Probability (Pc)

Gaussian approximation valid when hard-body radius HBR << σ (covariance scale):

```
Pc = (π × HBR²) / (2π × σ_u × σ_v) × exp(-0.5 × ((x_miss/σ_u)² + (y_miss/σ_v)²))
```

Where:
- σ_u, σ_v = principal axes of the combined covariance projected onto the miss plane
- x_miss, y_miss = miss vector components in the principal axis frame
- HBR = hard-body radius of the conjunction (combined radius of both objects)
- Miss plane = plane perpendicular to relative velocity at TCA

## Population Stability Index (PSI) Interpretation

Used for ML model drift monitoring:
- PSI < 0.1: negligible change, no action
- 0.1 ≤ PSI < 0.2: moderate change, monitor
- PSI ≥ 0.2: significant change, retrain recommended

Formula:
```
PSI = Σ (actual_pct_i - expected_pct_i) × ln(actual_pct_i / expected_pct_i)
```

## Orbital Altitude Bands

| Band | Altitude Range | Turkish Satellites | Key Debris Populations |
|------|---------------|-------------------|----------------------|
| LEO | 300–2000 km | GÖKTÜRK-1/2, RASAT, İMECE | Fengyun-3C fragments, Cosmos 2251 debris, Iridium 33 debris |
| MEO | 2000–35,000 km | None | GNSS constellations |
| GEO | ~35,786 km | Türksat 4A/4B/5A/5B | ~600 GEO belt objects |
