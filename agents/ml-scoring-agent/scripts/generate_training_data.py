#!/usr/bin/env python3
"""
Training Data Generator
Gercek 445 conjunction event'inden RF + LSTM icin training data uretir.
Cikti:
  agents/ml-scoring-agent/data/imports/training-data/rf_training_data.json
  agents/ml-scoring-agent/data/imports/training-data/lstm_sequences.json
"""
import json, os, math, glob
import numpy as np
from datetime import datetime, timezone

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
AGENT_DIR   = os.path.dirname(SCRIPT_DIR)
ROOT_DIR    = os.path.dirname(os.path.dirname(AGENT_DIR))
OUTPUT_DIR  = os.path.join(AGENT_DIR, 'data', 'imports', 'training-data')
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── En son dosyaları bul ─────────────────────────────────────────────────────
def latest(pattern):
    files = glob.glob(pattern)
    return max(files, key=os.path.getmtime) if files else None

events_path  = latest(os.path.join(ROOT_DIR, 'agents/conjunction-analysis-agent/outputs/*_conjunction-events.json'))
catalog_path = latest(os.path.join(ROOT_DIR, 'agents/tle-ingestion-agent/outputs/*_tle-catalog.json'))

print(f"[Load] Events : {os.path.basename(events_path)}")
print(f"[Load] Catalog: {os.path.basename(catalog_path)}")

with open(events_path)  as f: events_data  = json.load(f)
with open(catalog_path) as f: catalog_data = json.load(f)

events  = events_data['conjunction_events']
catalog = {obj['norad_id']: obj for obj in catalog_data['catalog']}

R_EARTH = 6378.137  # km
MU      = 398600.4418  # km^3/s^2

def mean_motion_to_altitude(mean_motion_rev_day):
    """Ortalama hareket (rev/day) -> yaklasik yukseklik (km)"""
    try:
        n = mean_motion_rev_day * 2 * math.pi / 86400  # rad/s
        a = (MU / n**2) ** (1/3)  # km
        return a - R_EARTH
    except:
        return 500.0

def extract_features(event, catalog):
    """Bir event'ten 21 ozellik cikar."""
    tk_id  = event['turkish_norad_id']
    deb_id = event['debris_norad_id']
    tk_obj  = catalog.get(tk_id, {})
    deb_obj = catalog.get(deb_id, {})

    def parse_tle_field(obj, field_idx_l2_start, field_idx_l2_end, default=0.0):
        try:
            return float(obj['line2'][field_idx_l2_start:field_idx_l2_end])
        except:
            return default

    # Yörünge parametreleri - TLE line2'den
    tk_inc   = parse_tle_field(tk_obj,  8, 16)   # inclination
    tk_ecc   = parse_tle_field(tk_obj, 26, 33) * 1e-7  # eccentricity (implicit decimal)
    tk_mm    = parse_tle_field(tk_obj, 52, 63)   # mean motion
    deb_inc  = parse_tle_field(deb_obj, 8, 16)
    deb_ecc  = parse_tle_field(deb_obj, 26, 33) * 1e-7
    deb_mm   = parse_tle_field(deb_obj, 52, 63)

    tk_alt   = mean_motion_to_altitude(tk_mm)  if tk_mm  > 0 else 500.0
    deb_alt  = mean_motion_to_altitude(deb_mm) if deb_mm > 0 else 500.0

    # TCA'ya kalan sure (saat)
    try:
        tca_dt  = datetime.fromisoformat(event['tca_utc'])
        now_dt  = datetime.now(timezone.utc)
        time_to_tca_h = (tca_dt - now_dt).total_seconds() / 3600
    except:
        time_to_tca_h = 24.0

    miss_dist = event.get('miss_distance_km', 50.0)
    rel_vel   = event.get('relative_velocity_km_s', 7.0)
    radial    = event.get('radial_miss_km', 10.0)
    intrack   = event.get('intrack_miss_km', 30.0)
    crosstrack= event.get('crosstrack_miss_km', 20.0)
    pc        = event.get('analytic_pc', 0.0)
    is_leo    = 1 if event.get('orbital_band') == 'LEO' else 0

    # Nesne tipi
    deb_type  = deb_obj.get('name', '').upper()
    is_debris = 1 if any(k in deb_type for k in ['DEB', 'DEBRIS', 'R/B', 'ROCKET']) else 0

    inc_diff  = abs(tk_inc - deb_inc)
    alt_diff  = abs(tk_alt - deb_alt)
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

def label_event(feat, tier=None):
    """severity_tier veya miss distance bazli label uret."""
    tier_map = {'RED': 2, 'ORANGE': 2, 'YELLOW': 1, 'GREEN': 0}
    if tier in tier_map:
        return tier_map[tier]
    miss = feat['miss_distance_km']
    vel  = feat['relative_velocity_km_s']
    if miss < 5.0:  return 2
    if miss < 15.0: return 1
    return 0

