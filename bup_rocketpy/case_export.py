"""Exports a self-contained .py AND .ipynb per RCSM case (CRS 10.1.3/
10.1.5/10.1.6): "a runnable .py or .ipynb" that "a RocketPy team member
or LASC staff can run on their own machine" with "just pip install
rocketpy" - no import of this repo's own bup_rocketpy package. Every
geometry/mass/motor/launch value gets baked in as a literal in the
generated file; only the .eng and the two drag-curve CSVs stay as
separate sibling files (CRS 10.1.9 wants the .eng itself delivered
anyway), referenced by relative path.

File name: Mission[ID]_[Case]_RocketPy_v[N].py/.ipynb (CRS 10.1.6).

2026-10-20 review ("judge-grade LASC package"): both the .py and the
.ipynb are built from the SAME ordered list of sections (title,
markdown explanation, code lines) via _build_case_sections() - one
physics-to-code path, two renderings, so they can never silently
diverge from each other. Each script also now opens with a clearly
marked INPUTS block (mass, CG, inertia, rail geometry, wind, site,
launch date/time - CRS 10.2.1's Launch Readiness Review is exactly
when these get updated with as-measured values) with units and a
source note per line, and closes with a clean results table (no
internal/variable names) plus a results.json a verification step can
read back without screen-scraping prose, and non-interactively saved
plots (CLAUDE.md Sec 6 Phase 5 / this review's own item 6).
"""
import json
import math
import os

from bup_rocketpy.ork_reader import airframe_length_m


def _fmt(x):
    return repr(float(x))


def _clean_comment(text):
    """A '#' comment can't contain a literal newline - defensively
    collapse one if a source string ever picked one up."""
    return " ".join(str(text).split())


class _Section:
    __slots__ = ("title", "markdown", "lines")

    def __init__(self, title, markdown):
        self.title = title
        self.markdown = markdown
        self.lines = []

    def a(self, line):
        self.lines.append(line)


