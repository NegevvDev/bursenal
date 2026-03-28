# Rules: ML Scoring Agent

## Boundaries

### This agent CAN:
- Read ML feature files from `agents/conjunction-analysis-agent/outputs/`
- Read model artifacts from own `data/models/`
- Read training data from own `data/imports/training-data/`
- Write scored conjunctions, training reports, drift reports to own `outputs/`
- Write model artifacts to own `data/models/` (only after human approval for retrain)
- Update own `MEMORY.md` with model performance and SHAP patterns
- Log to `journal/entries/`

### This agent CANNOT:
- Deploy a retrained model to inference without human approval
- Overwrite model artifacts without archiving the previous version first
- Run LSTM inference when approach sequence covers <6 hours (use RF-only)
- Suppress a tier override without logging reason
- Modify other agents' files

## Handoff Rules

### Hand off to HUMAN when:
- No training data exists in `data/imports/training-data/` → cannot train initial model
- Retrain fails quality threshold (AUC < 0.92 or Brier > 0.05) for 2 consecutive attempts
- More than 5 RED-tier events in one scoring cycle
- Model artifacts missing or corrupted during inference

### Hand off to ORCHESTRATOR when:
- Training data needs to be sourced from a new external provider
- A new ML architecture (e.g., Transformer) is being considered

### Hand off to JOURNAL when:
- Each cycle completes (tier distribution, override count, model version)
- Drift detected (PSI > 0.1 on any feature)
- Retrain completed (new model version, metrics)

## Shared Knowledge Rules
- Read `knowledge/ORBITAL_MECHANICS_REFERENCE.md` when interpreting SHAP features for memory updates
- Never write to `knowledge/` files
- Log model governance decisions (retrain approvals, version changes) to journal

## Sync Safety
- Scored conjunction outputs: `YYYY-MM-DD_HHMM_scored-conjunctions.json`
- Model artifacts: archive before overwrite using `data/models/archive/YYYY-MM-DD_*.pkl` pattern
- Never overwrite output files
- Scripts must be idempotent
