# How to Export CDM Data from Space-Track

CDM (Conjunction Data Message) files provide real covariance data that improves Pc accuracy.

## What CDMs Are

Space-Track publishes official conjunction data messages for active satellites. Each CDM includes:
- Primary and secondary object NORAD IDs
- Time of Closest Approach (TCA) UTC
- Miss distance, relative velocity
- Covariance matrix components in RTN (Radial-Transverse-Normal) frame
- Official Pc estimate

## How to Download

1. Log in at https://www.space-track.org
2. Navigate to: **Conjunction Data Messages (CDMs)**
3. Filter by NORAD ID for Turkish satellites (see `knowledge/SATELLITE_REGISTRY.md`)
4. Download as JSON format
5. Place files in this folder: `data/imports/cdm/`

**Naming convention (preferred):** `YYYY-MM-DD_NORAD-PRIMARY_cdm.json`

## API Query (Automated Download)

```python
import requests

session = requests.Session()
session.post("https://www.space-track.org/ajaxauth/login",
             data={'identity': USER, 'password': PASS})

# CDMs for Türksat 4A (NORAD 39522)
url = ("https://www.space-track.org/basicspacedata/query/class/cdm_public/"
       "SAT_1_ID/39522/orderby/TCA_TIME/format/json")
r = session.get(url)
with open("cdm_turksat4a.json", "w") as f:
    f.write(r.text)
```

Repeat for each of the 8 Turkish satellite NORAD IDs.

## CDM Data Format Used by `compute_pc.py`

The script looks for JSON files with these fields:
- `SAT_1_ID`: Primary NORAD ID
- `SAT_2_ID`: Secondary NORAD ID
- `TCA_TIME`: TCA UTC string
- `MISS_DISTANCE`: miss distance (m — script converts to km)
- `RELATIVE_SPEED`: relative velocity (m/s)
- `SAT1_CR_R`, `SAT1_CT_R`, `SAT1_CT_T`, `SAT1_CN_R`, `SAT1_CN_T`, `SAT1_CN_N`: Covariance (m²)

If CDM files are not present, `compute_pc.py` uses the default diagonal covariance model from `knowledge/SATELLITE_REGISTRY.md`. This is acceptable for initial operation but CDM covariances produce more accurate Pc values.

## Update Frequency

Recommended: Download CDMs at least once per day for any active ORANGE or RED tier events.
For GREEN/YELLOW events: weekly CDM refresh is sufficient.
