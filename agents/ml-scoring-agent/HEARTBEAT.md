# ML Scoring Agent Heartbeat

## Schedule
Every 6 hours: 00:45, 06:45, 12:45, 18:45 UTC (15 minutes after conjunction analysis agent).

## Each Cycle

### 1. Read Context
- Check journal for `conjunction-analysis-agent` completion entry within the past 30 minutes
- If no fresh feature file found: skip cycle and log
- Read own `MEMORY.md` for model performance history, known edge cases
- Check `data/models/model_manifest.json` for active model version

### 2. Assess State
- Load the most recent `ml-features.parquet` from `agents/conjunction-analysis-agent/outputs/`
- Is a trained model available in `data/models/`? → If not, log to journal and use analytic Pc only
- Are there >100 new conjunction events since last drift check? → Trigger drift check after scoring

### 3. Execute Skill
- Run `SCORE_CONJUNCTIONS` on the feature file
- If model artifact missing or corrupted: log escalation to journal, output analytic-Pc-only scores
- If any tier override occurs (ML tier ≠ analytic tier): log each override with reason
- Weekly only: run `MONITOR_MODEL_DRIFT`

### 4. Log to Journal
- Events scored (count)
- Tier distribution: RED/ORANGE/YELLOW/GREEN counts
- Tier overrides: how many, which direction (escalation vs de-escalation)
- Inference latency (seconds)
- Active model version

## Weekly Review (Monday 03:30 UTC — runs before standard cycle)

### 1. Gather Data
- Aggregate scored events from the past 7 days
- Load drift report from last `MONITOR_MODEL_DRIFT` run

### 2. Score Against Targets
| Metric | Target | This Week | Status |
|--------|--------|-----------|--------|
| Inference latency / 1000 events | <60 sec | | |
| Tier override rate | <10% of events | | |
| Feature PSI (any feature) | <0.1 (stable) | | |
| Brier score vs training baseline | <+0.02 degradation | | |

### 3. Analyze Wins and Misses
- **Wins:** Which features most consistently explain RED tier predictions (SHAP)?
- **Misses:** Any tier overrides that turned out wrong when CDM data arrived?

### 4. Update Memory
- SHAP top features per tier level (stable signals vs noisy ones)
- Any objects or orbital regimes where model consistently mis-scores

### 5. Log Weekly Summary to Journal
- Model health: STABLE / MONITOR / RETRAIN_RECOMMENDED
- Tier distribution trend (week-over-week)
- Any notable tier escalations

## Monthly Review (first Monday of month — runs after weekly review)
- Run `TRAIN_MODEL` if retrain was recommended in any of the past 4 weekly reviews
- Compare new model metrics vs previous: accept only if AUC improves or holds
- Archive old model artifacts before replacing
- Log model governance entry to journal

## Escalation Rules
- No trained model in `data/models/` → escalate to human to provide training data and trigger first TRAIN_MODEL run
- Retrain produces AUC < 0.92 or Brier > 0.05 for 2 consecutive attempts → escalate to human
- More than 5 RED-tier events in a single scoring cycle → log to journal as high-priority flag
- Model artifact files corrupted or missing mid-cycle → escalate immediately, output analytic-Pc-only
