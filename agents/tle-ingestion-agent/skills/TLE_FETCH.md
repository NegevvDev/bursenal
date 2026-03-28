# Skill: TLE Fetch

## Purpose
Download current TLE sets for Turkish satellites and a large catalog of debris objects from CelesTrak and Space-Track.org, producing a deduplicated, normalized JSON catalog.

## Serves Goals
- Coverage completeness (all 8 Turkish satellites present with fresh TLE)
- Fetch reliability (successful fetch rate >99%)
- Catalog breadth (>500 GEO objects, >2000 LEO objects)

## Inputs
- `knowledge/SATELLITE_REGISTRY.md` — NORAD IDs for the 8 Turkish satellites
- `data/imports/credentials.env` — Space-Track.org credentials (optional but recommended)
- CelesTrak public endpoints (no auth required)

## Process
1. Read `knowledge/SATELLITE_REGISTRY.md` to load NORAD IDs and orbital bands for all Turkish satellites
2. Fetch the following CelesTrak catalogs via HTTP GET:
   - `https://celestrak.org/pub/TLE/active.txt` — all active satellites
   - `https://celestrak.org/pub/TLE/geo.txt` — GEO belt objects
   - `https://celestrak.org/pub/TLE/1999-025.txt` — Fengyun-3C debris (high debris density cloud)
   - `https://celestrak.org/pub/TLE/cosmos-2251-debris.txt` — Cosmos 2251 collision debris
   - `https://celestrak.org/pub/TLE/iridium-33-debris.txt` — Iridium 33 collision debris
3. If `data/imports/credentials.env` exists: authenticate with Space-Track.org and fetch the GP catalog for GEO band (35000–36500 km altitude) and LEO band (300–1200 km altitude)
4. Parse all fetched text into (name, line1, line2) tuples using the standard 3-line TLE format
5. Validate each TLE: compute checksum for line 1 and line 2 independently (mod-10 checksum per TLE spec), reject any TLE that fails
6. Deduplicate by NORAD ID: when multiple sources provide the same object, keep the TLE with the most recent epoch
7. Determine orbital band per object: mean motion < 3.0 rev/day → GEO; otherwise LEO
8. Mark the 8 Turkish satellites with `is_turkish_satellite: true` and `satellite_name` field
9. Verify all 8 Turkish satellite NORAD IDs are present in the output catalog — log any missing ones
10. Write the catalog to `outputs/YYYY-MM-DD_HHMM_tle-catalog.json` with fields: `norad_id`, `name`, `line1`, `line2`, `epoch_utc`, `source`, `orbital_band`, `is_turkish_satellite` (if applicable)
11. Log fetch completion to journal: total objects, Turkish satellites confirmed, any missing, source status

## Outputs
- `outputs/YYYY-MM-DD_HHMM_tle-catalog.json` — full deduplicated catalog
- Journal entry with fetch summary

## Quality Bar
- All 8 Turkish satellite TLEs must be present and have epoch within 48 hours
- No TLE in the catalog may have a failed checksum
- Catalog must contain at least 1000 objects total before downstream agents can proceed
- If any Turkish satellite is missing: log the gap to journal, do not abort (partial catalog is still useful for other satellites)

## Tools
- `scripts/fetch_tles.py` — HTTP fetching, TLE parsing, checksum validation, deduplication, output writing
- Libraries: `requests`, `json`, `datetime`, `hashlib`

## Integration
- Output feeds directly into `orbit-propagation-agent` (reads latest `tle-catalog.json`)
- If catalog is incomplete (missing Turkish satellites), `TLE_VALIDATE` skill logs the gap for escalation