def _build_case_sections(mission_id, case_name, version, parsed, parsed_eng, eng_filename, power_off_drag_filename, power_on_drag_filename, dry_mass_kg, dry_cg_m, i_axial, i_transverse, radius_m, include_recovery, coordinate_system_orientation="tail_to_nose", mission_id_template=None, launch_override=None, motor_dry_override_kg=None, recovery_chute=None, recovery_force_apogee=False, mass_source=None, inertia_source=None, launch_date_time_str=None, include_results_section=True):
    """Returns (filename_stem, [Section, ...]) - filename_stem has no
    extension (the caller adds .py or .ipynb). See generate_case_script's
    docstring for every parameter's meaning; mass_source/inertia_source/
    launch_date_time_str are new (2026-10-20 review, judge-grade LASC
    package) and purely textual - they feed the INPUTS block's "source"
    notes and change no physics. None (the default, for any existing
    caller) renders an honest "not recorded" note instead of guessing.

    include_results_section=False (2026-10-20 review, judge-grade LASC
    package): omits the single-flight Results section at the end - used
    by mc_export.py, which needs the IDENTICAL Setup/Inputs/Environment/
    Motor/Rocket/Recovery/Flight sections (so the Monte Carlo script's
    nominal vehicle can never silently diverge from this case's own
    deterministic one) but appends its own Monte Carlo-specific results
    instead of a single flight.info()-style summary."""
    effective_launch = launch_override if launch_override is not None else parsed.launch
    if mission_id_template is not None:
        filename_stem = mission_id_template.format(id=mission_id, case=case_name, version=version)
    else:
        filename_stem = f"Mission{mission_id}_{case_name}_RocketPy_v{version}"

    to_rpy_sign = -1.0 if coordinate_system_orientation == "tail_to_nose" else 1.0
    nose_pos = to_rpy_sign * 0.0
    # 2026-09-27 review item 1c: airframe_length_m() (nose + body tubes +
    # transitions), matching translate.build_rocket's own motor placement -
    # a body-tubes-only formula silently missed a transition/boat-tail
    # placed after the last body tube.
    motor_pos = to_rpy_sign * airframe_length_m(parsed)

    sections = []

    # ---- Setup -------------------------------------------------------
    s = _Section("Setup", (
        f"**{filename_stem}** - self-contained RocketPy simulation, **{case_name}** case, Mission {mission_id}.\n\n"
        "Requires only `pip install rocketpy` - no other file from the Beyond UP RocketPy repo is imported.\n\n"
        f"Run alongside this file: `{eng_filename}`, `{power_off_drag_filename}`, `{power_on_drag_filename}`.\n\n"
        "Model validation status and every documented approximation (mass/CG source, drag curve source) "
        "are on the app's own Validation page - this script is a frozen snapshot of one simulated case."
    ))
    a = s.a
    a("import json")
    a("import math")
    a("import os")
    a("import sys")
    a("")
    # Must precede `import rocketpy` - rocketpy imports matplotlib.pyplot
    # at module load time, which silently locks in whatever GUI backend
    # is available FIRST; forcing Agg here guarantees no window ever
    # opens when this runs on a machine with no display (a CI box, a
    # judge's headless re-run) - item 6 of this review.
    a("import matplotlib")
    a('matplotlib.use("Agg")')
    a("from rocketpy import Environment, SolidMotor, Rocket, Flight")
    a("")
    # 2026-09-30 review item 3 (found running the full suite under a
    # Windows-like non-UTF-8 default encoding): the results table below
    # prints Greek letters (e.g. a stability-margin symbol) - on a real
    # Windows console (cp1252 or another non-UTF-8 codepage, the common
    # case unless the user opted into "Use Unicode UTF-8 for worldwide
    # language support") that would raise UnicodeEncodeError and crash
    # the standalone script outright, which is exactly the CRS 10.1.5
    # "a RocketPy team member or LASC staff can run it on their own
    # machine" scenario this file exists for. reconfigure() is a no-op
    # (silently ignored) on a stdout that doesn't support it (rare, e.g.
    # some captured/piped streams), so this is safe everywhere.
    a("if hasattr(sys.stdout, 'reconfigure'):")
    a("    sys.stdout.reconfigure(encoding='utf-8')")
    a("")
    a("try:")
    a("    HERE = os.path.dirname(os.path.abspath(__file__))")
    a("except NameError:")
    a("    HERE = os.getcwd()  # running inside a Jupyter notebook - __file__ isn't defined; assumes the notebook was launched from its own folder, alongside its sibling .eng/CSV files (the normal way to open it)")
    a("RESULTS_DIR = os.path.join(HERE, 'results_' + " + repr(filename_stem) + ")  # plots + results.json land here, nothing opens a window")
    a("os.makedirs(RESULTS_DIR, exist_ok=True)")
    sections.append(s)

    from bup_rocketpy.translate import motor_grain_params, wind_uv  # noqa: F401 (wind_uv only used for its formula, re-derived below standalone)

    # ---- Inputs --------------------------------------------------------
    mass_source_text = _clean_comment(mass_source) if mass_source else "not recorded - re-check against OpenRocket/measured values before the Launch Readiness Review"
    inertia_source_text = _clean_comment(inertia_source) if inertia_source else "geometric estimate (approximate - see the app's Rocket page)"
    launch_source_text = (
        "real launch-day weather (Launch Day page, overrides the .ork's own recorded conditions)"
        if launch_override is not None else
        "the .ork's own recorded launch conditions - replace with real launch-day weather before submission"
    )
    h = parsed_eng.header
    motor_dry_mass = motor_dry_override_kg if motor_dry_override_kg is not None else (h.total_mass_kg - h.propellant_mass_kg)
    motor_mass_source_text = "measured override (operator-entered, overrides the .eng header)" if motor_dry_override_kg is not None else "the .eng header's own declared dry mass"
    launch_date_time_literal = repr(_clean_comment(launch_date_time_str)) if launch_date_time_str else "None"
    launch_date_time_source = _clean_comment(launch_date_time_str) if launch_date_time_str else "not recorded - edit with the actual flight date/time before the Launch Readiness Review (CRS 10.2.1)"

    s = _Section("Inputs (Launch Readiness Review, CRS 10.2.1)", (
        "Every value below is what this script was generated with, together with where it came from. "
        "**Edit these in place** if LASC officials measure a different value on site at the Launch Readiness "
        "Review - every later block reads these names, not a second hard-coded copy, so one edit here is enough."
    ))
    a = s.a
    a(f"DRY_MASS_KG = {_fmt(dry_mass_kg)}  # kg, dry mass without the motor - source: {mass_source_text}")
    a(f"DRY_CG_M = {_fmt(dry_cg_m)}  # m from the nose tip - source: {mass_source_text}")
    a(f"I_AXIAL_KGM2 = {_fmt(i_axial)}  # kg*m^2, roll axis - source: {inertia_source_text}")
    a(f"I_TRANSVERSE_KGM2 = {_fmt(i_transverse)}  # kg*m^2, pitch/yaw axis - source: {inertia_source_text}")
    a(f"MOTOR_DRY_MASS_KG = {_fmt(motor_dry_mass)}  # kg, motor casing mass with no propellant - source: {motor_mass_source_text}")
    a(f"RAIL_LENGTH_M = {_fmt(effective_launch.rail_length_m)}  # m - source: {launch_source_text}")
    a(f"RAIL_INCLINATION_DEG = {_fmt(effective_launch.inclination_deg)}  # deg from horizontal, rocketpy convention (90 = vertical) - source: {launch_source_text}")
    a(f"RAIL_HEADING_DEG = {_fmt(effective_launch.rail_direction_deg)}  # deg, compass bearing the rail points toward - source: {launch_source_text}")
    a(f"WIND_SPEED_MS = {_fmt(effective_launch.wind_average_ms)}  # m/s average wind - source: {launch_source_text}")
    a(f"WIND_DIRECTION_DEG = {_fmt(effective_launch.wind_direction_deg)}  # deg, compass bearing the wind blows FROM - source: {launch_source_text}")
    a(f"SITE_LATITUDE_DEG = {_fmt(effective_launch.latitude)}  # source: {launch_source_text}")
    a(f"SITE_LONGITUDE_DEG = {_fmt(effective_launch.longitude)}  # source: {launch_source_text}")
    a(f"SITE_ELEVATION_M = {_fmt(effective_launch.altitude_m)}  # m MSL - source: {launch_source_text}")
    a(f"LAUNCH_DATE_TIME = {launch_date_time_literal}  # informational only, the standard-atmosphere model below does not use it directly - source: {launch_date_time_source}")
    sections.append(s)

    # ---- Environment ---------------------------------------------------
    s = _Section("Environment", (
        "A standard atmosphere model at the launch site's own coordinates and elevation, with the wind applied "
        "as a constant East/North gust (rocketpy's `add_wind_gust`) derived from the speed + compass bearing above."
    ))
    a = s.a
    a("env = Environment(latitude=SITE_LATITUDE_DEG, longitude=SITE_LONGITUDE_DEG, elevation=SITE_ELEVATION_M)")
    a('env.set_atmospheric_model(type="standard_atmosphere")')
    a("wind_bearing_rad = math.radians(WIND_DIRECTION_DEG + 180.0)  # the wind VELOCITY points opposite its own \"blowing from\" bearing")
    a("wind_u = WIND_SPEED_MS * math.sin(wind_bearing_rad)")
    a("wind_v = WIND_SPEED_MS * math.cos(wind_bearing_rad)")
    a("if WIND_SPEED_MS:")
    a("    env.add_wind_gust(wind_u, wind_v)")
    sections.append(s)

    # ---- Motor ----------------------------------------------------------
    s = _Section("Motor (CRS 10.1.9)", (
        "The real, measured thrust curve from the SRAD motor's `.eng` file, baked in here as a literal list "
        "(not re-parsed from the `.eng` at run time - rocketpy's own `.eng` parser unconditionally inserts a "
        "`(0, 0)` point, which double-counts a curve that already starts at t=0). The `.eng` itself still ships "
        "alongside this script, as CRS 10.1.9 requires."
    ))
    a = s.a
    grain_outer_r, grain_inner_r, grain_height, grain_density = motor_grain_params(h)
    a(f"thrust_curve = {parsed_eng.thrust_curve!r}")
    a("")
    a("motor = SolidMotor(")
    a("    thrust_source=thrust_curve,")
    a("    dry_mass=MOTOR_DRY_MASS_KG,")
    a("    dry_inertia=(0.01, 0.01, 0.001),  # not recoverable from a RASP .eng header - approximate, see reference/prometeo_mission44/src/prometeo/motor.py for the same convention")
    a(f"    nozzle_radius={_fmt((h.diameter_mm / 1000.0) * 0.15)},")
    a("    grain_number=1,")
    a(f"    grain_density={_fmt(grain_density)},  # solved to exactly match the .eng header's declared propellant mass, see translate.motor_grain_params")
    a(f"    grain_outer_radius={_fmt(grain_outer_r)},")
    a(f"    grain_initial_inner_radius={_fmt(grain_inner_r)},")
    a(f"    grain_initial_height={_fmt(grain_height)},")
    a("    grain_separation=0.005,")
    a(f"    grains_center_of_mass_position={_fmt((h.length_mm / 1000.0) / 2.0)},")
    a(f"    center_of_dry_mass_position={_fmt((h.length_mm / 1000.0) / 2.0)},")
    a("    nozzle_position=0,")
    a(f"    burn_time={_fmt(parsed_eng.burn_time_s)},")
    a(f"    throat_radius={_fmt((h.diameter_mm / 1000.0) * 0.1)},")
    a('    coordinate_system_orientation="nozzle_to_combustion_chamber",')
    a(")")
    sections.append(s)

    # ---- Rocket (geometry) ----------------------------------------------
    s = _Section("Rocket", (
        "Dry mass/CG/inertia from the INPUTS block above, plus every real fin set, nose cone and rail button "
        "parsed from the `.ork`. Drag is supplied as power-off/power-on Cd-vs-Mach curves (rocketpy does not "
        "compute Cd from geometry) - see the sibling CSV files."
    ))
    a = s.a
    a("rocket = Rocket(")
    a(f"    radius={_fmt(radius_m)},")
    a("    mass=DRY_MASS_KG,")
    a("    inertia=(I_TRANSVERSE_KGM2, I_TRANSVERSE_KGM2, I_AXIAL_KGM2),")
    a('    power_off_drag=os.path.join(HERE, "' + power_off_drag_filename + '"),')
    a('    power_on_drag=os.path.join(HERE, "' + power_on_drag_filename + '"),')
    a(f"    center_of_mass_without_motor={_fmt(to_rpy_sign)} * DRY_CG_M,")
    a(f'    coordinate_system_orientation="{coordinate_system_orientation}",')
    a(")")
    a(f"rocket.add_motor(motor, position={_fmt(motor_pos)})")
    a("")
    if parsed.nose is not None:
        from bup_rocketpy.translate import rocketpy_nose_kind
        a(f'rocket.add_nose(length={_fmt(parsed.nose.length)}, kind="{rocketpy_nose_kind(parsed.nose.shape)}", position={_fmt(nose_pos)})')
    for fin in parsed.fins:
        # 2026-10-09 review item 2: this exported script is the ACTUAL CRS
        # 10.1.6 deliverable LASC runs - it must build the SAME fin shape
        # translate.build_rocket does, not the trapezoid surrogate (see
        # ork_reader.FinSet's docstring) every other fin field here is
        # borrowed from for the hand-calc/drawing paths only.
        if fin.shape == "elliptical":
            a("rocket.add_elliptical_fins(")
            a(f"    n={fin.count}, root_chord={_fmt(fin.root_chord)}, span={_fmt(fin.span)},")
            a(f"    cant_angle={_fmt(fin.cant_angle)}, position={_fmt(to_rpy_sign * fin.position_m)},")
            a(")")
        elif fin.shape == "freeform" and fin.fin_points:
            a("rocket.add_free_form_fins(")
            a(f"    n={fin.count}, shape_points={fin.fin_points!r},")
            a(f"    cant_angle={_fmt(fin.cant_angle)}, position={_fmt(to_rpy_sign * fin.position_m)},")
            a(")")
        else:
            a("rocket.add_trapezoidal_fins(")
            a(f"    n={fin.count}, root_chord={_fmt(fin.root_chord)}, tip_chord={_fmt(fin.tip_chord)},")
            a(f"    span={_fmt(fin.span)}, sweep_length={_fmt(fin.sweep_length)}, cant_angle={_fmt(fin.cant_angle)},")
            a(f"    position={_fmt(to_rpy_sign * fin.position_m)},")
            a(")")
    if parsed.rail_buttons is not None:
        a(f"rocket.set_rail_buttons(upper_button_position={_fmt(to_rpy_sign * parsed.rail_buttons.upper_position_m)}, lower_button_position={_fmt(to_rpy_sign * parsed.rail_buttons.lower_position_m)})")
    sections.append(s)

    # ---- Recovery ---------------------------------------------------------
    recovery_markdown = "No recovery system - this is the Ballistic case (CRS 10.1.11): free-fall under drag alone."
    s_title = "Recovery: none (Ballistic case)"
    if include_recovery and recovery_chute is not None:
        s_title = "Recovery (single chute - Drogue-only / Main-at-apogee case)"
        recovery_markdown = (
            "CRS 10.1.12/10.1.13 require testing each recovery stage in isolation - only the ONE chute this "
            "case is named for is added here, with its real trigger (or forced to apogee, for Main-at-apogee)."
        )
    elif include_recovery:
        s_title = "Recovery (CRS 10.1.9: trigger, phase, size, Cd)"
        recovery_markdown = (
            "Every real parachute from the `.ork`, with its real trigger, size and Cd. A reefed main with a "
            "line cutter is one physical canopy that opens in two stages - modeled here as two rocketpy "
            "`Parachute` objects (the reefed stage, then the full canopy), matching the app's own physics "
            "exactly rather than a single wrong-size chute."
        )
    s = _Section(s_title, recovery_markdown)
    a = s.a
    if include_recovery and recovery_chute is not None:
        from bup_rocketpy.translate import parachute_trigger

        chute = recovery_chute
        cd_s = chute.cd * math.pi * (chute.diameter / 2.0) ** 2
        if recovery_force_apogee:
            trigger = '"apogee"'
        else:
            trigger_value, trigger_warning = parachute_trigger(chute)
            if trigger_warning:
                a(f"# NOTE: {trigger_warning}")
            trigger = '"apogee"' if trigger_value == "apogee" else _fmt(trigger_value)
        a(f'rocket.add_parachute(name={chute.name!r}, cd_s={_fmt(cd_s)}, trigger={trigger}, sampling_rate=100, lag={_fmt(chute.deploy_delay or 0.0)})')
    elif include_recovery:
        from bup_rocketpy.translate import parachute_trigger

        # 2026-10-19 review ("check every bug" audit, findings #3/#4 of
        # the report/export report): this loop used to add exactly ONE
        # rocketpy Parachute per <parachute> in the .ork, with no
        # dedup - two real divergences from translate.build_rocket()
        # (what the app itself actually flies):
        #   - a reefed main + line cutter (a real, supported topology -
        #     see ork_reader/rcsm_cases) is ONE physical canopy that
        #     opens in TWO stages; flying it as a single chute here gave
        #     this script completely different (wrong) recovery physics
        #     and descent numbers than what the app reported.
        #   - two parachutes resolving to the exact same (trigger, lag)
        #     make rocketpy insert a duplicate timestamp in the flight
        #     solution, which later crashes with "array must not contain
        #     infs or NaNs" inside its own cubic-spline fitting -
        #     translate.build_rocket() nudges the lag apart to avoid
        #     this; this script didn't, so a vehicle the app itself can
        #     simulate fine could still crash as a standalone CRS
        #     10.1.5 submission. Both are now computed exactly the same
        #     way translate.build_rocket() does, so this script can
        #     never silently diverge from what the app actually flew.
        def _chute_keys(chute):
            trigger, _ = parachute_trigger(chute)
            keys = [(trigger, chute.deploy_delay or 0.0)]
            if chute.is_reefed and chute.reefed_cd is not None and chute.reefed_diameter_m is not None and chute.cutter_altitude_m is not None:
                keys.append((chute.cutter_altitude_m, chute.cutter_delay_s or 0.0))
            return keys

        trigger_lag_counts = {}
        for chute in parsed.parachutes:
            if chute.cd is None:
                continue
            for key in _chute_keys(chute):
                trigger_lag_counts[key] = trigger_lag_counts.get(key, 0) + 1
        seen_trigger_lag = {}

        def _dedupe_lag(trigger, lag):
            lag = lag or 0.0
            key = (trigger, lag)
            if trigger_lag_counts.get(key, 0) < 2:
                return lag
            count = seen_trigger_lag.get(key, 0)
            seen_trigger_lag[key] = count + 1
            return lag + (count + 1) * 0.0137  # same nudge translate.build_rocket() uses - see that function's own comment

        for chute in parsed.parachutes:
            if chute.cd is None:
                a(f"# SKIPPED parachute {chute.name!r}: Cd was 'auto' in OpenRocket, not resolvable from the .ork file - add it manually")
                continue
            trigger_value, trigger_warning = parachute_trigger(chute)
            if trigger_warning:
                a(f"# NOTE: {trigger_warning}")
            trigger = '"apogee"' if trigger_value == "apogee" else _fmt(trigger_value)

            if chute.is_reefed and chute.reefed_cd is not None and chute.reefed_diameter_m is not None and chute.cutter_altitude_m is not None:
                reefed_cd_s = chute.reefed_cd * math.pi * (chute.reefed_diameter_m / 2.0) ** 2
                reefed_lag = _dedupe_lag(trigger_value, chute.deploy_delay)
                a(f'rocket.add_parachute(name={(chute.name + " (reefed)")!r}, cd_s={_fmt(reefed_cd_s)}, trigger={trigger}, sampling_rate=100, lag={_fmt(reefed_lag)})')
                full_cd_s = chute.cd * math.pi * (chute.diameter / 2.0) ** 2
                full_lag = _dedupe_lag(chute.cutter_altitude_m, chute.cutter_delay_s)
                a(f'rocket.add_parachute(name={(chute.name + " (full)")!r}, cd_s={_fmt(full_cd_s)}, trigger={_fmt(chute.cutter_altitude_m)}, sampling_rate=100, lag={_fmt(full_lag)})')
                continue

            cd_s = chute.cd * math.pi * (chute.diameter / 2.0) ** 2
            lag = _dedupe_lag(trigger_value, chute.deploy_delay)
            a(f'rocket.add_parachute(name={chute.name!r}, cd_s={_fmt(cd_s)}, trigger={trigger}, sampling_rate=100, lag={_fmt(lag)})')
    else:
        a("pass  # no recovery system in this case - the rocket free-falls under drag alone")
    sections.append(s)

    # ---- Flight -------------------------------------------------------
    s = _Section("Flight (CRS 10.1.8)", (
        "Runs the simulation with the rail geometry from the INPUTS block above."
    ))
    a = s.a
    a("flight = Flight(")
    a("    rocket=rocket,")
    a("    environment=env,")
    a("    rail_length=RAIL_LENGTH_M,")
    a("    inclination=RAIL_INCLINATION_DEG,")
    a("    heading=RAIL_HEADING_DEG,")
    # 2026-10-20 review ("judge-grade LASC package", item 5 - caught by
    # the new verification gate comparing this script against the app's
    # OWN Ballistic flight): rcsm_cases.py/monte_carlo.py/analysis.py/
    # validation.py all consistently stop the Ballistic (no-recovery)
    # case AT APOGEE rather than simulating a genuinely out-of-control
    # tumbling re-entry - report.py's own wording for it is literally
    # "apogee only (recovery/descent not modeled)". The reason is
    # physical, not a shortcut: the power-off/power-on drag curves this
    # app uses are calibrated for a nose-forward, stable ascent, and
    # produce an arbitrary (not a MORE complete) number for a chaotic
    # tumble, which a real axial Cd-vs-Mach curve cannot credibly
    # represent at all. This export used to keep integrating anyway,
    # silently describing a different (and not more correct) flight
    # than the one every other page of the app reports as "Ballistic".
    a(f"    terminate_on_apogee={not include_recovery},")
    a(")")
    sections.append(s)

    if not include_results_section:
        return filename_stem, sections

    # ---- Results --------------------------------------------------------
    s = _Section("Results", (
        "A clean summary table (no internal variable names), the standard flight plots saved to a results "
        "folder instead of opening a window, and a `results.json` with the same numbers for automated checking."
    ))
    a = s.a
    a("ascent_times = [t for t in flight.time if flight.out_of_rail_time <= t <= flight.apogee_time] or [flight.apogee_time]")
    a("min_static_margin_cal = min(flight.stability_margin(t) for t in ascent_times)")
    a("")
    a("parachute_results = []")
    a("events = list(getattr(flight, 'parachute_events', []))")
    a("for i, (t_deploy, chute) in enumerate(events):")
    a("    next_t = events[i + 1][0] if i + 1 < len(events) else None")
    a("    t_sample = (next_t - 0.05) if next_t is not None else (flight.t_final - 0.05)")
    a("    t_sample = max(t_sample, t_deploy + 0.01)")
    a("    vx, vy, vz = flight.vx(t_sample), flight.vy(t_sample), flight.vz(t_sample)")
    a("    descent_rate_ms = math.sqrt(vx ** 2 + vy ** 2 + vz ** 2)")
    a("    parachute_results.append({")
    a("        'name': getattr(chute, 'name', f'parachute {i + 1}'),")
    a("        'deploy_time_s': t_deploy,")
    a("        'deploy_altitude_agl_m': flight.z(t_deploy) - env.elevation,")
    a("        'descent_rate_ms': descent_rate_ms,")
    a("    })")
    a("")
    a("results = {")
    a(f"    'mission_id': {mission_id!r},")
    a(f"    'case': {case_name!r},")
    a("    'apogee_agl_m': flight.apogee - env.elevation,")
    a("    'max_speed_ms': flight.max_speed,")
    a("    'max_mach': flight.max_mach_number,")
    a("    'max_acceleration_ms2': flight.max_acceleration,")
    a("    'rail_exit_velocity_ms': flight.out_of_rail_velocity,")
    a("    'flight_time_s': flight.t_final,")
    a("    'min_static_margin_cal': min_static_margin_cal,")
    a("    'landing_x_m': flight.x_impact,")
    a("    'landing_y_m': flight.y_impact,")
    a("    'landing_speed_ms': abs(flight.impact_velocity),  # rocketpy's own sign convention is signed-vertical; magnitude is what the app's own recovery panel/report show")
    a("    'parachute_events': parachute_results,")
    a("}")
    a("with open(os.path.join(RESULTS_DIR, 'results.json'), 'w', encoding='utf-8') as f:")
    a("    json.dump(results, f, indent=2)")
    a("")
    a("print()")
    a("print('=' * 60)")
    a(f"print('RESULTS - {_clean_comment(case_name)} case, Mission {_clean_comment(str(mission_id))}')")
    a("print('=' * 60)")
    a("print(f\"Apogee AGL:              {results['apogee_agl_m']:.1f} m\")")
    a("print(f\"Max speed:               {results['max_speed_ms']:.1f} m/s\")")
    a("print(f\"Max Mach number:         {results['max_mach']:.3f}\")")
    a("print(f\"Max acceleration:        {results['max_acceleration_ms2']:.1f} m/s^2\")")
    a("print(f\"Rail exit velocity:      {results['rail_exit_velocity_ms']:.1f} m/s\")")
    a("print(f\"Flight time:             {results['flight_time_s']:.1f} s\")")
    a("print(f\"Minimum static margin:   {results['min_static_margin_cal']:.2f} cal\")")
    a("print(f\"Landing point (x, y):    ({results['landing_x_m']:.1f}, {results['landing_y_m']:.1f}) m from the launch rail\")")
    a("print(f\"Landing speed:           {results['landing_speed_ms']:.1f} m/s\")")
    a("if parachute_results:")
    a("    print('Recovery events:')")
    a("    for p in parachute_results:")
    a("        print(f\"  {p['name']}: deployed at t={p['deploy_time_s']:.1f} s, {p['deploy_altitude_agl_m']:.0f} m AGL, descent rate ~{p['descent_rate_ms']:.1f} m/s\")")
    a("else:")
    a("    print('Recovery events: none (Ballistic case)')")
    a("print('=' * 60)")
    a("print(f'Full plots and results.json saved to: {RESULTS_DIR}')")
    a("")
    a("flight.plots.linear_kinematics_data(filename=os.path.join(RESULTS_DIR, 'kinematics.png'))")
    a("flight.plots.fluid_mechanics_data(filename=os.path.join(RESULTS_DIR, 'fluid_mechanics.png'))")
    a("flight.plots.stability_and_control_data(filename=os.path.join(RESULTS_DIR, 'stability.png'))")
    a("flight.plots.trajectory_3d(filename=os.path.join(RESULTS_DIR, 'trajectory_3d.png'))")
    sections.append(s)

    return filename_stem, sections


