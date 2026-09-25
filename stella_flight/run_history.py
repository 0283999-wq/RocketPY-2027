"""Run history (2026-09-26 review, item 2 "History" page): every run
saved automatically to a local runs/ folder (inputs, results, timestamp,
notes). List, reopen, delete, compare two runs.
"""
import json
import os
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

RUNS_DIR_NAME = "runs"


def _runs_dir(repo_root):
    d = os.path.join(repo_root, RUNS_DIR_NAME)
    os.makedirs(d, exist_ok=True)
    return d


@dataclass
class RunRecord:
    run_id: str
    timestamp: str
    vehicle_name: str
    ork_filename: str
    eng_filename: str
    dry_mass_kg: float
    dry_cg_m: float
    apogee_agl_m: float
    max_speed_ms: float
    min_static_margin_cal: float
    is_stable: bool
    notes: str = ""


def save_run(repo_root, sim_result, load_result, dry_mass_kg, dry_cg_m, notes=""):
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_dir = os.path.join(_runs_dir(repo_root), run_id)
    os.makedirs(run_dir, exist_ok=True)

    record = RunRecord(
        run_id=run_id, timestamp=datetime.now(timezone.utc).isoformat(),
        vehicle_name=load_result.parsed_ork.name,
        ork_filename=os.path.basename(load_result.parsed_ork.name),
        eng_filename=os.path.basename(load_result.eng_path),
        dry_mass_kg=dry_mass_kg, dry_cg_m=dry_cg_m,
        apogee_agl_m=sim_result.apogee_agl_m, max_speed_ms=sim_result.max_speed_ms,
        min_static_margin_cal=sim_result.min_static_margin_cal, is_stable=sim_result.is_stable,
        notes=notes,
    )
    with open(os.path.join(run_dir, "record.json"), "w") as f:
        json.dump(asdict(record), f, indent=2)

    if load_result.eng_path and os.path.exists(load_result.eng_path):
        shutil.copy(load_result.eng_path, os.path.join(run_dir, os.path.basename(load_result.eng_path)))
    if sim_result.csv_path and os.path.exists(sim_result.csv_path):
        shutil.copy(sim_result.csv_path, os.path.join(run_dir, "flight_data.csv"))
    for name, path in sim_result.plot_paths.items():
        if path and os.path.exists(path):
            shutil.copy(path, os.path.join(run_dir, f"{name}.png"))

    return record


def list_runs(repo_root):
    d = _runs_dir(repo_root)
    records = []
    for run_id in sorted(os.listdir(d), reverse=True):
        record_path = os.path.join(d, run_id, "record.json")
        if os.path.exists(record_path):
            with open(record_path) as f:
                records.append(RunRecord(**json.load(f)))
    return records


def get_run(repo_root, run_id):
    record_path = os.path.join(_runs_dir(repo_root), run_id, "record.json")
    if not os.path.exists(record_path):
        return None
    with open(record_path) as f:
        return RunRecord(**json.load(f))


def delete_run(repo_root, run_id):
    run_dir = os.path.join(_runs_dir(repo_root), run_id)
    if os.path.exists(run_dir):
        shutil.rmtree(run_dir)
        return True
    return False
