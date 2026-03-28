#!/usr/bin/env python3
"""
Score Conjunctions Script — ml-scoring-agent
RF + XGBoost + LSTM ile 445 conjunction event'ini skorlar.
Output: outputs/YYYY-MM-DD_HHMM_scored-conjunctions.json

Dependencies: pip install scikit-learn joblib shap numpy xgboost tensorflow
"""
import json, os, math, glob
import numpy as np
import joblib
from datetime import datetime, timezone

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
AGENT_DIR   = os.path.dirname(SCRIPT_DIR)
ROOT_DIR    = os.path.dirname(os.path.dirname(AGENT_DIR))
MODELS_DIR  = os.path.join(AGENT_DIR, 'data', 'models')
OUTPUTS_DIR = os.path.join(AGENT_DIR, 'outputs')
os.makedirs(OUTPUTS_DIR, exist_ok=True)

R_EARTH = 6378.137
MU      = 398600.4418

def latest(pattern):
    files = glob.glob(pattern)
    return max(files, key=os.path.getmtime) if files else None

# ── Veri yükle ───────────────────────────────────────────────────────────────
events_path  = latest(os.path.join(ROOT_DIR, 'agents/conjunction-analysis-agent/outputs/*_conjunction-events.json'))
catalog_path = latest(os.path.join(ROOT_DIR, 'agents/tle-ingestion-agent/outputs/*_tle-catalog.json'))

print(f"[Load] Events : {os.path.basename(events_path)}")
print(f"[Load] Catalog: {os.path.basename(catalog_path)}")

with open(events_path)  as f: events_data  = json.load(f)
with open(catalog_path) as f: catalog_data = json.load(f)

events  = events_data['conjunction_events']
catalog = {obj['norad_id']: obj for obj in catalog_data['catalog']}

def mean_motion_to_altitude(mm):
    try:
        n = mm * 2 * math.pi / 86400
        return (MU / n**2) ** (1/3) - R_EARTH
    except:
        return 500.0

def extract_features(event, catalog):
    tk_id  = event['turkish_norad_id']
    deb_id = event['debris_norad_id']
    tk_obj  = catalog.get(tk_id, {})
    deb_obj = catalog.get(deb_id, {})

    def tle2(obj, s, e, default=0.0):
        try:    return float(obj['line2'][s:e])
        except: return default

    tk_inc  = tle2(tk_obj,  8, 16)
    tk_ecc  = tle2(tk_obj, 26, 33) * 1e-7
    tk_mm   = tle2(tk_obj, 52, 63)
    deb_inc = tle2(deb_obj,  8, 16)
    deb_ecc = tle2(deb_obj, 26, 33) * 1e-7
    deb_mm  = tle2(deb_obj, 52, 63)

    tk_alt  = mean_motion_to_altitude(tk_mm)  if tk_mm  > 0 else 500.0
    deb_alt = mean_motion_to_altitude(deb_mm) if deb_mm > 0 else 500.0

    try:
        tca_dt = datetime.fromisoformat(event['tca_utc'])
        now_dt = datetime.now(timezone.utc)
        time_to_tca_h = (tca_dt - now_dt).total_seconds() / 3600
    except:
        time_to_tca_h = 24.0

    miss_dist  = event.get('miss_distance_km', 50.0)
    rel_vel    = event.get('relative_velocity_km_s', 7.0)
    radial     = event.get('radial_miss_km', 10.0)
    intrack    = event.get('intrack_miss_km', 30.0)
    crosstrack = event.get('crosstrack_miss_km', 20.0)
    pc         = event.get('analytic_pc', 0.0)
    is_leo     = 1 if event.get('orbital_band') == 'LEO' else 0

    deb_name  = deb_obj.get('name', '').upper()
    is_debris = 1 if any(k in deb_name for k in ['DEB', 'DEBRIS', 'R/B', 'ROCKET']) else 0

    inc_diff      = abs(tk_inc - deb_inc)
    alt_diff      = abs(tk_alt - deb_alt)
    closing_speed = rel_vel * math.cos(math.radians(min(inc_diff, 90)))

    return {
        'miss_distance_km':       miss_dist,
        'relative_velocity_km_s': rel_vel,
        'time_to_tca_h':          max(0, time_to_tca_h),
        'radial_miss_km':         radial,
        'intrack_miss_km':        intrack,
        'crosstrack_miss_km':     crosstrack,
        'analytic_pc':            pc,
        'tk_inclination':         tk_inc,
        'tk_eccentricity':        tk_ecc,
        'tk_altitude_km':         tk_alt,
        'tk_mean_motion':         tk_mm,
        'deb_inclination':        deb_inc,
        'deb_eccentricity':       deb_ecc,
        'deb_altitude_km':        deb_alt,
        'deb_mean_motion':        deb_mm,
        'inclination_diff':       inc_diff,
        'altitude_diff_km':       alt_diff,
        'closing_speed_km_s':     closing_speed,
        'is_leo':                 is_leo,
        'is_debris':              is_debris,
        'hbr_km':                 event.get('hbr_km', 0.02),
    }

