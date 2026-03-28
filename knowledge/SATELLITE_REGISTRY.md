# Satellite Registry

Reference list of Turkish satellites monitored by the Yörünge Temizliği system.
This file is static — agents read it but never write to it directly.
To add or update a satellite, propose the change via a journal entry.

## Turkish Satellites

| Name | NORAD ID | Orbital Band | Altitude (km) | Type | Operator | Hard-Body Radius (m) | Notes |
|------|----------|-------------|----------------|------|----------|---------------------|-------|
| Türksat 4A | 39522 | GEO | ~35,786 | Communication | Türksat A.Ş. | 30 | Launched 2014, 42°E |
| Türksat 4B | 40985 | GEO | ~35,786 | Communication | Türksat A.Ş. | 30 | Launched 2015, 50°E |
| Türksat 5A | 47790 | GEO | ~35,786 | Communication | Türksat A.Ş. | 30 | Launched 2021, 31°E |
| Türksat 5B | 49077 | GEO | ~35,786 | Communication | Türksat A.Ş. | 30 | Launched 2021, 42°E |
| GÖKTÜRK-1 | 41875 | LEO | ~681 | Earth Observation | MİLLİ SAVUNMA | 20 | Launched 2016, sun-sync |
| GÖKTÜRK-2 | 38704 | LEO | ~686 | Earth Observation | TÜBİTAK UZAY | 20 | Launched 2012, sun-sync |
| RASAT | 37791 | LEO | ~689 | Earth Observation | TÜBİTAK UZAY | 20 | Launched 2011, sun-sync |
| İMECE | 55491 | LEO | ~680 | Earth Observation | ROKETSAN / TÜBİTAK | 20 | Launched 2023, sun-sync |

## Screening Thresholds

| Orbital Band | Coarse Screening Threshold | TCA Refinement Window |
|-------------|---------------------------|----------------------|
| LEO (mean motion ≥ 3.0 rev/day) | 50 km | ±30 minutes, 5s step |
| GEO (mean motion < 3.0 rev/day) | 200 km | ±30 minutes, 5s step |

## Covariance Model Defaults

Used when no Space-Track CDM covariance data is available.
Values are 1-sigma position uncertainty in RSW frame (km).

| Band | σ_radial | σ_intrack | σ_crosstrack |
|------|----------|-----------|--------------|
| LEO | 0.1 | 1.0 | 0.1 |
| GEO | 0.5 | 5.0 | 0.5 |

## Severity Tiers (Analytic Pc)

| Tier | Pc Range | Recommended Action |
|------|----------|-------------------|
| GREEN | < 1×10⁻⁶ | No action |
| YELLOW | 1×10⁻⁶ – 1×10⁻⁴ | Track |
| ORANGE | 1×10⁻⁴ – 1×10⁻³ | Monitor closely |
| RED | ≥ 1×10⁻³ | Immediate review, potential maneuver |
