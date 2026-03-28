#!/usr/bin/env python3
"""
LSTM Training Script — Colab GPU icin optimize edilmistir.
Cikti: agents/ml-scoring-agent/data/models/lstm_model.h5
"""
import json, os, numpy as np

# ── Veri yukle ───────────────────────────────────────────────────────────────
BASE_DIR  = '/content/bursenal'
DATA_PATH = f'{BASE_DIR}/agents/ml-scoring-agent/data/imports/training-data/lstm_sequences.json'
MODEL_DIR = f'{BASE_DIR}/agents/ml-scoring-agent/data/models'
os.makedirs(MODEL_DIR, exist_ok=True)

print("[Load] LSTM veri yukleniyor...")
with open(DATA_PATH) as f:
    raw = json.load(f)

sequences    = np.array(raw['sequences'], dtype=np.float32)   # (N, seq_len, features)
labels       = np.array(raw['labels'],    dtype=np.int32)
feature_keys = raw['feature_keys']
seq_len      = raw['seq_len']
n_features   = len(feature_keys)

print(f"[Data] {len(sequences)} sequence | seq_len={seq_len} | features={n_features}")
print(f"[Data] Label 0: {sum(labels==0)} | Label 1: {sum(labels==1)} | Label 2: {sum(labels==2)}")

# ── Normalize ────────────────────────────────────────────────────────────────
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split

N, T, F = sequences.shape
X_flat  = sequences.reshape(-1, F)
scaler  = StandardScaler()
X_flat_s = scaler.fit_transform(X_flat)
X_scaled = X_flat_s.reshape(N, T, F)

# Test seti: %20
X_train, X_test, y_train, y_test = train_test_split(
    X_scaled, labels, test_size=0.2, random_state=42, stratify=labels)

print(f"[Split] Train: {len(X_train)} | Test: {len(X_test)}")

# ── Model ────────────────────────────────────────────────────────────────────
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout, BatchNormalization
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
from tensorflow.keras.utils import to_categorical

print(f"[TF] GPU: {tf.config.list_physical_devices('GPU')}")

n_classes = 3
y_train_cat = to_categorical(y_train, n_classes)
y_test_cat  = to_categorical(y_test,  n_classes)

# Class weights (imbalance icin)
from sklearn.utils.class_weight import compute_class_weight
class_weights = compute_class_weight('balanced', classes=np.unique(labels), y=labels)
class_weight_dict = {i: w for i, w in enumerate(class_weights)}
print(f"[Weights] {class_weight_dict}")

model = Sequential([
    LSTM(64, return_sequences=True, input_shape=(seq_len, n_features)),
    Dropout(0.3),
    BatchNormalization(),
    LSTM(32, return_sequences=False),
    Dropout(0.2),
    Dense(32, activation='relu'),
    Dense(n_classes, activation='softmax'),
])

model.compile(
    optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
    loss='categorical_crossentropy',
    metrics=['accuracy'],
)

model.summary()

# ── Eğitim ───────────────────────────────────────────────────────────────────
callbacks = [
    EarlyStopping(monitor='val_loss', patience=10, restore_best_weights=True),
    ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=5, min_lr=1e-5),
]

history = model.fit(
    X_train, y_train_cat,
    epochs=50,
    batch_size=64,
    validation_data=(X_test, y_test_cat),
    class_weight=class_weight_dict,
    callbacks=callbacks,
    verbose=1,
)

# ── Değerlendirme ─────────────────────────────────────────────────────────────
from sklearn.metrics import classification_report, roc_auc_score

y_pred_proba = model.predict(X_test)
y_pred       = np.argmax(y_pred_proba, axis=1)

print("\n[LSTM] Classification Report:")
print(classification_report(y_test, y_pred, labels=[0,1,2],
      target_names=['GREEN','YELLOW','ORANGE/RED'], zero_division=0))

try:
    auc = roc_auc_score(y_test, y_pred_proba, multi_class='ovr', average='macro')
    print(f"[LSTM] AUC (macro): {auc:.4f}")
except Exception as e:
    print(f"[LSTM] AUC hesaplanamadi: {e}")

# ── Kaydet ───────────────────────────────────────────────────────────────────
model_path = f'{MODEL_DIR}/lstm_model.h5'
model.save(model_path)
print(f"\n[Done] Model kaydedildi: {model_path}")

# Google Drive'a kopyala (opsiyonel)
try:
    from google.colab import drive
    drive.mount('/content/drive')
    import shutil
    drive_path = '/content/drive/MyDrive/bursenal_models'
    os.makedirs(drive_path, exist_ok=True)
    shutil.copy(model_path, drive_path)
    print(f"[Drive] Kopyalandi: {drive_path}/lstm_model.h5")
except:
    print("[Drive] Google Drive kopyalama atlaindi")
