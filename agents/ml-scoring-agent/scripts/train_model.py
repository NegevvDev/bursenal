#!/usr/bin/env python3
"""
RF + XGBoost Ensemble Training Script
Cikti: agents/ml-scoring-agent/data/models/
"""
import json, os, glob
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.preprocessing import StandardScaler
import joblib

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
AGENT_DIR  = os.path.dirname(SCRIPT_DIR)
DATA_PATH  = os.path.join(AGENT_DIR, 'data', 'imports', 'training-data', 'rf_training_data.json')
MODEL_DIR  = os.path.join(AGENT_DIR, 'data', 'models')
os.makedirs(MODEL_DIR, exist_ok=True)

# ── Veri yukle ───────────────────────────────────────────────────────────────
print("[Load] Training data yukleniyor...")
with open(DATA_PATH) as f:
    raw = json.load(f)

feature_keys = raw['feature_keys']
data         = raw['data']

X = np.array([[row[k] for k in feature_keys] for row in data])
y = np.array([row['label'] for row in data])
sources = np.array([row['source'] for row in data])

print(f"[Data] {len(X)} kayit | {len(feature_keys)} ozellik")
print(f"[Data] Label 0: {sum(y==0)} | Label 1: {sum(y==1)} | Label 2: {sum(y==2)}")

# ── Test seti: sadece gercek event'ler (%20) ─────────────────────────────────
real_idx  = np.where(sources == 'real')[0]
synth_idx = np.where(sources != 'real')[0]

np.random.seed(42)
np.random.shuffle(real_idx)
n_test    = max(int(len(real_idx) * 0.2), 10)
test_idx  = real_idx[:n_test]
train_real_idx = real_idx[n_test:]

train_idx = np.concatenate([train_real_idx, synth_idx])

X_train, X_test = X[train_idx], X[test_idx]
y_train, y_test = y[train_idx], y[test_idx]

print(f"[Split] Train: {len(X_train)} | Test (gercek): {len(X_test)}")

# ── Normalize ────────────────────────────────────────────────────────────────
scaler    = StandardScaler()
X_train_s = scaler.fit_transform(X_train)
X_test_s  = scaler.transform(X_test)

# ── Random Forest ────────────────────────────────────────────────────────────
print("\n[RF] Egitiliyor...")
rf = RandomForestClassifier(
    n_estimators=200,
    max_depth=7,
    min_samples_leaf=5,
    max_features='sqrt',
    class_weight='balanced',
    random_state=42,
    n_jobs=-1,
)
rf.fit(X_train_s, y_train)
rf_pred  = rf.predict(X_test_s)
rf_proba = rf.predict_proba(X_test_s)

print("[RF] Classification Report:")
print(classification_report(y_test, rf_pred, labels=sorted(set(y_test)), zero_division=0))
try:
    rf_auc = roc_auc_score(y_test, rf_proba, multi_class='ovr', average='macro')
    print(f"[RF] AUC (macro): {rf_auc:.4f}")
except Exception as e:
    rf_auc = 0.0

# ── XGBoost ──────────────────────────────────────────────────────────────────
print("\n[XGB] Egitiliyor...")
xgb_available = False
xgb_proba     = None
xgb_auc       = 0.0
try:
    from xgboost import XGBClassifier
    xgb = XGBClassifier(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        eval_metric='mlogloss',
        random_state=42,
        verbosity=0,
    )
    xgb.fit(X_train_s, y_train)
    xgb_pred  = xgb.predict(X_test_s)
    xgb_proba = xgb.predict_proba(X_test_s)
    print("[XGB] Classification Report:")
    print(classification_report(y_test, xgb_pred, labels=sorted(set(y_test)), zero_division=0))
    try:
        xgb_auc = roc_auc_score(y_test, xgb_proba, multi_class='ovr', average='macro')
        print(f"[XGB] AUC (macro): {xgb_auc:.4f}")
    except:
        pass
    xgb_available = True
    joblib.dump(xgb, os.path.join(MODEL_DIR, 'xgb_model.pkl'))
except ImportError:
    print("[XGB] XGBoost yuklu degil, sadece RF kullanilacak")

# ── Ensemble ─────────────────────────────────────────────────────────────────
if xgb_available:
    print("\n[Ensemble] RF 0.6 + XGBoost 0.4...")
    ens_proba = 0.6 * rf_proba + 0.4 * xgb_proba
    ens_pred  = np.argmax(ens_proba, axis=1)
    print("[Ensemble] Classification Report:")
    print(classification_report(y_test, ens_pred, labels=sorted(set(y_test)), zero_division=0))

# ── Feature importance ────────────────────────────────────────────────────────
print("\n[SHAP] Feature importance hesaplaniyor...")
try:
    import shap
    explainer   = shap.TreeExplainer(rf)
    shap_vals   = explainer.shap_values(X_test_s[:50])
    if isinstance(shap_vals, list):
        mean_shap = np.abs(np.array(shap_vals)).mean(axis=(0, 1))
    else:
        mean_shap = np.abs(shap_vals).mean(axis=0)
    importance = sorted(zip(feature_keys, mean_shap.tolist()), key=lambda x: x[1], reverse=True)
    print("[SHAP] Top 10 ozellik:")
    for feat, score in importance[:10]:
        print(f"  {feat:<30} {score:.4f}")
except Exception as e:
    print(f"[SHAP] Atlanim: {e} — RF feature_importances kullaniliyor")
    importance = sorted(zip(feature_keys, rf.feature_importances_.tolist()), key=lambda x: x[1], reverse=True)
    print("[RF] Top 10 ozellik:")
    for feat, score in importance[:10]:
        print(f"  {feat:<30} {score:.4f}")

# ── Kaydet ───────────────────────────────────────────────────────────────────
joblib.dump(rf,     os.path.join(MODEL_DIR, 'rf_model.pkl'))
joblib.dump(scaler, os.path.join(MODEL_DIR, 'scaler.pkl'))

import datetime
meta = {
    'feature_keys':      feature_keys,
    'n_train':           int(len(X_train)),
    'n_test':            int(len(X_test)),
    'xgb_available':     xgb_available,
    'rf_auc':            float(rf_auc),
    'xgb_auc':           float(xgb_auc),
    'feature_importance': [[k, float(v)] for k, v in importance[:10]],
    'trained_at':        datetime.datetime.utcnow().isoformat(),
}
with open(os.path.join(MODEL_DIR, 'model_meta.json'), 'w') as f:
    json.dump(meta, f, indent=2)

print(f"\n[Done] {MODEL_DIR}")
print("  rf_model.pkl | scaler.pkl | model_meta.json")
if xgb_available:
    print("  xgb_model.pkl")