# ── Gercek 445 event'i isle ──────────────────────────────────────────────────
print("[Extract] 445 gercek event isleniyor...")
real_features = []
for ev in events:
    feat = extract_features(ev, catalog)
    feat['label'] = label_event(feat, tier=ev.get('severity_tier'))
    feat['source'] = 'real'
    real_features.append(feat)

print(f"[Extract] {len(real_features)} real event | Labels: {sum(f['label']>0 for f in real_features)} risky")

# ── Sentetik veri uret (gercek veriden turetilmis) ───────────────────────────
np.random.seed(42)
N_SYNTHETIC = 5000
print(f"[Synth] {N_SYNTHETIC} sentetik kayit uretiliyor...")

feature_keys = [k for k in real_features[0].keys() if k not in ('label', 'source')]
real_arr = np.array([[f[k] for k in feature_keys] for f in real_features])
mean = real_arr.mean(axis=0)
std  = real_arr.std(axis=0) + 1e-9

synthetic = []
for _ in range(N_SYNTHETIC):
    base   = real_arr[np.random.randint(len(real_arr))]
    noise  = np.random.normal(0, std * 0.3)
    sample = base + noise

    # Fiziksel sinirlar
    feat = {}
    for j, k in enumerate(feature_keys):
        v = float(sample[j])
        if k in ('is_leo', 'is_debris'):
            feat[k] = int(round(min(max(v, 0), 1)))
        elif k in ('analytic_pc',):
            feat[k] = max(0.0, min(1.0, v))
        elif k in ('miss_distance_km', 'relative_velocity_km_s', 'hbr_km',
                   'time_to_tca_h', 'tk_altitude_km', 'deb_altitude_km'):
            feat[k] = max(0.001, v)
        else:
            feat[k] = v

    feat['label']  = label_event(feat)
    feat['source'] = 'synthetic'
    synthetic.append(feat)

all_data = real_features + synthetic
print(f"[Data] Toplam: {len(all_data)} | Real: {len(real_features)} | Synth: {N_SYNTHETIC}")
print(f"[Data] Label 0 (low): {sum(f['label']==0 for f in all_data)}")
print(f"[Data] Label 1 (med): {sum(f['label']==1 for f in all_data)}")
print(f"[Data] Label 2 (high):{sum(f['label']==2 for f in all_data)}")

rf_path = os.path.join(OUTPUT_DIR, 'rf_training_data.json')
with open(rf_path, 'w') as f:
    json.dump({'feature_keys': feature_keys, 'data': all_data}, f)
print(f"[Done] RF data -> {rf_path}")

# ── LSTM icin zaman serisi ───────────────────────────────────────────────────
print("[LSTM] Zaman serisi olusturuluyor...")

# Her Turk uydusu icin event listesi (zaman sirali)
from collections import defaultdict
sat_events = defaultdict(list)
for feat in all_data:
    # turkish_name bilgisi yok synthetic'te, real'den aliriz
    pass

# Real event'leri uyduya gore grupla
sat_real = defaultdict(list)
for i, ev in enumerate(events):
    name = ev['turkish_name']
    feat = real_features[i].copy()
    feat['tca_utc'] = ev['tca_utc']
    sat_real[name].append(feat)

# Her uydu icin sliding window ile sequence olustur
SEQ_LEN    = 5
sequences  = []
seq_labels = []

for sat_name, sat_evs in sat_real.items():
    # TCA zamanina gore sirala
    sat_evs_sorted = sorted(sat_evs, key=lambda x: x.get('tca_utc', ''))

    # Sentetik varyasyonlar ekleyerek sequence uzat
    extended = []
    for ev in sat_evs_sorted:
        extended.append(ev)
        for _ in range(8):  # Her event icin 8 varyasyon
            noise_ev = {}
            for k in feature_keys:
                v = ev[k]
                if isinstance(v, float):
                    noise_ev[k] = max(0.0, v + np.random.normal(0, abs(v) * 0.1 + 1e-9))
                else:
                    noise_ev[k] = v
            noise_ev['label']  = label_event(noise_ev)
            noise_ev['source'] = 'lstm_augmented'
            extended.append(noise_ev)

    # Sliding window
    for i in range(len(extended) - SEQ_LEN):
        seq = [[extended[i+j][k] for k in feature_keys] for j in range(SEQ_LEN)]
        lbl = extended[i + SEQ_LEN]['label']
        sequences.append(seq)
        seq_labels.append(lbl)

print(f"[LSTM] {len(sequences)} sequence olusturuldu (seq_len={SEQ_LEN})")

lstm_path = os.path.join(OUTPUT_DIR, 'lstm_sequences.json')
with open(lstm_path, 'w') as f:
    json.dump({
        'feature_keys': feature_keys,
        'seq_len':       SEQ_LEN,
        'sequences':     sequences,
        'labels':        seq_labels,
    }, f)
print(f"[Done] LSTM data -> {lstm_path}")