# ── Feature matrix ──────────────────────────────────────────────────────────
print("[Extract] Features çıkarılıyor...")
feature_rows = []
for ev in events:
    feat = extract_features(ev, catalog)
    feature_rows.append(feat)

meta_path = os.path.join(MODELS_DIR, 'model_meta.json')
with open(meta_path) as f:
    meta = json.load(f)
feature_keys = meta['feature_keys']

X = np.array([[row[k] for k in feature_keys] for row in feature_rows], dtype=np.float32)
print(f"[Extract] {len(X)} event | {len(feature_keys)} feature")

# ── Model yükle ve normalize et ─────────────────────────────────────────────
rf_model = joblib.load(os.path.join(MODELS_DIR, 'rf_model.pkl'))
scaler   = joblib.load(os.path.join(MODELS_DIR, 'scaler.pkl'))
X_scaled = scaler.transform(X)

xgb_model  = None
xgb_path   = os.path.join(MODELS_DIR, 'xgb_model.pkl')
if os.path.exists(xgb_path):
    xgb_model = joblib.load(xgb_path)
    print("[Model] RF + XGBoost ensemble yüklendi")
else:
    print("[Model] Sadece RF kullanılıyor (xgb_model.pkl bulunamadı)")

# ── RF inference ─────────────────────────────────────────────────────────────
rf_proba = rf_model.predict_proba(X_scaled)   # (N, 3): class 0,1,2

if xgb_model:
    xgb_proba  = xgb_model.predict_proba(X_scaled)
    ens_proba  = 0.6 * rf_proba + 0.4 * xgb_proba
else:
    ens_proba = rf_proba

ml_labels = np.argmax(ens_proba, axis=1)   # 0=GREEN, 1=YELLOW, 2=RED/ORANGE

# ── LSTM inference (opsiyonel) ────────────────────────────────────────────────
lstm_scores = None
lstm_path   = os.path.join(MODELS_DIR, 'lstm_model.h5')
if os.path.exists(lstm_path):
    try:
        import tensorflow as tf
        lstm_model = tf.keras.models.load_model(lstm_path)
        # Tek event'i seq_len=5 tekrarlayarak sequence oluştur (inference modu)
        seq_len    = 5
        X_seq      = np.tile(X_scaled[:, np.newaxis, :], (1, seq_len, 1))
        lstm_proba = lstm_model.predict(X_seq, verbose=0)   # (N, 3)
        # Ensemble: RF/XGB 0.7 + LSTM 0.3
        ens_proba  = 0.7 * ens_proba + 0.3 * lstm_proba
        ml_labels  = np.argmax(ens_proba, axis=1)
        lstm_scores = True
        print(f"[LSTM] Yüklendi ve çalıştırıldı: {lstm_path}")
    except Exception as e:
        print(f"[WARN] LSTM inference başarısız: {e}")

# ── SHAP explanations ─────────────────────────────────────────────────────────
shap_vals = None
try:
    import shap
    explainer = shap.TreeExplainer(rf_model)
    sv = explainer.shap_values(X_scaled)
    # sv: list of 3 arrays (one per class), each (N, F)
    sv_arr = np.array(sv) if isinstance(sv, list) else sv
    if sv_arr.ndim == 3:
        # (3, N, F) → mean over classes axis=0 → (N, F)
        # (N, F, 3) → mean over classes axis=2 → (N, F)
        if sv_arr.shape[0] == len(X_scaled):
            shap_vals = np.abs(sv_arr).mean(axis=2)   # (N, F)
        else:
            shap_vals = np.abs(sv_arr).mean(axis=0)   # (N, F)
    elif sv_arr.ndim == 2:
        shap_vals = np.abs(sv_arr)
    else:
        shap_vals = None
    print(f"[SHAP] Tamamlandı — shape={shap_vals.shape if shap_vals is not None else 'N/A'}")
