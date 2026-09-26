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
from dataclasses import asdict, dataclass, field
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
    # 2026-09-27 review item 2: enough to fully reconstitute the exact
    # session state that produced this run, not just its RESULTS - so
    # "Reopen this mission" (item 4) restores reefing/overrides/weather/
    # profile, not just the .ork/.eng. reefing_settings is a list of
    # plain dicts (one per parachute, dataclasses.asdict(chute)) rather
    # than a list of Parachute objects - json-serializable, and forward-
    # compatible if Parachute ever gains a field this schema doesn't
    # know about yet (an old record.json just won't have it).
    reefing_settings: list = field(default_factory=list)
    dry_mass_override_kg: float = None  # None means "no manual override was active" - the default path used the geometric/stored-sim estimate instead
    dry_cg_override_m: float = None
    launch_override: dict = None  # dataclasses.asdict(LaunchConditions) if a Launch Day weather override was active, else None
    competition_profile: str = ""
    ork_saved: bool = False  # whether THIS run's own .ork copy exists in its run_dir (older runs, saved before this field existed, do not have one)
    power_off_drag_saved: bool = False
    power_on_drag_saved: bool = False


def save_run(repo_root, sim_result, load_result, dry_mass_kg, dry_cg_m, ork_path=None, ork_filename=None, eng_filename=None, notes="",
             dry_mass_override_kg=None, dry_cg_override_m=None, launch_override=None, competition_profile=""):
    """dry_mass_override_kg/dry_cg_override_m: the RAW override fields (None
    if no manual override was active this run) - kept separate from
    dry_mass_kg/dry_cg_m (the value ACTUALLY used, override or estimate)
    so reopen_run() can tell whether to re-enable the override checkbox.
    launch_override: dataclasses.asdict(state["launch_override"]) if a
    Launch Day weather override was active, else None. competition_profile:
    state["competition_profile"]. All 2026-09-27 review item 2 - enough
    to fully reconstitute the session, not just log the result."""
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_dir = os.path.join(_runs_dir(repo_root), run_id)
    os.makedirs(run_dir, exist_ok=True)

    launch = load_result.parsed_ork.launch
    eng_header = getattr(load_result.parsed_eng, "header", None)
    ork_saved = bool(ork_path and os.path.exists(ork_path))
    power_off_saved = bool(load_result.power_off_drag_path and os.path.exists(load_result.power_off_drag_path))
    power_on_saved = bool(load_result.power_on_drag_path and os.path.exists(load_result.power_on_drag_path))
    record = RunRecord(
        run_id=run_id, timestamp=datetime.now(timezone.utc).isoformat(),
        vehicle_name=load_result.parsed_ork.name,
        # ork_path is the actual uploaded file's path - load_result.parsed_ork.name
        # is the ROCKET's declared name from inside the .ork's own XML, not a
        # filename at all (a pre-existing display bug this also fixes).
        ork_filename=ork_filename or (os.path.basename(ork_path) if ork_path else "unknown.ork"),
        eng_filename=eng_filename or os.path.basename(load_result.eng_path),
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
        reefing_settings=[asdict(c) for c in load_result.parsed_ork.parachutes],
        dry_mass_override_kg=dry_mass_override_kg, dry_cg_override_m=dry_cg_override_m,
        launch_override=launch_override, competition_profile=competition_profile,
        ork_saved=ork_saved, power_off_drag_saved=power_off_saved, power_on_drag_saved=power_on_saved,
    )
    _atomic_write_json(os.path.join(run_dir, "record.json"), asdict(record))

    if ork_saved:
        shutil.copy(ork_path, os.path.join(run_dir, record.ork_filename))
    if load_result.eng_path and os.path.exists(load_result.eng_path):
        shutil.copy(load_result.eng_path, os.path.join(run_dir, record.eng_filename))
    if power_off_saved:
        shutil.copy(load_result.power_off_drag_path, os.path.join(run_dir, "power_off_drag.csv"))
    if power_on_saved:
        shutil.copy(load_result.power_on_drag_path, os.path.join(run_dir, "power_on_drag.csv"))
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


class MissionNotReopenableError(ValueError):
    """Raised when a run predates this feature (no saved .ork copy) or
    its saved files have gone missing - reopen_run() never silently
    guesses at a substitute .ork."""


def reopen_run(repo_root, run_id, outputs_dir):
    """2026-09-27 review item 2/4: rebuilds a full, ready-to-simulate
    session state from a past run - the .ork/.eng/drag CSVs this run
    itself saved, re-parsed fresh, with reefing settings/mass overrides/
    weather override/competition profile re-applied on top. Returns a
    dict matching the keys gui/state.py's state dict expects for these
    fields (NOT gui.state itself - this module stays NiceGUI-free; the
    caller, e.g. the History page, copies these into state.state).

    Raises MissionNotReopenableError if this run has no saved .ork (a
    run saved before this feature existed) or its files are missing -
    never fabricates a substitute."""
    import dataclasses

    record = get_run(repo_root, run_id)
    if record is None:
        raise MissionNotReopenableError(f"run '{run_id}' not found or its record.json is corrupt")
    if not record.ork_saved:
        raise MissionNotReopenableError(
            f"run '{run_id}' has no saved .ork copy (it predates this feature) - it can be viewed but not reopened. "
            "Re-run Simulate on the original files to create a reopenable mission."
        )

    run_dir = os.path.join(_runs_dir(repo_root), run_id)
    ork_path = os.path.join(run_dir, record.ork_filename)
    eng_path = os.path.join(run_dir, record.eng_filename)
    power_off_path = os.path.join(run_dir, "power_off_drag.csv") if record.power_off_drag_saved else None
    power_on_path = os.path.join(run_dir, "power_on_drag.csv") if record.power_on_drag_saved else None
    if not os.path.exists(ork_path) or not os.path.exists(eng_path):
        raise MissionNotReopenableError(f"run '{run_id}' claims saved files but they're missing from {run_dir} - the run folder may have been partially deleted.")

    # Deferred import: gui/pipeline.py has NO NiceGUI import (its own
    # module docstring), same reasoning as report.py's deferred import
    # of gui/rocket_drawing.py - reusing the app's own load_files() here
    # (rather than a second hand-written .ork/.eng parsing path) is
    # exactly the "ONE path" rule this project already follows elsewhere.
    from bup_rocketpy.gui import pipeline

    load_result = pipeline.load_files(ork_path, eng_path, power_off_path, power_on_path, outputs_dir=outputs_dir)

    if record.reefing_settings:
        by_name = {c["name"]: c for c in record.reefing_settings}
        load_result.parsed_ork.parachutes = [
            dataclasses.replace(chute, **{k: v for k, v in by_name.get(chute.name, {}).items() if k != "name"})
            if chute.name in by_name else chute
            for chute in load_result.parsed_ork.parachutes
        ]

    launch_override = None
    if record.launch_override:
        from bup_rocketpy.ork_reader import LaunchConditions
        launch_override = LaunchConditions(**record.launch_override)

    return {
        "load_result": load_result,
        "ork_path": ork_path, "ork_filename": record.ork_filename, "eng_filename": record.eng_filename,
        "dry_mass_override": record.dry_mass_override_kg, "dry_cg_override": record.dry_cg_override_m,
        "launch_override": launch_override,
        "competition_profile": record.competition_profile or "lasc",
        "vehicle_name": record.vehicle_name, "mission_id": record.run_id,
    }


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
