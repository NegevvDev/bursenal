# How to Configure: TLE Ingestion Agent

## Step 1: Space-Track Credentials (Optional but Recommended)

Create a file `credentials.env` in this folder (`data/imports/`):

```
SPACETRACK_USER=your_email@example.com
SPACETRACK_PASS=your_password
```

Register for a free account at: https://www.space-track.org/auth/createAccount

**Security note:** Never commit `credentials.env` to git. Add it to `.gitignore`.

Without credentials, the agent will still fetch from CelesTrak (free, no auth), which covers all 8 Turkish satellites and major debris catalogs.

## Step 2: Verify NORAD IDs

Check `knowledge/SATELLITE_REGISTRY.md` to confirm the NORAD IDs for the 8 Turkish satellites are current.
If a satellite has been replaced or a new one added, update the registry via a journal entry and then update `TURKISH_SATELLITES` in `scripts/fetch_tles.py`.

## Step 3: First Run

```bash
cd agents/tle-ingestion-agent
python scripts/fetch_tles.py
python scripts/validate_tles.py
```

Expected output:
- `outputs/YYYY-MM-DD_HHMM_tle-catalog.json` — ~3,000–8,000 objects
- `outputs/YYYY-MM-DD_tle-validation-report.md` — all 8 Turkish satellites should show FRESH status

## Troubleshooting

| Problem | Likely Cause | Fix |
|---------|-------------|-----|
| Turkish satellite MISSING in catalog | NORAD ID outdated | Verify current NORAD ID on celestrak.org |
| Space-Track auth fails | Wrong credentials or 2FA enabled | Check credentials.env, disable 2FA on Space-Track account |
| Low catalog count (<1000 objects) | CelesTrak network issue | Retry after 1 hour |
| High checksum failure rate | Network corruption or URL changed | Check CelesTrak for URL updates |
