# Yörünge Temizliği — Space Debris Tracking System

Turkish satellite conjunction risk detection using SGP4 orbit propagation and ML scoring.

> Hackathon project — detects potential collisions between Turkish satellites and space debris using real orbital data from NASA/US Space Force.

---

## What It Does

There are **22,000+ tracked objects** in Earth's orbit. This system:

1. Fetches real-time orbital data (TLEs) from CelesTrak and Space-Track.org
2. Propagates all objects' trajectories 72 hours forward using the SGP4 algorithm
3. Finds which debris objects will pass dangerously close to Turkish satellites
4. Computes collision probability using the Chan analytic formula
5. Scores each event with a Random Forest + LSTM ensemble model (SHAP explainability)
6. Generates tiered alerts: 🟢 GREEN / 🟡 YELLOW / 🟠 ORANGE / 🔴 RED

---

## Monitored Satellites

| Satellite | NORAD ID | Orbit | Operator |
|-----------|----------|-------|----------|
| Türksat 4A | 39522 | GEO ~35,786 km | Türksat A.Ş. |
| Türksat 4B | 40985 | GEO ~35,786 km | Türksat A.Ş. |
| Türksat 5A | 47790 | GEO ~35,786 km | Türksat A.Ş. |
| Türksat 5B | 49077 | GEO ~35,786 km | Türksat A.Ş. |
| GÖKTÜRK-1 | 41875 | LEO ~681 km | Milli Savunma |
| GÖKTÜRK-2 | 38704 | LEO ~686 km | TÜBİTAK UZAY |
| RASAT | 37791 | LEO ~689 km | TÜBİTAK UZAY |
| İMECE | 55491 | LEO ~680 km | ROKETSAN / TÜBİTAK |

---

## Pipeline

```
CelesTrak / Space-Track
        ↓
[tle-ingestion-agent]      → fetch + validate TLE data (every 6h)
        ↓
[orbit-propagation-agent]  → SGP4 72h propagation + coarse screening
        ↓
[conjunction-analysis-agent] → precise TCA, Chan Pc, ML features
        ↓
[ml-scoring-agent]         → RF + LSTM ensemble, SHAP explanations
        ↓
[alert-reporting-agent]    → tiered alerts + weekly report
```

---

## Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. (Optional) Add Space-Track credentials
Create `agents/tle-ingestion-agent/data/imports/credentials.env`:
```
SPACETRACK_USER=your_email@example.com
SPACETRACK_PASS=your_password
```
Free account at [space-track.org](https://www.space-track.org/auth/createAccount).
Without this, the system still works using CelesTrak (free, no auth).

### 3. Run the pipeline
```bash
python agents/tle-ingestion-agent/scripts/fetch_tles.py
python agents/tle-ingestion-agent/scripts/validate_tles.py
python agents/orbit-propagation-agent/scripts/propagate_orbits.py
python agents/orbit-propagation-agent/scripts/screen_conjunctions.py
python agents/conjunction-analysis-agent/scripts/compute_tca.py
python agents/conjunction-analysis-agent/scripts/compute_pc.py
python agents/conjunction-analysis-agent/scripts/extract_features.py
python agents/ml-scoring-agent/scripts/score_conjunctions.py
python agents/alert-reporting-agent/scripts/generate_alerts.py
```

Each step writes dated output files to its agent's `outputs/` folder. The next step reads from there automatically.

---

## ML Model

The system works **without a trained model** — it uses the analytic Chan formula as the risk baseline.

To train the ML model:
1. Export historical CDM data from Space-Track → see `agents/ml-scoring-agent/data/imports/training-data/HOW_TO_EXPORT_TRAINING_DATA.md`
2. Run: `python agents/ml-scoring-agent/scripts/train_model.py`
3. Set `"status": "approved"` in `agents/ml-scoring-agent/data/models/model_manifest.json`

For quick demo/testing, generate synthetic training data:
```python
# See HOW_TO_EXPORT_TRAINING_DATA.md for the synthetic data generation snippet
```

---

## Google Colab

The entire pipeline runs on Google Colab. Recommended notebook structure for team collaboration:

| Notebook | Agent(s) |
|----------|---------|
| `01_data_pipeline.ipynb` | tle-ingestion + orbit-propagation |
| `02_conjunction_analysis.ipynb` | conjunction-analysis |
| `03_ml_model.ipynb` | ml-scoring (use GPU runtime) |
| `04_alerts_viz.ipynb` | alert-reporting + visualization |

Mount a shared Google Drive folder so all notebooks read/write to the same location.

```python
# Add to top of each notebook
from google.colab import drive
drive.mount('/content/drive')
import os, subprocess
subprocess.run(['git', 'clone', 'https://github.com/YOUR_USERNAME/bursenal.git'])
os.chdir('bursenal')
```

---

## Project Structure

```
bursenal/
├── agents/
│   ├── tle-ingestion-agent/        # TLE data fetching & validation
│   ├── orbit-propagation-agent/    # SGP4 propagation & screening
│   ├── conjunction-analysis-agent/ # TCA, Pc, ML features
│   ├── ml-scoring-agent/           # ML training & inference
│   └── alert-reporting-agent/      # Alerts & weekly reports
│
├── knowledge/
│   ├── SATELLITE_REGISTRY.md       # Turkish satellite NORAD IDs & specs
│   ├── ORBITAL_MECHANICS_REFERENCE.md
│   └── DEBRIS_CATALOG_GUIDE.md     # CelesTrak & Space-Track guide
│
├── orchestrator/
│   └── YORUNGE-TEMIZLIGI-STATUS.md # Pipeline activation checklist
│
├── journal/entries/                # Agent cycle logs (runtime)
├── requirements.txt
└── AGENT_REGISTRY.md
```

---

## Data Sources

| Source | URL | Auth | What it provides |
|--------|-----|------|-----------------|
| CelesTrak | celestrak.org | None (free) | TLEs for 8,000+ objects |
| Space-Track | space-track.org | Free account | Full GP catalog, CDM data |

---

## Tech Stack

- **SGP4** — NASA standard orbit propagation
- **Chan formula** — analytic collision probability
- **Random Forest** — tabular risk scoring (scikit-learn)
- **LSTM** — temporal approach sequence model (TensorFlow)
- **SHAP** — model explainability
