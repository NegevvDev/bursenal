# Skill: TLE Validate

## Purpose
Perform deep validation of the TLE catalog: epoch freshness audit, physical plausibility checks on orbital elements, and cross-source consistency verification.

## Serves Goals
- Data quality (100% of output TLEs pass all validation checks)
- Coverage completeness (identifies gaps before downstream agents use stale data)

## Inputs
- Most recent `outputs/YYYY-MM-DD_HHMM_tle-catalog.json` from this agent's outputs
- `knowledge/SATELLITE_REGISTRY.md` — expected NORAD IDs and orbital bands

## Process
1. Load the most recent TLE catalog from `outputs/`
2. For each object, parse the mean motion from TLE line 2, columns 53–63 (revolutions per day)
3. Check physical plausibility: mean motion must be between 0.002 rev/day (very high GEO) and 17 rev/day (ISS-like LEO) — flag objects outside this range
4. Compute semi-major axis from mean motion: `a = (mu / n^2)^(1/3)` where `n` is in rad/s and `mu = 3.986004418e14 m^3/s^2` — flag if implied altitude is below 100 km (reentry) or above 100,000 km (escape)
5. Check BSTAR drag coefficient (TLE line 1, columns 54–61): for LEO objects, zero BSTAR is suspicious — flag as possible stale TLE
6. Compute TLE epoch age: parse year from columns 19–20 and day-of-year from columns 20–32 of line 1, convert to UTC, compute age = now − epoch — flag any object with epoch age > 7 days
7. For each Turkish satellite: flag if epoch age > 48 hours (critical threshold)
8. Cross-source check: if both CelesTrak and Space-Track data are present for the same NORAD ID, compare epoch timestamps — flag if they differ by more than 6 hours (one source may be stale)
9. Compute summary statistics: total objects, flagged objects by reason, Turkish satellite freshness status
10. Write validation report to `outputs/YYYY-MM-DD_tle-validation-report.md`
11. If any Turkish satellite has epoch age > 48 hours: add escalation flag to journal entry
12. If overall rejection rate (failed checksum + physical implausibility) > 2%: add escalation flag

## Outputs
- `outputs/YYYY-MM-DD_tle-validation-report.md` — per-object validation flags and summary statistics
- Journal entry with validation summary and any escalation flags

## Quality Bar
- Every Turkish satellite must have a freshness status in the report (FRESH / STALE / MISSING)
- Report must include total flagged count with breakdown by reason
- Validation must complete before `orbit-propagation-agent` reads the catalog

## Tools
- `scripts/validate_tles.py` — epoch parsing, physical checks, cross-source comparison, report writing
- Libraries: `numpy`, `pandas`, `json`, `datetime`

## Integration
- Runs immediately after `TLE_FETCH` in every cycle
- Validation flags are read by `orbit-propagation-agent` before propagation (via journal entry)
- Persistent stale patterns logged to `MEMORY.md` after 3+ occurrences
