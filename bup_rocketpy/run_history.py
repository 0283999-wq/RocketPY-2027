"""Run history (2026-09-26 review, item 2 "History" page): every run
saved automatically to a local runs/ folder (inputs, results, timestamp,
notes). List, reopen, delete, compare two runs.
"""
import json
import os
import shutil
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

import numpy as np

RUNS_DIR_NAME = "runs"


class _NumpyJSONEncoder(json.JSONEncoder):
    """rocketpy/numpy results carry numpy scalar types (np.bool_,
    np.float64, np.int64, ...) that json.dump refuses outright - the
    "Object of type bool is not JSON serializable" crash Diego hit came
    from `min(margins) > 0` producing a numpy.bool_, not a plain bool.
    Converting every numpy scalar to its native Python type here fixes
    the whole class of bug instead of hunting each field one at a time.
    """
    def default(self, o):
        if isinstance(o, np.bool_):
            return bool(o)
        if isinstance(o, np.integer):
            return int(o)
        if isinstance(o, np.floating):
            return float(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
        return super().default(o)


def _atomic_write_json(path, data):
    """Write via a temp file + os.replace so a crash/kill mid-write never
    leaves a truncated, unparseable record.json behind (the second bug
    Diego hit: a half-written file that then poisoned list_runs forever)."""
    d = os.path.dirname(path)
    fd, tmp_path = tempfile.mkstemp(dir=d, prefix=".tmp_", suffix=".json")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2, cls=_NumpyJSONEncoder)
        os.replace(tmp_path, path)
    except BaseException:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


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
    _atomic_write_json(os.path.join(run_dir, "record.json"), asdict(record))

    if load_result.eng_path and os.path.exists(load_result.eng_path):
        shutil.copy(load_result.eng_path, os.path.join(run_dir, os.path.basename(load_result.eng_path)))
    if sim_result.csv_path and os.path.exists(sim_result.csv_path):
        shutil.copy(sim_result.csv_path, os.path.join(run_dir, "flight_data.csv"))
    for name, path in sim_result.plot_paths.items():
        if path and os.path.exists(path):
            shutil.copy(path, os.path.join(run_dir, f"{name}.png"))

    return record


def list_runs(repo_root):
    """Returns (records, warnings). A corrupt/truncated/old-schema
    record.json (e.g. left over from before the atomic-write fix, or from
    a killed process) is skipped with a warning instead of taking the
    whole History page down - a page must never crash per CLAUDE.md."""
    d = _runs_dir(repo_root)
    records = []
    warnings = []
    for run_id in sorted(os.listdir(d), reverse=True):
        record_path = os.path.join(d, run_id, "record.json")
        if not os.path.exists(record_path):
            continue
        try:
            with open(record_path) as f:
                records.append(RunRecord(**json.load(f)))
        except (json.JSONDecodeError, TypeError, OSError) as e:
            warnings.append(f"Skipped corrupt run '{run_id}': {e}")
    return records, warnings


def get_run(repo_root, run_id):
    record_path = os.path.join(_runs_dir(repo_root), run_id, "record.json")
    if not os.path.exists(record_path):
        return None
    try:
        with open(record_path) as f:
            return RunRecord(**json.load(f))
    except (json.JSONDecodeError, TypeError, OSError):
        return None


def delete_run(repo_root, run_id):
    run_dir = os.path.join(_runs_dir(repo_root), run_id)
    if os.path.exists(run_dir):
        shutil.rmtree(run_dir)
        return True
    return False
