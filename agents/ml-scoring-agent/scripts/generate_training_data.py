#!/usr/bin/env python3
"""
Training Data Generator
extract_features.py'nin ürettiği 445 gerçek event'ten
RF + LSTM için training data üretir.
Çıktı:
  agents/ml-scoring-agent/data/imports/training-data/rf_training_data.json
  agents/ml-scoring-agent/data/imports/training-data/lstm_sequences.json
"""
import json, os, glob
import numpy as np
import pandas as pd

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
AGENT_DIR  = os.path.dirname(SCRIPT_DIR)
ROOT_DIR   = os.path.dirname(os.path.dirname(AGENT_DIR))
OUTPUT_DIR = os.path.join(AGENT_DIR, 'data', 'imports', 'training-data')
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── En son ml-features.parquet'i bul ─────────────────────────────────────────
def latest(pattern):
    files = glob.glob(pattern)
    return max(files, key=os.path.getmtime) if files else None

parquet_path = latest(os.path.join(
    ROOT_DIR, 'agents/conjunction-analysis-agent/outputs/*_ml-features.parquet'))

if not parquet_path:
    print("[ERROR] ml-features.parquet bulunamadı. Önce extract_features.py çalıştır.")
    exit(1)

print(f"[Load] {os.path.basename(parquet_path)}")
df = pd.read_parquet(parquet_path)

FEATURE_COLS = [
    'miss_distance_km', 'relative_velocity_km_s', 'radial_miss_km',
    'intrack_miss_km', 'crosstrack_miss_km', 'tca_hours_from_now',
    'log10_pc_analytic', 'primary_sma_km', 'primary_eccentricity',
    'primary_inclination_deg', 'primary_raan_deg', 'secondary_sma_km',
    'secondary_eccentricity', 'secondary_inclination_deg', 'secondary_raan_deg',
    'object_type_encoded', 'tca_urgency', 'velocity_miss_product',
    'delta_inclination_deg', 'delta_sma_km', 'orbital_similarity_score',
]

TIER_MAP = {'RED': 2, 'ORANGE': 2, 'YELLOW': 1, 'GREEN': 0}

# ── Gerçek 445 event ──────────────────────────────────────────────────────────
real_data = []
for _, row in df.iterrows():
    feat = {k: float(row[k]) for k in FEATURE_COLS}
    feat['label']  = TIER_MAP.get(row.get('severity_tier', 'GREEN'), 0)
    feat['source'] = 'real'
    real_data.append(feat)

print(f"[Real] {len(real_data)} event | "
      f"Label 0: {sum(f['label']==0 for f in real_data)} | "
      f"Label 1: {sum(f['label']==1 for f in real_data)} | "
      f"Label 2: {sum(f['label']==2 for f in real_data)}")

# ── 5000 sentetik üret ────────────────────────────────────────────────────────
np.random.seed(42)
N_SYNTHETIC = 5000
print(f"[Synth] {N_SYNTHETIC} sentetik kayıt üretiliyor...")

real_arr = np.array([[f[k] for k in FEATURE_COLS] for f in real_data])
mean = real_arr.mean(axis=0)
std  = real_arr.std(axis=0) + 1e-9

# Binary / bounded sütunların indeksleri
BINARY_COLS  = ['object_type_encoded']
BOUNDED_COLS = ['primary_eccentricity', 'secondary_eccentricity',
                'tca_urgency', 'orbital_similarity_score']

synthetic = []
for _ in range(N_SYNTHETIC):
    base   = real_arr[np.random.randint(len(real_arr))]
    noise  = np.random.normal(0, std * 0.4)
    sample = base + noise

    feat = {}
    for j, k in enumerate(FEATURE_COLS):
        v = float(sample[j])
        if k in BINARY_COLS:
            feat[k] = float(int(round(min(max(v, 0), 2))))
        elif k in BOUNDED_COLS:
            feat[k] = max(0.0, min(1.0, v))
        elif k in ('miss_distance_km', 'relative_velocity_km_s',
                   'primary_sma_km', 'secondary_sma_km'):
            feat[k] = max(0.001, v)
        else:
            feat[k] = v

    # Gerçekçi label: miss distance bazlı (compute_pc.py eşikleriyle aynı)
    miss = feat['miss_distance_km']
    vel  = feat['relative_velocity_km_s']
    lpc  = feat['log10_pc_analytic']
    if (miss < 1.0 and vel >= 1.0) or lpc > -3:
        label = 2
    elif miss < 8.0 or lpc > -6:
        label = 1
    else:
        label = 0

    # 8% label noise — gerçek dünyadaki belirsizliği simüle eder
    if np.random.random() < 0.02:
        label = int(np.random.choice([0, 1, 2]))
    feat['label']  = label
    feat['source'] = 'synthetic'
    synthetic.append(feat)

