# Alert Reporting Agent Heartbeat

## Schedule
Every 6 hours: 01:00, 07:00, 13:00, 19:00 UTC (15 minutes after ML scoring agent).
Weekly report: Every Monday 08:00 UTC.

## Each Cycle

### 1. Read Context
- Check journal for `ml-scoring-agent` completion entry within the past 30 minutes
- Also check journal for any RED-tier flags from `conjunction-analysis-agent` — if found, run immediately out-of-schedule
- Read `data/alert-log.json` for deduplication history
- Read `knowledge/SATELLITE_REGISTRY.md` for satellite display names

### 2. Assess State
- Load the most recent `scored-conjunctions.json` from `agents/ml-scoring-agent/outputs/`
- How many RED and ORANGE events exist that have not yet had an alert in the past 24 hours?
- Any events whose tier has escalated since last alert? → Always re-alert on escalation

### 3. Execute Skill
- Run `GENERATE_ALERTS` for the current scored conjunction set
- If a RED event is detected in journal (out-of-schedule trigger): run `GENERATE_ALERTS` immediately
- Monday 08:00 UTC only: run `WEEKLY_REPORT` before or after the standard cycle

### 4. Log to Journal
- Number of new alerts by tier (RED/ORANGE/YELLOW)
- Number of events deduplicated (already alerted, no tier change)
- Any out-of-schedule RED triggers
- Location of output files

## Weekly Review (Monday 08:00 UTC — runs as part of WEEKLY_REPORT skill)

### 1. Gather Data
- Collect all scored conjunction files from the past 7 days
- Collect all alert files from the past 7 days

### 2. Score Against Targets
| Metric | Target | This Week | Status |
|--------|--------|-----------|--------|
| Alert-to-score latency (RED) | <5 min | | |
| False alarm rate | <5% | | |
| Report completeness | 100% of active events | | |
| Trend flags | All worsening bands flagged | | |

### 3. Analyze Wins and Misses
- **Wins:** Which alert format is clearest for the human operator?
- **Misses:** Any RED event where alert was delayed >5 minutes?

### 4. Update Memory
- Satellites with recurring ORANGE events (persistent risk objects)
- Time patterns in RED alert frequency (orbital resonance signatures)

### 5. Log Weekly Summary to Journal
- Week's highest-risk event (satellite, debris, miss distance, ML score)
- Count of alerts by tier for the week
- Any new objects appearing in ORANGE/RED tier for the first time

## Monthly Review
- Review alert log for tier escalation patterns: are any debris objects consistently escalating?
- Review false alarm rate: any systematic source of spurious ORANGE alerts?
- Propose threshold adjustments to human if false alarm rate > 10% for 2 consecutive months

## Escalation Rules
- RED-tier alert cannot be generated (script error, missing data) → escalate to human immediately with raw scored-conjunctions.json path
- Satellite missing from weekly report → escalate to human (may indicate upstream data gap)
- More than 3 RED events simultaneously → escalate to human with full event list
- Alert log file becomes corrupted → escalate to human before proceeding
