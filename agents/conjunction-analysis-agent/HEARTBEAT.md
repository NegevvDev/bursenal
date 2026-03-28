# Conjunction Analysis Agent Heartbeat

## Schedule
Every 6 hours: 00:30, 06:30, 12:30, 18:30 UTC (15 minutes after orbit propagation agent).

## Each Cycle

### 1. Read Context
- Check journal for `orbit-propagation-agent` completion entry within the past 30 minutes
- If no fresh candidate list found: skip cycle and log
- Read own `MEMORY.md` for known covariance model adjustments, problem NORAD IDs
- Check `data/imports/cdm/` for any new Space-Track CDM files to use as real covariance inputs

### 2. Assess State
- Load the most recent `conjunction-candidates.json` from `agents/orbit-propagation-agent/outputs/`
- How many candidate pairs? (affects expected runtime — >500 candidates takes ~15 min)
- Any CDM files in `data/imports/cdm/` newer than last cycle? → Use real covariance for those objects

### 3. Execute Skill
- Run `COMPUTE_TCA` for all candidates
- Run `COMPUTE_PC` on TCA results
- Run `EXTRACT_ML_FEATURES` on conjunction events
- If any RED-tier events detected: log to journal immediately (alert agent monitors journal)

### 4. Log to Journal
- Events by severity tier (RED/ORANGE/YELLOW/GREEN counts)
- Any RED or ORANGE events: include satellite name, debris NORAD ID, TCA time, miss distance
- Number of events using real CDM covariance vs default model
- Processing duration

## Weekly Review (Monday 03:00 UTC)

### 1. Gather Data
- Collect all `conjunction-events.json` files from the past 7 days
- Cross-reference any available Space-Track CDMs in `data/imports/cdm/`

### 2. Score Against Targets
| Metric | Target | This Week | Status |
|--------|--------|-----------|--------|
| Miss distance accuracy vs CDMs | <100 m error | | |
| TCA timing accuracy vs CDMs | <60 sec error | | |
| Events analyzed | All candidates | | |
| RED/ORANGE events flagged | 100% escalated | | |

### 3. Analyze Wins and Misses
- **Wins:** Which covariance model most closely matches CDM Pc values?
- **Misses:** Any candidate where TCA refinement failed to converge?

### 4. Update Memory
- Satellites with persistently high candidate counts (possible resonance orbits)
- Objects where default covariance significantly under/over-estimates real CDM Pc

### 5. Log Weekly Summary to Journal
- Total events analyzed, tier distribution
- Cross-validation accuracy against CDMs (if data available)
- Notable high-risk events of the week

## Monthly Review
- Review the quality of the default covariance model against accumulated CDM data
- Propose covariance model updates to human if systematic bias detected

## Escalation Rules
- Any RED-tier event (Pc >= 1e-3) → log to journal immediately in same cycle
- TCA minimization fails to converge for >1% of candidates → escalate to human
- More than 3 RED-tier events simultaneously → escalate to human (unusual debris environment)
- CDM cross-validation error > 500 m for multiple objects → covariance model needs adjustment, escalate