def generate_case_script(mission_id, case_name, version, parsed, parsed_eng, eng_filename, power_off_drag_filename, power_on_drag_filename, dry_mass_kg, dry_cg_m, i_axial, i_transverse, radius_m, include_recovery, coordinate_system_orientation="tail_to_nose", mission_id_template=None, launch_override=None, motor_dry_override_kg=None, recovery_chute=None, recovery_force_apogee=False, mass_source=None, inertia_source=None, launch_date_time_str=None):
    """Returns (filename, source_code). case_name is one of "Ballistic",
    "Nominal", "DrogueOnly", "MainAtApogee" (CRS 10.1.6/10.1.10-13).

    mission_id_template: 2026-09-26 review item H.2 (competition
    profiles) - an optional "{id}_{case}_{version}"-style template (see
    bup_rocketpy.competition_profiles) for a competition other than LASC.
    None (the default) keeps CRS 10.1.6's exact naming, unchanged.

    launch_override (2026-10-19 review, "check every bug" audit, finding
    #2): a LaunchConditions to use INSTEAD of parsed.launch - e.g. real
    launch-day weather from the Launch Day page (gui.pipeline.
    run_simulation's own same-named parameter). Without this, a report/
    export generated AFTER applying real weather would still describe
    "the .ork's own recorded conditions" while actually having simulated
    (and reported results for) the real-weather flight - a genuine
    mismatch between what this script says it does and what the app
    itself just flew. None (the default) keeps parsed.launch, unchanged.

    motor_dry_override_kg: the same "Measured motor mass" correction
    translate.build_motor already supports - see that function's own
    docstring. None (the default) keeps the .eng header's own value.

    recovery_chute/recovery_force_apogee (2026-10-19 review, "check
    every bug" audit, finding #6 - this function previously had NO way
    to represent a DrogueOnly/MainAtApogee case at all, so those names
    were never offered for export): when recovery_chute is given (a
    single real or reefed-surrogate Parachute, from rcsm_cases.
    _classify_parachutes/_reefed_surrogates - the caller resolves which
    one), ONLY that one chute is added with a plain trigger mapping (NOT
    the reefed-expansion/dedup logic below, which is for Nominal's "every
    real chute" case and would double-count an already-resolved
    surrogate). recovery_force_apogee=True overrides its trigger to
    "apogee" regardless of its own configured deploy event - the
    Main-at-apogee case's own definition (CRS 10.1.13).

    mass_source/inertia_source/launch_date_time_str (2026-10-20 review,
    judge-grade LASC package): textual provenance for the INPUTS block's
    "source" notes (e.g. state["mass_source"]/state["inertia_source"]).
    None (the default) renders an honest "not recorded" note rather than
    guessing - see _build_case_sections's own docstring."""
    filename_stem, sections = _build_case_sections(
        mission_id, case_name, version, parsed, parsed_eng, eng_filename, power_off_drag_filename, power_on_drag_filename,
        dry_mass_kg, dry_cg_m, i_axial, i_transverse, radius_m, include_recovery,
        coordinate_system_orientation=coordinate_system_orientation, mission_id_template=mission_id_template,
        launch_override=launch_override, motor_dry_override_kg=motor_dry_override_kg,
        recovery_chute=recovery_chute, recovery_force_apogee=recovery_force_apogee,
        mass_source=mass_source, inertia_source=inertia_source, launch_date_time_str=launch_date_time_str,
    )
    lines = [f'"""{filename_stem}.py - generated by Beyond UP RocketPy. Self-contained: requires only `pip install rocketpy`."""']
    for section in sections:
        lines.append("")
        lines.append(f"# --- {section.title} ---")
        lines.extend(section.lines)
    return filename_stem + ".py", "\n".join(lines) + "\n"


