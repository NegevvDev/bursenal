"""
colab_run.py — Google Colab icin tam pipeline
Colab'da su sekilde calistir:

  !git clone https://github.com/NegevvDev/bursenal.git /content/bursenal
  %cd /content/bursenal
  !pip install -q sgp4 scikit-learn xgboost joblib shap pandas pyarrow requests tensorflow
  !python colab_run.py
"""
import subprocess, sys, os, time
from datetime import datetime

BASE_DIR = '/content/bursenal'
PYTHON   = sys.executable

# Space-Track credentials — Colab Secrets'tan al (varsa), yoksa direkt yaz
try:
    from google.colab import userdata
    ST_USER = userdata.get('SPACETRACK_USER')
    ST_PASS = userdata.get('SPACETRACK_PASS')
except:
    ST_USER = 'negevvdev@gmail.com'
    ST_PASS = 'kagann2012133148481'

# credentials.env yaz
cred_path = os.path.join(BASE_DIR, 'agents/tle-ingestion-agent/data/imports/credentials.env')
os.makedirs(os.path.dirname(cred_path), exist_ok=True)
with open(cred_path, 'w') as f:
    f.write(f'SPACETRACK_USER={ST_USER}\n')
    f.write(f'SPACETRACK_PASS={ST_PASS}\n')
print(f'[Setup] credentials.env yazildi')

STEPS = [
    (1, "TLE Fetch",          "agents/tle-ingestion-agent/scripts/fetch_tles.py"),
    (2, "Orbit Propagation",  "agents/orbit-propagation-agent/scripts/propagate_orbits.py"),
    (3, "Conjunction Screen", "agents/orbit-propagation-agent/scripts/screen_conjunctions.py"),
    (4, "Compute TCA",        "agents/conjunction-analysis-agent/scripts/compute_tca.py"),
    (5, "Compute Pc",         "agents/conjunction-analysis-agent/scripts/compute_pc.py"),
    (6, "Extract Features",   "agents/conjunction-analysis-agent/scripts/extract_features.py"),
    (7, "ML Scoring",         "agents/ml-scoring-agent/scripts/score_conjunctions.py"),
    (8, "Generate Alerts",    "agents/alert-reporting-agent/scripts/generate_alerts.py"),
]

def run_step(num, name, script):
    full = os.path.join(BASE_DIR, script)
    if not os.path.exists(full):
        print(f'  [SKIP] {script}')
        return True
    print(f'\n{"="*60}')
    print(f'  Adim {num}/8 — {name}')
    print(f'{"="*60}')
    t0 = time.time()
    r  = subprocess.run([PYTHON, full], cwd=BASE_DIR)
    print(f'  [{"OK" if r.returncode == 0 else "HATA"}] {time.time()-t0:.1f}s')
    return r.returncode == 0

print(f'\nYorunge Temizligi — Colab Pipeline')
print(f'Baslangic: {datetime.now().strftime("%Y-%m-%d %H:%M")}')

for num, name, script in STEPS:
    if not run_step(num, name, script):
        print(f'\n[DURDU] Adim {num} basarisiz.')
        break
else:
    print(f'\n{"="*60}')
    print(f'  PIPELINE TAMAMLANDI')
    print(f'  Bitis: {datetime.now().strftime("%Y-%m-%d %H:%M")}')
    print(f'{"="*60}')