all_data = real_data + synthetic
print(f"[Data] Toplam: {len(all_data)} | Real: {len(real_data)} | Synth: {N_SYNTHETIC}")
print(f"[Data] Label 0: {sum(f['label']==0 for f in all_data)}")
print(f"[Data] Label 1: {sum(f['label']==1 for f in all_data)}")
print(f"[Data] Label 2: {sum(f['label']==2 for f in all_data)}")

# ── RF training data kaydet ───────────────────────────────────────────────────
rf_path = os.path.join(OUTPUT_DIR, 'rf_training_data.json')
with open(rf_path, 'w') as f:
    json.dump({'feature_keys': FEATURE_COLS, 'data': all_data}, f)
print(f"[Done] RF data -> {rf_path}")

# ── LSTM için zaman serisi ────────────────────────────────────────────────────
print("[LSTM] Zaman serisi oluşturuluyor...")

from collections import defaultdict

# Gerçek event'leri uyduya göre grupla
sat_real = defaultdict(list)
for _, row in df.iterrows():
    name = str(row.get('turkish_norad_id', 'unknown'))
    feat = {k: float(row[k]) for k in FEATURE_COLS}
    feat['tca_utc'] = str(row.get('tca_utc', ''))
    feat['label']   = TIER_MAP.get(row.get('severity_tier', 'GREEN'), 0)
    sat_real[name].append(feat)

SEQ_LEN    = 5
sequences  = []
seq_labels = []

for sat_name, sat_evs in sat_real.items():
    sat_evs_sorted = sorted(sat_evs, key=lambda x: x.get('tca_utc', ''))

    # Her event için 8 augmented varyasyon
    extended = []
    for ev in sat_evs_sorted:
        extended.append(ev)
        for _ in range(8):
            noise_ev = {}
            # Negatif olabilecek featurelar (log, açı farkları vb.) clamp edilmez
            ALLOW_NEGATIVE = {
                'log10_pc_analytic', 'radial_miss_km', 'intrack_miss_km',
                'crosstrack_miss_km', 'delta_inclination_deg', 'delta_sma_km',
                'primary_raan_deg', 'secondary_raan_deg',
            }
            for k in FEATURE_COLS:
                v = ev[k]
                noisy = v + np.random.normal(0, abs(v) * 0.1 + 1e-9)
                noise_ev[k] = float(noisy) if k in ALLOW_NEGATIVE else max(0.0, float(noisy))
            miss = noise_ev['miss_distance_km']
            vel2 = noise_ev['relative_velocity_km_s']
            lpc  = noise_ev['log10_pc_analytic']
            noise_ev['label']  = 2 if ((miss < 1.0 and vel2 >= 1.0) or lpc > -3) else (1 if (miss < 8.0 or lpc > -6) else 0)
            noise_ev['source'] = 'lstm_augmented'
            extended.append(noise_ev)

    for i in range(len(extended) - SEQ_LEN):
        seq = [[extended[i+j][k] for k in FEATURE_COLS] for j in range(SEQ_LEN)]
        lbl = extended[i + SEQ_LEN]['label']
        sequences.append(seq)
        seq_labels.append(lbl)

print(f"[LSTM] {len(sequences)} sequence (seq_len={SEQ_LEN})")

lstm_path = os.path.join(OUTPUT_DIR, 'lstm_sequences.json')
with open(lstm_path, 'w') as f:
    json.dump({
        'feature_keys': FEATURE_COLS,
        'seq_len':      SEQ_LEN,
        'sequences':    sequences,
        'labels':       seq_labels,
    }, f)
print(f"[Done] LSTM data -> {lstm_path}")
