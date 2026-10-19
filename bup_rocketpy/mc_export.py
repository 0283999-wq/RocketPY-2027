"""Exports a self-contained Monte Carlo dispersion analysis, Mission
[ID]_MonteCarlo_RocketPy_v[N].py/.ipynb (CRS 10.1.6-style naming,
generalized to a batch case), using rocketpy's own StochasticEnvironment/
StochasticSolidMotor/StochasticRocket/StochasticFlight/MonteCarlo classes
directly - the officially documented building blocks - with the SAME
uncertainties and sources the app's own Monte Carlo page shows (CLAUDE.md
Sec 6 Phase 4), so a LASC official re-running this gets the same
methodology (and, with the same MC_SEED, a reproducible run) as what
Diego's team actually used to produce its own apogee statistics and
landing ellipse.

2026-10-20 review ("judge-grade LASC package"): reuses case_export.
_build_case_sections(..., include_results_section=False) for the Setup/
Inputs/Environment/Motor/Rocket/Recovery/Flight sections - the NOMINAL
vehicle this Monte Carlo disperses around is built by the exact same
code as the per-case script, so the two can never silently describe two
different rockets. The three Stochastic* workarounds below (re-
registering nose/fins/parachutes on the StochasticRocket, and
monkeypatching numpy's default_rng during construction to seed it) are
NOT this module inventing anything - they are real rocketpy==1.13.0
behaviors bup_rocketpy.monte_carlo.py already had to work around (see
that module's own extensive comments and docs/rocketpy_issues/), baked
into the generated script so IT doesn't silently under-disperse/produce
an unseeded "reproducible" run that secretly isn't.
"""
import json

from bup_rocketpy import case_export


def _fmt(x):
    return repr(float(x))


