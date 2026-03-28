# Orbit Propagation Agent Heartbeat

## Schedule
Every 6 hours: 00:15, 06:15, 12:15, 18:15 UTC (15 minutes after TLE ingestion agent).

## Each Cycle

### 1. Read Context
- Check journal for `tle-ingestion-agent` completion entry within the past 30 minutes
- If no fresh TLE journal entry found: wait up to 15 minutes, then skip cycle and log
- Read own `MEMORY.md` for known SGP4 error patterns or problematic NORAD IDs

### 2. Assess State
- Load the most recent `tle-catalog.json` from `agents/tle-ingestion-agent/outputs/`
- Verify catalog timestamp is less than 8 hours old — abort if older
- How many objects in the catalog? (affects expected runtime)

### 3. Execute Skill
- Run `PROPAGATE_ORBITS` for all objects in the catalog
- Run `SCREEN_CONJUNCTIONS` on the resulting state vectors
- If propagation error rate > 5%: log to journal as escalation, do not write candidate list

### 4. Log to Journal
- Objects propagated (LEO count, GEO count)
- Propagation errors (NORAD IDs with SGP4 error codes, error type)
- Candidate pairs found per Turkish satellite
- Total candidates, processing duration (minutes)

## Weekly Review (Monday 02:30 UTC)

### 1. Gather Data
- Count candidate pairs per cycle across the past 7 days
- Identify which Turkish satellites consistently produce the most candidates

### 2. Score Against Targets
| Metric | Target | This Week | Status |
|--------|--------|-----------|--------|
| Propagation coverage | 100% of catalog | | |
| Processing latency | <30 min | | |
| SGP4 error rate | <1% of objects | | |
| Screening candidate count | Stable or tracked trend | | |

### 3. Analyze Wins and Misses
- **Wins:** Time step selection producing accurate results within latency budget?
- **Misses:** Any objects consistently throwing SGP4 errors? (likely decaying orbits)

### 4. Update Memory
- NORAD IDs known to produce SGP4 errors (likely re-entering objects — flag for removal from catalog)
- Altitude bands with highest candidate density

### 5. Log Weekly Summary to Journal
- Average candidates per cycle per satellite
- SGP4 error trend
- Any new high-density debris zones detected

## Monthly Review
- Review screening threshold performance: any false negatives found when cross-checking against CDMs?
- Consider tightening LEO threshold from 50 km to 30 km if compute allows

## Escalation Rules
- TLE catalog is older than 8 hours when cycle starts → skip and log
- SGP4 error rate exceeds 5% in a single cycle → log escalation, do not publish candidates
- Processing time exceeds 60 minutes → investigate and escalate to human
- Candidate count drops to 0 for all satellites → likely propagation failure, escalate
