#!/usr/bin/env python3
"""
run_pipeline.py — Yorunge Temizligi tam pipeline
Tum adimlari sirayla calistirir.

Kullanim:
    python run_pipeline.py           # Tam pipeline
    python run_pipeline.py --from 3  # 3. adimdan itibaren
    python run_pipeline.py --only 5  # Sadece 5. adim
"""
import subprocess
import sys
import os
import time
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
PYTHON = os.path.join(ROOT, '.venv', 'Scripts', 'python.exe')  # Windows
if not os.path.exists(PYTHON):
    PYTHON = os.path.join(ROOT, '.venv', 'bin', 'python')  # Linux
if not os.path.exists(PYTHON):
    PYTHON = sys.executable  # fallback

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

def run_step(num, name, script_path):
    full_path = os.path.join(ROOT, script_path)
    if not os.path.exists(full_path):
        print(f"  [SKIP] Script bulunamadi: {script_path}")
        return True  # skip, don't fail

    print(f"\n{'='*60}")
    print(f"  Adim {num}/8 — {name}")
    print(f"{'='*60}")

    t0 = time.time()
    result = subprocess.run(
        [PYTHON, full_path],
        cwd=ROOT,
        capture_output=False,
    )
    elapsed = time.time() - t0

    if result.returncode != 0:
        print(f"\n  [HATA] Adim {num} basarisiz (exit={result.returncode}) — {elapsed:.1f}s")
        return False

    print(f"\n  [OK] {elapsed:.1f}s")
    return True


def main():
    # Arguman parse
    start_from = 1
    only_step  = None

    args = sys.argv[1:]
    if '--from' in args:
        start_from = int(args[args.index('--from') + 1])
    if '--only' in args:
        only_step = int(args[args.index('--only') + 1])

    print(f"\nYorunge Temizligi Pipeline")
    print(f"Baslangic: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if only_step:
        print(f"Mod: Sadece adim {only_step}")
    elif start_from > 1:
        print(f"Mod: Adim {start_from}'den itibaren")

    t_total = time.time()
    failed  = False

    for num, name, script in STEPS:
        if only_step and num != only_step:
            continue
        if num < start_from:
            continue

        ok = run_step(num, name, script)
        if not ok:
            print(f"\n[PIPELINE DURDU] Adim {num} ({name}) basarisiz.")
            print("Duzeltip tekrar calistirmak icin: python run_pipeline.py --from {num}")
            failed = True
            break

    elapsed_total = time.time() - t_total
    print(f"\n{'='*60}")
    if failed:
        print(f"  PIPELINE BASARISIZ — {elapsed_total:.0f}s")
    else:
        print(f"  PIPELINE TAMAMLANDI — {elapsed_total:.0f}s")
        print(f"  Bitis: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    main()