def _build_mc_sections(mission_id, version, parsed, parsed_eng, eng_filename, power_off_drag_filename, power_on_drag_filename, dry_mass_kg, dry_cg_m, i_axial, i_transverse, radius_m, uncertainties, n_simulations, include_recovery=True, mission_id_template=None, launch_override=None, motor_dry_override_kg=None, mass_source=None, inertia_source=None, launch_date_time_str=None, seed=None):
    """Returns (filename_stem, [Section, ...]). uncertainties: a list of
    bup_rocketpy.monte_carlo.Uncertainty (or any object with .name/
    .nominal/.std_dev/.source/.enabled) - typically state["mc_uncertainties"],
    the SAME list the app's own Monte Carlo page edited/showed, so this
    script's INPUTS can never silently diverge from what Diego actually
    configured. Only .enabled ones are baked in and randomized - a
    disabled uncertainty is dropped entirely (its parameter stays fixed
    at the nominal value), matching run_monte_carlo()'s own behavior.

    seed: None (the default) bakes in MC_SEED = None - a genuinely
    unseeded, different-every-run analysis, matching the app's own
    interactive Monte Carlo page today. A real int makes the exported
    script reproducible run-to-run (recommended for a competition
    submission) - this module does not invent one; the caller decides."""
    filename_stem, sections = case_export._build_case_sections(
        mission_id, "MonteCarlo", version, parsed, parsed_eng, eng_filename, power_off_drag_filename, power_on_drag_filename,
        dry_mass_kg, dry_cg_m, i_axial, i_transverse, radius_m, include_recovery,
        mission_id_template=mission_id_template, launch_override=launch_override, motor_dry_override_kg=motor_dry_override_kg,
        mass_source=mass_source, inertia_source=inertia_source, launch_date_time_str=launch_date_time_str,
        include_results_section=False,
    )

    enabled = [u for u in uncertainties if u.enabled]

    # ---- Uncertainties ---------------------------------------------------
    s = case_export._Section("Uncertainties", (
        "Every randomized input, its standard deviation, and where it came from - the SAME table shown (and "
        "editable) on the app's own Monte Carlo page. A disabled uncertainty there is simply absent here, so "
        "its parameter stays fixed at the nominal value for every sample, exactly like the live run it mirrors."
    ))
    a = s.a
    a("N_SIMULATIONS = " + repr(int(n_simulations)) + "  # edit to run more/fewer samples")
    a(f"MC_SEED = {seed!r}  # an int makes this run reproducible; None (the default) draws fresh randomness every run, same as the app's own Monte Carlo page")
    a("")
    a("UNCERTAINTIES = {")
    for u in enabled:
        source = case_export._clean_comment(u.source)
        a(f"    {u.name!r}: {{'nominal': {_fmt(u.nominal)}, 'std_dev': {_fmt(u.std_dev)}, 'source': {source!r}}},")
    a("}")
    a("print('Uncertainties used in this run:')")
    a("for name, u in UNCERTAINTIES.items():")
    a("    print(f\"  {name}: {u['nominal']:.4g} +/- {u['std_dev']:.4g}  (source: {u['source']})\")")
    sections.append(s)

    # ---- Monte Carlo setup ------------------------------------------------
    s = case_export._Section("Monte Carlo setup", (
        "Wraps the nominal environment/motor/rocket/flight above in rocketpy's own Stochastic* classes. "
        "rocketpy==1.13.0's `StochasticRocket.create_object()` does not carry over a nose cone, fin set or "
        "parachute added to the nominal `Rocket` via `rocket.add_X()` - each is re-registered explicitly below, "
        "or the sampled rockets would silently fly with no aerosurfaces/recovery at all."
    ))
    a = s.a
    a("import contextlib")
    a("import numpy as np")
    a("from rocketpy import MonteCarlo, StochasticEnvironment, StochasticFlight, StochasticNoseCone, StochasticParachute, StochasticRocket, StochasticSolidMotor, StochasticTrapezoidalFins, StochasticEllipticalFins")
    a("")
    a("@contextlib.contextmanager")
    a("def _seeded_rng(seed):")
    a("    # rocketpy's Stochastic* classes draw their own numpy Generator")
    a("    # at CONSTRUCTION time (not per-sample) - this is the only point")
    a("    # that actually controls their randomness; replacing the RNG")
    a("    # object on an already-built Stochastic* instance does nothing,")
    a("    # since each uncertainty's sampler is already a bound method of")
    a("    # the generator that existed when it was built.")
    a("    if seed is None:")
    a("        yield")
    a("        return")
    a("    real_default_rng = np.random.default_rng")
    a("    np.random.default_rng = lambda *a, **k: real_default_rng(seed)")
    a("    try:")
    a("        yield")
    a("    finally:")
    a("        np.random.default_rng = real_default_rng")
    a("")
    a("wind_std = UNCERTAINTIES['wind_speed_ms']['std_dev'] / max(WIND_SPEED_MS, 0.1) if 'wind_speed_ms' in UNCERTAINTIES else 0.0")
    a("wind_factor = (1, wind_std)  # applied to BOTH axes: StochasticEnvironment samples x/y independently, so this is also the only source of wind-DIRECTION dispersion available (rocketpy has no native wind-direction parameter)")
    a("")
    a("with _seeded_rng(MC_SEED):")
    a("    stochastic_env = StochasticEnvironment(environment=env, wind_velocity_x_factor=wind_factor, wind_velocity_y_factor=wind_factor)")
    a("    stochastic_motor = StochasticSolidMotor(solid_motor=motor, total_impulse=(motor.total_impulse, UNCERTAINTIES['total_impulse_Ns']['std_dev']) if 'total_impulse_Ns' in UNCERTAINTIES else None)")
    a("    stochastic_rocket = StochasticRocket(")
    a("        rocket=rocket,")
    a("        mass=(DRY_MASS_KG, UNCERTAINTIES['dry_mass_kg']['std_dev']) if 'dry_mass_kg' in UNCERTAINTIES else None,")
    a("        center_of_mass_without_motor=(rocket.center_of_mass_without_motor, UNCERTAINTIES['dry_cg_m']['std_dev'] if 'dry_cg_m' in UNCERTAINTIES else 0),")
    a("        power_off_drag_factor=(1, UNCERTAINTIES['power_off_drag_factor']['std_dev']) if 'power_off_drag_factor' in UNCERTAINTIES else (1, 0),")
    a("        power_on_drag_factor=(1, UNCERTAINTIES['power_on_drag_factor']['std_dev']) if 'power_on_drag_factor' in UNCERTAINTIES else (1, 0),")
    a("    )")
    a("    stochastic_rocket.add_motor(stochastic_motor)")
    a("    if rocket.nosecones:")
    a("        stochastic_rocket.add_nose(StochasticNoseCone(nosecone=rocket.nosecones[0]))")
    a("    for fin_surface in rocket.fins:")
    a("        fin_kind = type(fin_surface).__name__")
    a("        if fin_kind == 'EllipticalFins':")
    a("            stochastic_rocket.add_elliptical_fins(StochasticEllipticalFins(elliptical_fins=fin_surface))")
    a("        elif fin_kind == 'FreeFormFins':")
    a("            # rocketpy has no Stochastic* class for free-form fins at all (confirmed: no StochasticFreeFormFins exists) -")
    a("            # create_object() builds the sampled Rocket from scratch out of whatever was add_X()'d here, so this fin")
    a("            # set is not approximated or frozen at its nominal shape - it is simply ABSENT from every MC sample.")
    a("            print(f\"WARNING: '{fin_surface.name}' (free-form fins) is MISSING from every Monte Carlo sample - rocketpy has no Stochastic* class for this shape.\")")
    a("        else:")
    a("            stochastic_rocket.add_trapezoidal_fins(StochasticTrapezoidalFins(trapezoidal_fins=fin_surface))")
    a("    for chute in rocket.parachutes:")
    a("        cd_s_std = chute.cd_s * UNCERTAINTIES['parachute_cd_s_factor']['std_dev'] if 'parachute_cd_s_factor' in UNCERTAINTIES else 0")
    a("        lag_std = UNCERTAINTIES['parachute_lag_s']['std_dev'] if 'parachute_lag_s' in UNCERTAINTIES else 0")
    a("        lag_is_safe = chute.lag - 2 * lag_std >= 0  # a real deploy lag is often 0 (apogee-triggered); randomizing it unconditionally would sample a NEGATIVE lag on ~half of all draws and corrupt that sample")
    a("        stochastic_rocket.add_parachute(StochasticParachute(")
    a("            parachute=chute,")
    a("            cd_s=(chute.cd_s, cd_s_std) if cd_s_std else None,")
    a("            lag=(chute.lag, lag_std) if lag_std and lag_is_safe else None,")
    a("        ))")
    a("    stochastic_flight = StochasticFlight(")
    a("        flight=flight,")
    a("        inclination=(RAIL_INCLINATION_DEG, UNCERTAINTIES['inclination_deg']['std_dev']) if 'inclination_deg' in UNCERTAINTIES else None,")
    a("        heading=(RAIL_HEADING_DEG, UNCERTAINTIES['heading_deg']['std_dev']) if 'heading_deg' in UNCERTAINTIES else None,")
    a("    )")
    sections.append(s)

    # ---- Run --------------------------------------------------------------
    s = case_export._Section("Run", (
        "`MonteCarlo.simulate()` draws N_SIMULATIONS samples, flies each one, and writes every sample's "
        "outputs to a results file next to this script - the same rocketpy class and workflow the "
        "documentation itself recommends for this exact job."
    ))
    a = s.a
    a("mc = MonteCarlo(")
    a("    filename=os.path.join(RESULTS_DIR, 'montecarlo'),")
    a("    environment=stochastic_env, rocket=stochastic_rocket, flight=stochastic_flight,")
    a(")")
    a("mc.simulate(number_of_simulations=N_SIMULATIONS, append=False)")
    a("")
    a("# mc.simulate() also writes montecarlo.inputs.txt - a FULL serialized")
    a("# copy of the environment/rocket/motor (including the entire gravity")
    a("# model and drag/thrust curves) for EVERY sample, which is several MB")
    a("# per sample and not something a reviewer needs (it exists so a later")
    a("# run with append=True can resume) - removed to keep this results")
    a("# folder a reasonable size. montecarlo.outputs.txt (the actual per-")
    a("# sample results, orders of magnitude smaller) is kept.")
    a("inputs_log_path = os.path.join(RESULTS_DIR, 'montecarlo.inputs.txt')")
    a("if os.path.exists(inputs_log_path):")
    a("    os.remove(inputs_log_path)")
    sections.append(s)

    # ---- Results ------------------------------------------------------------
    s = case_export._Section("Results", (
        "Apogee mean and 90% interval (5th-95th percentile, matching the app's own convention), the 1 sigma/"
        "2 sigma/3 sigma landing ellipses (PNG + a KML importable into Google Earth), and a results.json with "
        "the same numbers for automated checking."
    ))
    a = s.a
    a("apogee_agl = np.array(mc.results['apogee']) - env.elevation")
    a("x_impact = np.array(mc.results['x_impact'])")
    a("y_impact = np.array(mc.results['y_impact'])")
    a("")
    a("results = {")
    a(f"    'mission_id': {mission_id!r},")
    a("    'n_simulations': int(mc.num_of_loaded_sims),")
    a("    'apogee_agl_mean_m': float(apogee_agl.mean()),")
    a("    'apogee_agl_p05_m': float(np.percentile(apogee_agl, 5)),")
    a("    'apogee_agl_p95_m': float(np.percentile(apogee_agl, 95)),")
    a("    'landing_x_mean_m': float(x_impact.mean()),")
    a("    'landing_y_mean_m': float(y_impact.mean()),")
    a("    'landing_dispersion_std_m': float(np.sqrt(x_impact.std() ** 2 + y_impact.std() ** 2)),")
    a("}")
    a("with open(os.path.join(RESULTS_DIR, 'results_montecarlo.json'), 'w', encoding='utf-8') as f:")
    a("    json.dump(results, f, indent=2)")
    a("")
    a("print()")
    a("print('=' * 60)")
    a(f"print('MONTE CARLO RESULTS - Mission {case_export._clean_comment(str(mission_id))}')")
    a("print('=' * 60)")
    a("print(f\"Samples completed:        {results['n_simulations']} / {N_SIMULATIONS}\")")
    a("print(f\"Apogee AGL (mean):        {results['apogee_agl_mean_m']:.1f} m\")")
    a("print(f\"Apogee AGL (90% CI):      [{results['apogee_agl_p05_m']:.1f}, {results['apogee_agl_p95_m']:.1f}] m\")")
    a("print(f\"Landing point (mean):     ({results['landing_x_mean_m']:.1f}, {results['landing_y_mean_m']:.1f}) m from the launch rail\")")
    a("print(f\"Landing dispersion (std): {results['landing_dispersion_std_m']:.1f} m\")")
    a("print('=' * 60)")
    a("print(f'Full plots, KML ellipses and results_montecarlo.json saved to: {RESULTS_DIR}')")
    a("")
    a("import matplotlib.pyplot as plt")
    a("plt.figure(figsize=(8, 5))")
    a("plt.hist(apogee_agl, bins=min(30, max(5, len(apogee_agl) // 3)))")
    a("plt.xlabel('Apogee AGL (m)')")
    a("plt.ylabel('Count')")
    a("plt.title('Monte Carlo apogee distribution')")
    a("plt.tight_layout()")
    a("plt.savefig(os.path.join(RESULTS_DIR, 'apogee_histogram.png'))")
    a("plt.close()")
    a("")
    a("mc.plots.ellipses(save=True)  # writes {RESULTS_DIR}/montecarlo.png (the MonteCarlo filename above, with .png appended)")
    a("mc.export_ellipses_to_kml(")
    a("    filename=os.path.join(RESULTS_DIR, 'landing_ellipses.kml'),")
    a("    origin_lat=SITE_LATITUDE_DEG, origin_lon=SITE_LONGITUDE_DEG,")
    a(")")
    sections.append(s)

    return filename_stem, sections


