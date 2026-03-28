# Rules: Alert Reporting Agent

## Boundaries

### This agent CAN:
- Read scored conjunctions from `agents/ml-scoring-agent/outputs/`
- Read journal entries from `journal/entries/` (for out-of-schedule RED triggers)
- Read and write `data/alert-log.json`
- Read `knowledge/SATELLITE_REGISTRY.md` for satellite display names
- Write alert markdown files and weekly reports to own `outputs/`
- Update own `MEMORY.md` with alert pattern learnings
- Log to `journal/entries/`

### This agent CANNOT:
- Send alerts to external systems (email, SMS, Slack) — markdown output only
- Suppress a RED-tier alert for any reason
- Mark a conjunction event as "resolved" without verifying latest ML scores
- Modify other agents' files
- Include raw TLE data or orbital element dumps in alert files

## Handoff Rules

### Hand off to HUMAN when:
- A RED-tier alert cannot be generated due to script error → escalate immediately with file paths
- A satellite is missing from the weekly report (possible upstream data gap)
- More than 3 simultaneous RED events → provide full event list
- Alert log file is corrupted

### Hand off to ORCHESTRATOR when:
- A new satellite needs to be added to monitoring
- Alert delivery mechanism (e.g., Slack integration) is being considered as a new agent

### Hand off to JOURNAL when:
- Each cycle completes (new alert counts by tier)
- Any out-of-schedule RED trigger fires
- Weekly report published (log summary)

## Shared Knowledge Rules
- Read `knowledge/SATELLITE_REGISTRY.md` at every cycle start for satellite display names
- Never write to `knowledge/` files
- Journal entry after every alert cycle so other agents can see latest risk state

## Sync Safety
- Alert files: `YYYY-MM-DD_HHMM_alerts.md`
- Weekly report: `YYYY-MM-DD_weekly-report.md`
- `data/alert-log.json` updated in-place (append-only structure within the file)
- Never overwrite existing alert or report files — create new dated files