except Exception as e:
    shap_vals = None
    print(f"[WARN] SHAP atlandı: {e}")

# ── Label → tier ─────────────────────────────────────────────────────────────
LABEL_TIER = {0: 'GREEN', 1: 'YELLOW', 2: 'RED/ORANGE'}
TIER_ORDER  = {'GREEN': 0, 'YELLOW': 1, 'ORANGE': 2, 'RED': 3, 'RED/ORANGE': 2}

def resolve_tier(ml_label, analytic_tier, miss_km):
    """ML tahminini analitik tier ile birleştir, kötüyü al."""
    ml_tier = LABEL_TIER[ml_label]
    # Eğer ML RED/ORANGE diyorsa ve miss < 3 km → RED, değilse ORANGE
    if ml_tier == 'RED/ORANGE':
        ml_tier = 'RED' if miss_km < 3.0 else 'ORANGE'
    a_ord = TIER_ORDER.get(analytic_tier, 0)
    m_ord = TIER_ORDER.get(ml_tier, 0)
    return ml_tier if m_ord >= a_ord else analytic_tier

# ── Sonuçları derle ───────────────────────────────────────────────────────────
now = datetime.now(timezone.utc)
ts  = now.strftime('%Y-%m-%d_%H%M')

tier_counts = {'RED': 0, 'ORANGE': 0, 'YELLOW': 0, 'GREEN': 0}
records = []

for i, ev in enumerate(events):
    ml_lbl       = int(ml_labels[i])
    analytic_tier = ev.get('severity_tier', 'GREEN')
    miss_km       = ev.get('miss_distance_km', 50.0)
    final_tier    = resolve_tier(ml_lbl, analytic_tier, miss_km)

    tier_counts[final_tier] = tier_counts.get(final_tier, 0) + 1

    # Risk skoru: P(class>=1) = 1 - P(GREEN)
    risk_score = float(1.0 - ens_proba[i, 0])

    # Top SHAP features
    top_shap = []
    if shap_vals is not None:
        top_idxs = [int(x) for x in np.argsort(shap_vals[i])[::-1][:3]]
        for fi in top_idxs:
            top_shap.append({
                'feature': feature_keys[fi],
                'shap':    float(shap_vals[i, fi]),
                'value':   float(X[i, fi]),
            })

    records.append({
        'event_id':               ev.get('event_id', f'ev_{i:04d}'),
        'turkish_name':           ev.get('turkish_name', ''),
        'turkish_norad_id':       ev.get('turkish_norad_id', 0),
        'debris_norad_id':        ev.get('debris_norad_id', 0),
        'tca_utc':                ev.get('tca_utc', ''),
        'miss_distance_km':       miss_km,
        'relative_velocity_km_s': ev.get('relative_velocity_km_s', 0.0),
        'analytic_pc':            ev.get('analytic_pc', 0.0),
        'analytic_tier':          analytic_tier,
        'ml_label':               ml_lbl,
        'risk_score':             round(risk_score, 6),
        'final_tier':             final_tier,
        'lstm_used':              lstm_scores is True,
        'top_shap_features':      top_shap,
    })

output = {
    'scored_at_utc':       now.isoformat(),
    'total_scored':        len(records),
    'tier_counts':         tier_counts,
    'lstm_used':           lstm_scores is True,
    'xgb_used':            xgb_model is not None,
    'scored_conjunctions': records,
}

output_path = os.path.join(OUTPUTS_DIR, f"{ts}_scored-conjunctions.json")
with open(output_path, 'w') as f:
    json.dump(output, f, indent=2)

print(f"\n[Done] {len(records)} event skorlandı")
print(f"  RED:{tier_counts.get('RED',0)} ORANGE:{tier_counts.get('ORANGE',0)} YELLOW:{tier_counts.get('YELLOW',0)} GREEN:{tier_counts.get('GREEN',0)}")
print(f"  Çıktı: {os.path.basename(output_path)}")

# RED olayları vurgula
for rec in records:
    if rec['final_tier'] == 'RED':
        shap_str = ', '.join(f["feature"] for f in rec['top_shap_features'][:2])
        print(f"  !! RED: {rec['turkish_name']} × NORAD {rec['debris_norad_id']} | TCA {rec['tca_utc']} | risk={rec['risk_score']:.4f} | SHAP: {shap_str}")