def generate_mc_script(mission_id, version, parsed, parsed_eng, eng_filename, power_off_drag_filename, power_on_drag_filename, dry_mass_kg, dry_cg_m, i_axial, i_transverse, radius_m, uncertainties, n_simulations, include_recovery=True, mission_id_template=None, launch_override=None, motor_dry_override_kg=None, mass_source=None, inertia_source=None, launch_date_time_str=None, seed=None):
    """Returns (filename, source_code) - Mission[ID]_MonteCarlo_RocketPy_v
    [N].py. See _build_mc_sections's docstring for every parameter's
    meaning (identical to case_export.generate_case_script's own, plus
    uncertainties/n_simulations/seed)."""
    filename_stem, sections = _build_mc_sections(
        mission_id, version, parsed, parsed_eng, eng_filename, power_off_drag_filename, power_on_drag_filename,
        dry_mass_kg, dry_cg_m, i_axial, i_transverse, radius_m, uncertainties, n_simulations,
        include_recovery=include_recovery, mission_id_template=mission_id_template, launch_override=launch_override,
        motor_dry_override_kg=motor_dry_override_kg, mass_source=mass_source, inertia_source=inertia_source,
        launch_date_time_str=launch_date_time_str, seed=seed,
    )
    lines = [f'"""{filename_stem}.py - generated by Beyond UP RocketPy. Self-contained: requires only `pip install rocketpy`."""']
    for section in sections:
        lines.append("")
        lines.append(f"# --- {section.title} ---")
        lines.extend(section.lines)
    return filename_stem + ".py", "\n".join(lines) + "\n"


