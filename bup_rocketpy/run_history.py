"""Run history (2026-09-26 review, item 2 "History" page): every run
saved automatically to a local runs/ folder (inputs, results, timestamp,
notes). List, reopen, delete, compare two runs.
"""
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

import numpy as np

RUNS_DIR_NAME = "runs"


def _git_commit_hash(repo_root):
    """2026-09-26 review item C: which app version produced this run -
    Diego saw the SAME Major Tom inputs give Mach 0.9 on one run and
    Mach 1.0 on another (3,788 -> 3,827 m apogee), most likely because
    the code changed between runs, not the inputs. Recording this makes
    that provable instead of guessed at. Falls back to "unknown" rather
    than raising - a missing git binary or a non-repo checkout (e.g. a
    zipped release) must never block saving a run."""
    try:
        result = subprocess.run(["git", "rev-parse", "--short=12", "HEAD"], cwd=repo_root, capture_output=True, text=True, timeout=5)
        return result.stdout.strip() if result.returncode == 0 and result.stdout.strip() else "unknown"
    except Exception:
        return "unknown"


def _file_hash(path):
    """Short (12 hex char) sha256 of a file's CONTENT - part of the same
    reproducibility record as the git commit hash: same inputs + same
    commit should be provably the same run. "" for a missing/None path
    (e.g. no CSV was supplied, the .ork's own stored data was used)."""
    if not path or not os.path.exists(path):
        return ""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:12]


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
    # BUP_ROCKETPY_RUNS_DIR lets tests point a real running app at an
    # isolated runs/ folder (a fresh one, or one pre-seeded with a
    # corrupt record.json) without ever touching the real repo's own
    # runs/ - 2026-09-25 review Section 4's "fresh runs/ AND a runs/
    # with an old/corrupt record" e2e requirement.
    d = os.environ.get("BUP_ROCKETPY_RUNS_DIR") or os.path.join(repo_root, RUNS_DIR_NAME)
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
    # 2026-09-26 review item C: reproducibility - enough to answer "would
    # the SAME inputs on the SAME app version give the SAME result".
    app_commit_hash: str = "unknown"
    ork_file_hash: str = ""
    eng_file_hash: str = ""
    power_off_drag_hash: str = ""
    power_on_drag_hash: str = ""
    site_lat: float = None
    site_lon: float = None
    site_altitude_m: float = None
    motor_designation: str = ""
    max_mach: float = None
    drag_curve_max_mach: float = None
    mach_extrapolated: bool = False
    drag_curve_source: str = ""


def save_run(repo_root, sim_result, load_result, dry_mass_kg, dry_cg_m, ork_path=None, notes=""):
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_dir = os.path.join(_runs_dir(repo_root), run_id)
    os.makedirs(run_dir, exist_ok=True)

    launch = load_result.parsed_ork.launch
    eng_header = getattr(load_result.parsed_eng, "header", None)
    record = RunRecord(
        run_id=run_id, timestamp=datetime.now(timezone.utc).isoformat(),
        vehicle_name=load_result.parsed_ork.name,
        # ork_path is the actual uploaded file's path - load_result.parsed_ork.name
        # is the ROCKET's declared name from inside the .ork's own XML, not a
        # filename at all (a pre-existing display bug this also fixes).
        ork_filename=os.path.basename(ork_path) if ork_path else "unknown.ork",
        eng_filename=os.path.basename(load_result.eng_path),
        dry_mass_kg=dry_mass_kg, dry_cg_m=dry_cg_m,
        apogee_agl_m=sim_result.apogee_agl_m, max_speed_ms=sim_result.max_speed_ms,
        min_static_margin_cal=sim_result.min_static_margin_cal, is_stable=sim_result.is_stable,
        notes=notes,
        app_commit_hash=_git_commit_hash(repo_root),
        ork_file_hash=_file_hash(ork_path),
        eng_file_hash=_file_hash(load_result.eng_path),
        power_off_drag_hash=_file_hash(load_result.power_off_drag_path),
        power_on_drag_hash=_file_hash(load_result.power_on_drag_path),
        site_lat=launch.latitude if launch else None,
        site_lon=launch.longitude if launch else None,
        site_altitude_m=launch.altitude_m if launch else None,
        motor_designation=eng_header.designation if eng_header else "",
        max_mach=sim_result.max_mach,
        drag_curve_max_mach=sim_result.drag_curve_max_mach,
        mach_extrapolated=sim_result.mach_extrapolated,
        drag_curve_source=load_result.drag_curve_source,
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


def current_app_commit_hash(repo_root):
    """Public wrapper for the History page - lets it compare a saved
    run's app_commit_hash against what's actually running NOW, to
    highlight runs made with an older app version (2026-09-26 review
    item C)."""
    return _git_commit_hash(repo_root)


def cleanup_corrupt_runs(repo_root):
    """Moves every run whose record.json fails to parse into
    runs/_corrupt/<run_id>/, instead of deleting it outright - a corrupt
    record might still have a recoverable flight_data.csv/plots next to
    it, so this is a quarantine, not a delete. Returns the list of run_ids
    moved."""
    d = _runs_dir(repo_root)
    corrupt_dir = os.path.join(d, "_corrupt")
    moved = []
    for run_id in sorted(os.listdir(d)):
        if run_id == "_corrupt":
            continue
        run_dir = os.path.join(d, run_id)
        record_path = os.path.join(run_dir, "record.json")
        if not os.path.isdir(run_dir) or not os.path.exists(record_path):
            continue
        try:
            with open(record_path) as f:
                RunRecord(**json.load(f))
        except (json.JSONDecodeError, TypeError, OSError):
            os.makedirs(corrupt_dir, exist_ok=True)
            shutil.move(run_dir, os.path.join(corrupt_dir, run_id))
            moved.append(run_id)
    return moved
