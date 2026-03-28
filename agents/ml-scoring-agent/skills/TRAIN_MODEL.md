# Skill: Train Model

## Purpose
Train or retrain the ML collision risk ensemble (Random Forest + LSTM) on historical conjunction data, calibrate probabilities, evaluate on held-out test data, and persist artifacts only if quality thresholds are met.

## Serves Goals
- Model accuracy (AUC-ROC > 0.92)
- Calibration (Brier score < 0.05)
- High-risk recall (>95% for Pc > 1e-4 events)

## Inputs
- `data/imports/training-data/historical_conjunctions.parquet` — labeled historical CDM records (required)
- `data/imports/training-data/historical_sequences.npz` — temporal approach sequences (optional, for LSTM)
- `data/imports/training-data/HOW_TO_EXPORT_TRAINING_DATA.md` — instructions for the human to populate these files

## Process
1. Load `historical_conjunctions.parquet`. Verify it has at minimum: all 20 feature columns + `label` column (1 = high-risk, 0 = nominal)
2. Split: 70% train, 15% validation, 15% test. Use stratified split on `label` to preserve class distribution.
3. Apply SMOTE oversampling to training set minority class (high-risk events): target ratio 1:10. Use `imbalanced-learn`'s `SMOTE(sampling_strategy=0.1, random_state=42)`.
4. Fit `StandardScaler` on training features only. Save scaler to `data/models/scaler.pkl`.
5. Compute training distribution statistics per feature (mean, std, min, max, 10-quantile boundaries) — save to `data/models/training_stats.json` for drift monitoring.

   **Random Forest training:**
6. Run `RandomizedSearchCV` with 5-fold stratified CV over:
   - `n_estimators`: [200, 500, 1000]
   - `max_features`: ['sqrt', 'log2', 0.3]
   - `min_samples_leaf`: [1, 5, 10]
   - `class_weight`: ['balanced']
   - Scoring: AUC-PR (more informative than AUC-ROC for imbalanced classes)
7. Refit best params on full train set. Apply isotonic regression calibration using `CalibratedClassifierCV(cv=5, method='isotonic')`.

   **LSTM training (if `historical_sequences.npz` exists):**
8. Load sequence array of shape `(n_events, 6, 3)` — 6 hourly steps before TCA, 3 features per step: `[miss_distance_km, relative_velocity_km_s, log10_pc_analytic]`
9. Build Keras model: `LSTM(64) → Dropout(0.2) → Dense(32, relu) → Dense(1, sigmoid)`
10. Train with `Adam(lr=1e-3)`, `binary_crossentropy` loss, `class_weight={0:1, 1:class_ratio}`, `EarlyStopping(patience=10, monitor='val_auc_pr', restore_best_weights=True)`, max 100 epochs

    **Evaluation:**
11. Evaluate both models on held-out test set: AUC-ROC, AUC-PR, Brier score, precision/recall at F1-maximizing threshold
12. If RF AUC-ROC ≥ 0.92 AND Brier ≤ 0.05:
    - Archive existing `data/models/` artifacts to `data/models/archive/YYYY-MM-DD_*.pkl`
    - Save: `rf_model.pkl`, `scaler.pkl`, `lstm_weights.h5` (if LSTM trained), `training_stats.json`
    - Write `model_manifest.json`: `{version, training_date, train_set_size, test_auc_roc, test_brier, test_recall_high_risk}`
    - Request human approval before activating for inference (log to journal: "AWAITING_HUMAN_APPROVAL")
13. If thresholds not met: do NOT overwrite existing model, log failure details to journal with escalation flag

## Outputs
- `data/models/rf_model.pkl`, `scaler.pkl`, `lstm_weights.h5`, `training_stats.json`, `model_manifest.json`
- `outputs/YYYY-MM-DD_model-training-report.md` — full evaluation metrics, feature importances, training curve

## Quality Bar
- Must never overwrite a working model with one that scores worse
- Training report must include confusion matrix, AUC-ROC curve description, top 10 feature importances
- Human approval required before new model is used in `SCORE_CONJUNCTIONS`

## Tools
- `scripts/train_model.py`
- Libraries: `scikit-learn`, `imbalanced-learn`, `tensorflow`/`keras`, `joblib`, `numpy`, `pandas`, `shap`, `pyarrow`

## Integration
- Triggered monthly by heartbeat or when drift monitoring recommends retrain
- Output model artifacts consumed by `SCORE_CONJUNCTIONS` and `MONITOR_MODEL_DRIFT`