def generate_mc_notebook(mission_id, version, parsed, parsed_eng, eng_filename, power_off_drag_filename, power_on_drag_filename, dry_mass_kg, dry_cg_m, i_axial, i_transverse, radius_m, uncertainties, n_simulations, include_recovery=True, mission_id_template=None, launch_override=None, motor_dry_override_kg=None, mass_source=None, inertia_source=None, launch_date_time_str=None, seed=None):
    """Returns (filename, notebook_json_text) - the exact same analysis
    as generate_mc_script's twin .py, rendered as a Jupyter notebook."""
    filename_stem, sections = _build_mc_sections(
        mission_id, version, parsed, parsed_eng, eng_filename, power_off_drag_filename, power_on_drag_filename,
        dry_mass_kg, dry_cg_m, i_axial, i_transverse, radius_m, uncertainties, n_simulations,
        include_recovery=include_recovery, mission_id_template=mission_id_template, launch_override=launch_override,
        motor_dry_override_kg=motor_dry_override_kg, mass_source=mass_source, inertia_source=inertia_source,
        launch_date_time_str=launch_date_time_str, seed=seed,
    )

    import uuid

    def _cell(cell_type, source_lines):
        return {
            "id": uuid.uuid4().hex[:16],
            "cell_type": cell_type,
            "metadata": {},
            "source": [line + "\n" for line in source_lines[:-1]] + ([source_lines[-1]] if source_lines else []),
            **({"outputs": [], "execution_count": None} if cell_type == "code" else {}),
        }

    cells = [_cell("markdown", [
        f"# {filename_stem}", "",
        f"Self-contained Monte Carlo dispersion analysis, Mission {mission_id}.",
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
    _nbformat.validate(_nbformat.from_dict(notebook))
    return filename_stem + ".ipynb", json.dumps(notebook, indent=1) + "\n"
