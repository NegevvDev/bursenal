# TLE Ingestion Agent Heartbeat

## Schedule
Every 6 hours: 00:00, 06:00, 12:00, 18:00 UTC.

## Each Cycle

### 1. Read Context
- Check recent journal entries for upstream failures or data gaps
- Read `knowledge/SATELLITE_REGISTRY.md` for current NORAD ID list
- Read own `MEMORY.md` for known source reliability patterns

### 2. Assess State
- When did the last successful fetch run? (check latest file in `outputs/`)
- Is the last catalog older than 7 hours? → Run immediately regardless of schedule
- Are any Turkish satellite TLEs missing from the last catalog? → Prioritize individual NORAD fetch

### 3. Execute Skill
- Default: run `TLE_FETCH` → then run `TLE_VALIDATE`
- If fetch fails (network error or Space-Track auth failure): retry once after 5 minutes, then log to journal and exit
- If validation finds >5% rejection rate: log to journal as escalation trigger

### 4. Log to Journal
- Fetch timestamp, source status (CelesTrak OK/FAIL, Space-Track OK/FAIL/SKIP)
- Total objects in catalog, count per orbital band
- Turkish satellites confirmed present / missing
- Any validation failures with reasons

## Weekly Review (Monday 02:00 UTC — runs before standard cycle)

### 1. Gather Data
- Read all `outputs/YYYY-MM-DD_tle-validation-report.md` files from the past 7 days

### 2. Score Against Targets
| Metric | Target | This Week | Status |
|--------|--------|-----------|--------|
| Turkish satellite TLE freshness | 100% <48h old | | |
| Fetch success rate | >99% | | |
| Catalog breadth (LEO) | >2000 objects | | |
| Catalog breadth (GEO) | >500 objects | | |

### 3. Analyze Wins and Misses
- **Wins:** Which fetch configuration produced the most reliable results?
- **Misses:** Any Turkish satellite with repeated TLE gaps? Log hypothesis.

### 4. Update Memory
Add confirmed patterns to MEMORY.md (e.g., "Space-Track rate-limits after 4 requests/day").

### 5. Log Weekly Summary to Journal
- Fetches attempted vs successful
- Any TLE gaps per satellite
- Catalog size trend (growing? stable?)
- Recommendations for next week

## Monthly Review
- Review catalog breadth trend: is the tracked debris population growing?
- Review Space-Track API error patterns
- Flag if any satellite has been maneuver-active (TLE epoch jumps >24h between cycles)

## Escalation Rules
- Any Turkish satellite TLE is older than 72 hours → escalate to human immediately
- Space-Track authentication fails for 2+ consecutive cycles → escalate to human
- Catalog size drops by >20% vs previous week → escalate to human
- CelesTrak returns HTTP 5xx for 3+ consecutive cycles → escalate to human