def generate_case_notebook(mission_id, case_name, version, parsed, parsed_eng, eng_filename, power_off_drag_filename, power_on_drag_filename, dry_mass_kg, dry_cg_m, i_axial, i_transverse, radius_m, include_recovery, coordinate_system_orientation="tail_to_nose", mission_id_template=None, launch_override=None, motor_dry_override_kg=None, recovery_chute=None, recovery_force_apogee=False, mass_source=None, inertia_source=None, launch_date_time_str=None):
    """Returns (filename, notebook_json_text) - the exact same simulation
    as generate_case_script's twin .py (same _build_case_sections() call,
    so the two can never diverge), rendered as a Jupyter notebook: one
    markdown cell explaining each block (environment, motor, rocket,
    recovery, flight), then its code cell, with the results/plots cell
    last. Every parameter is identical to generate_case_script's own -
    see that function's docstring."""
    filename_stem, sections = _build_case_sections(
        mission_id, case_name, version, parsed, parsed_eng, eng_filename, power_off_drag_filename, power_on_drag_filename,
        dry_mass_kg, dry_cg_m, i_axial, i_transverse, radius_m, include_recovery,
        coordinate_system_orientation=coordinate_system_orientation, mission_id_template=mission_id_template,
        launch_override=launch_override, motor_dry_override_kg=motor_dry_override_kg,
        recovery_chute=recovery_chute, recovery_force_apogee=recovery_force_apogee,
        mass_source=mass_source, inertia_source=inertia_source, launch_date_time_str=launch_date_time_str,
    )

    import uuid

    def _cell(cell_type, source_lines):
        return {
            "id": uuid.uuid4().hex[:16],  # nbformat 4.5+ requires a unique id per cell
            "cell_type": cell_type,
            "metadata": {},
            "source": [line + "\n" for line in source_lines[:-1]] + ([source_lines[-1]] if source_lines else []),
            **({"outputs": [], "execution_count": None} if cell_type == "code" else {}),
        }

    cells = [_cell("markdown", [
        f"# {filename_stem}", "",
        f"Self-contained RocketPy simulation - **{case_name}** case, Mission {mission_id}.",
        "Requires only `pip install rocketpy` - run every cell top to bottom.",
    ])]
    for section in sections:
        cells.append(_cell("markdown", [f"## {section.title}", "", section.markdown]))
        cells.append(_cell("code", list(section.lines) or ["pass"]))

    notebook = {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "pygments_lexer": "ipython3"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    import nbformat as _nbformat
    _nbformat.validate(_nbformat.from_dict(notebook))  # catches a malformed cell immediately, before this is ever offered for download
    return filename_stem + ".ipynb", json.dumps(notebook, indent=1) + "\n"
