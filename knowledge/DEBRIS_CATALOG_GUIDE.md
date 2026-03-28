# Debris Catalog Guide

Guide to the data sources used by `tle-ingestion-agent`. Static reference — agents read, never write.

## CelesTrak (Free, No Auth Required)

Base URL: `https://celestrak.org/pub/TLE/`

| Catalog File | URL Suffix | Contents | Approx. Size |
|-------------|-----------|---------|-------------|
| Active Satellites | `active.txt` | All currently active satellites (~6,500 objects) | ~6,500 TLEs |
| GEO Belt | `geo.txt` | GEO and near-GEO objects (~600 objects) | ~600 TLEs |
| Fengyun-3C Debris | `1999-025.txt` | High-density LEO debris cloud from 2007 ASAT test | ~3,400 TLEs |
| Cosmos 2251 Debris | `cosmos-2251-debris.txt` | Debris from 2009 collision | ~1,600 TLEs |
| Iridium 33 Debris | `iridium-33-debris.txt` | Debris from 2009 collision | ~600 TLEs |
| Space Stations | `stations.txt` | ISS and crewed vehicles | ~10 TLEs |

**Rate limits:** CelesTrak recommends not fetching more than once per hour for bulk files.
**TLE freshness:** CelesTrak updates bulk files approximately every 8 hours from Space-Track data.

## Space-Track.org (Free Account Required)

Registration: https://www.space-track.org/auth/createAccount
Credentials: Store in `agents/tle-ingestion-agent/data/imports/credentials.env`

```
SPACETRACK_USER=your_email@example.com
SPACETRACK_PASS=your_password
```

**Rate limits:** Maximum 300 requests per day, maximum 30 requests per minute.
For this system: 4 fetches per day × 2 orbital bands = 8 API calls/day (well within limits).

### Useful API Queries

GEO band (35,000–36,500 km altitude):
```
https://www.space-track.org/basicspacedata/query/class/gp/MEAN_MOTION/%3E0.98/%3C1.02/EPOCH/%3Enow-2/format/tle
```

LEO band (300–1,200 km altitude):
```
https://www.space-track.org/basicspacedata/query/class/gp/MEAN_MOTION/%3E6.8/%3C17.0/EPOCH/%3Enow-2/format/tle
```

### CDM (Conjunction Data Messages)

Space-Track publishes official CDMs for conjunctions involving active satellites.
Download path: `https://www.space-track.org/basicspacedata/query/class/cdm_public/`
Place downloaded CDM JSON files in: `agents/conjunction-analysis-agent/data/imports/cdm/`

Format: Space-Track CDMs include object NORAD IDs, TCA epoch, miss distance, relative velocity, and covariance components in RTN frame.

## NORAD Catalog Identifiers for Turkish Satellites

| Satellite | NORAD ID | CelesTrak Name | Launch Year |
|-----------|----------|---------------|-------------|
| Türksat 4A | 39522 | TURKSAT 4A | 2014 |
| Türksat 4B | 40985 | TURKSAT 4B | 2015 |
| Türksat 5A | 47790 | TURKSAT 5A | 2021 |
| Türksat 5B | 49077 | TURKSAT 5B | 2021 |
| GÖKTÜRK-1 | 41875 | GOKTURK-1 | 2016 |
| GÖKTÜRK-2 | 38704 | GOKTURK-2 | 2012 |
| RASAT | 37791 | RASAT | 2011 |
| İMECE | 55491 | IMECE | 2023 |

## High-Risk Debris Populations Near Turkish LEO Satellites

The following debris clouds intersect the 680–690 km sun-synchronous altitude band
where GÖKTÜRK-1/2, RASAT, and İMECE operate:

| Cloud | Source Event | Peak Object Count | Altitude Band |
|-------|-------------|-------------------|---------------|
| Fengyun-3C fragments | 2007 Chinese ASAT test | ~3,400 tracked | 800–850 km (orbital decay ongoing) |
| Cosmos 2251 debris | 2009 Iridium-Cosmos collision | ~1,600 tracked | 700–900 km |
| Iridium 33 debris | 2009 Iridium-Cosmos collision | ~600 tracked | 680–800 km |

Note: Many sub-10 cm fragments from these events are untracked. The cataloged objects represent only the detectable fraction.
