#!/usr/bin/env python3
"""
Yorunge Temizligi — FastAPI Backend
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

ROOT = Path(__file__).parent.parent
PYTHON = sys.executable

app = FastAPI(title="Yorunge Temizligi API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pipeline state
pipeline_state = {
    "running": False,
    "last_run": None,
    "last_status": None,
    "log": [],
}


def run_pipeline_task(steps: str = "all"):
    pipeline_state["running"] = True
    pipeline_state["log"] = []

    try:
        if steps == "all":
            cmd = [PYTHON, str(ROOT / "run_pipeline.py")]
        else:
            cmd = [PYTHON, str(ROOT / "run_pipeline.py"), "--from", steps]

        result = subprocess.run(
            cmd,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=1800,
        )
        pipeline_state["log"] = (result.stdout + result.stderr).splitlines()
        pipeline_state["last_status"] = "success" if result.returncode == 0 else "error"
    except subprocess.TimeoutExpired:
        pipeline_state["last_status"] = "timeout"
        pipeline_state["log"] = ["Pipeline timed out after 30 minutes"]
    except Exception as e:
        pipeline_state["last_status"] = "error"
        pipeline_state["log"] = [str(e)]
    finally:
        pipeline_state["running"] = False
        pipeline_state["last_run"] = datetime.now(timezone.utc).isoformat()


@app.get("/api/status")
def get_status():
    return {
        "running": pipeline_state["running"],
        "last_run": pipeline_state["last_run"],
        "last_status": pipeline_state["last_status"],
    }


@app.post("/api/run-pipeline")
def trigger_pipeline(background_tasks: BackgroundTasks, from_step: int = 1):
    if pipeline_state["running"]:
        raise HTTPException(status_code=409, detail="Pipeline already running")
    background_tasks.add_task(run_pipeline_task, str(from_step))
    return {"message": "Pipeline started", "from_step": from_step}


@app.get("/api/pipeline-log")
def get_log():
    return {"log": pipeline_state["log"]}


@app.get("/api/latest-alerts")
def get_alerts():
    outputs = ROOT / "agents" / "alert-reporting-agent" / "outputs"
    if not outputs.exists():
        raise HTTPException(status_code=404, detail="No alerts yet")

    files = sorted(outputs.glob("*_alerts.md"))
    if not files:
        raise HTTPException(status_code=404, detail="No alert files found")

    latest = files[-1]
    return {
        "filename": latest.name,
        "generated_at": latest.stat().st_mtime,
        "content": latest.read_text(encoding="utf-8"),
    }


@app.get("/api/latest-scores")
def get_scores():
    outputs = ROOT / "agents" / "ml-scoring-agent" / "outputs"
    if not outputs.exists():
        raise HTTPException(status_code=404, detail="No scores yet")

    files = sorted(outputs.glob("*_scored-conjunctions.json"))
    if not files:
        raise HTTPException(status_code=404, detail="No score files found")

    with open(files[-1], encoding="utf-8") as f:
        data = json.load(f)

    return data


@app.get("/api/model-info")
def get_model_info():
    meta_path = ROOT / "agents" / "ml-scoring-agent" / "data" / "models" / "model_meta.json"
    manifest_path = ROOT / "agents" / "ml-scoring-agent" / "data" / "models" / "model_manifest.json"

    result = {}
    if meta_path.exists():
        with open(meta_path) as f:
            result["meta"] = json.load(f)
    if manifest_path.exists():
        with open(manifest_path) as f:
            result["manifest"] = json.load(f)

    return result


# Serve frontend
frontend = ROOT / "api" / "frontend"
if frontend.exists():
    app.mount("/", StaticFiles(directory=str(frontend), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    uvicorn.run("main:app", host="0.0.0.0", port=args.port, reload=False)
