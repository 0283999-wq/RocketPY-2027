""""Compare Designs" (2026-10-09 review item 13, top priority alongside
item 12 - "this is what I actually need right now"): load two full
vehicle designs (two .ork files, e.g. two fin options for the same
airframe/motor) and compare them side by side - nominal numbers plus an
optional Monte Carlo run with COMMON RANDOM NUMBERS (the same seed for
both designs, same technique analysis.drag_comparison() already uses for
A/B drag-curve comparisons - CLAUDE.md Sec 6 point 2) so the reported
apogee difference isolates the DESIGN change from sampling noise.

Replaces the Analysis page's old "drag comparison" card's confusion
(item 9) for the "which design should I fly" question specifically -
drag_comparison() still exists for its own narrower "same rocket, two Cd
curves" question.
"""
import math
import os
from dataclasses import dataclass, field

import numpy as np

from bup_rocketpy import flutter, translate
from bup_rocketpy.gui import pipeline


@dataclass
class DesignSummary:
    """One design's (A or B) own numbers - the side-by-side table is just
    these two placed next to each other."""
    label: str  # "A" or "B"
    display_name: str
    ork_filename: str
    ork_hash: str
    fin_summary: str
    cd_curve_stale: bool
    apogee_agl_m: float
    max_speed_ms: float
    max_mach: float
    rail_exit_velocity_ms: float
    static_margin_t0_cal: float
    min_static_margin_cal: float
    max_static_margin_cal: float
    stability_mach03_cal: float
    fin_mass_kg: float
    flutter_velocity_ms: float
    flutter_source: str
    flutter_margin: float  # flutter_velocity / max_speed - must be >= 1.5 per STR 6.3.2
    openrocket_csv_path: str = None
    cd_mach_plot_path: str = None
    power_off_drag_path: str = None
    power_on_drag_path: str = None
    apogee_mc_mean_m: float = None
    apogee_mc_ci90: tuple = None
    mc_n_completed: int = None


@dataclass
class DesignComparisonResult:
    design_a: DesignSummary
    design_b: DesignSummary
    apogee_diff_b_minus_a_m: float = None  # nominal (single-run) difference, always available
    apogee_mc_diff_mean_m: float = None  # paired Monte Carlo difference, only if mc_n > 0
    apogee_mc_diff_ci90: tuple = None
    mc_n_paired: int = None
    verdict: str = ""


def _fin_mass_kg(parsed):
    rows = translate.component_table(parsed)
    return sum(r.mass_kg or 0.0 for r in rows if r.kind.startswith("Fin set"))


def _summarize_one_design(label, ork_path, eng_path, power_off_drag_path, power_on_drag_path, outputs_dir, ork_filename, eng_filename, simulation_name, mass_override_kg, cg_override_m):
    lr = pipeline.load_files(
        ork_path, eng_path, power_off_drag_path=power_off_drag_path, power_on_drag_path=power_on_drag_path,
        outputs_dir=outputs_dir, simulation_name=simulation_name, ork_filename=ork_filename, eng_filename=eng_filename,
    )
    sim = pipeline.run_simulation(lr, outputs_dir, dry_mass_override_kg=mass_override_kg, dry_cg_override_m=cg_override_m)

    flight = sim.flight
    rocket = flight.rocket
    radius = rocket.radius
    cg0 = -rocket.center_of_mass(0)
    cp0 = -rocket.cp_position(0)
    cp03 = -rocket.cp_position(0.3)
    static_margin_t0_cal = (cp0 - cg0) / (2 * radius)
    stability_m03_cal = (cp03 - cg0) / (2 * radius)

    env = flight.env
    flutter_result = flutter.worst_case_flutter(lr.parsed_ork, env.speed_of_sound(env.elevation), env.pressure(env.elevation))

    summary = DesignSummary(
        label=label, display_name=lr.display_name, ork_filename=lr.ork_filename, ork_hash=lr.ork_hash,
        fin_summary=lr.fin_summary, cd_curve_stale=lr.cd_curve_stale,
        apogee_agl_m=sim.apogee_agl_m, max_speed_ms=sim.max_speed_ms, max_mach=sim.max_mach,
        rail_exit_velocity_ms=sim.rail_exit_velocity_ms,
        static_margin_t0_cal=static_margin_t0_cal,
        min_static_margin_cal=sim.min_static_margin_cal, max_static_margin_cal=sim.max_static_margin_cal,
        stability_mach03_cal=stability_m03_cal,
        fin_mass_kg=_fin_mass_kg(lr.parsed_ork),
        flutter_velocity_ms=flutter_result.flutter_velocity_ms if flutter_result else None,
        flutter_source=flutter_result.source if flutter_result else "not computed (no fins parsed)",
        flutter_margin=(flutter_result.flutter_velocity_ms / sim.max_speed_ms) if flutter_result and sim.max_speed_ms else None,
        openrocket_csv_path=sim.openrocket_csv_path,
        cd_mach_plot_path=sim.plot_paths.get("cd_mach"),
        power_off_drag_path=lr.power_off_drag_path, power_on_drag_path=lr.power_on_drag_path,
    )
    return lr, sim, summary


def compare_designs(
    ork_path_a, eng_path_a, ork_path_b, eng_path_b,
    power_off_drag_a=None, power_on_drag_a=None, power_off_drag_b=None, power_on_drag_b=None,
    outputs_dir=None, ork_filename_a=None, eng_filename_a=None, ork_filename_b=None, eng_filename_b=None,
    simulation_name_a=None, simulation_name_b=None,
    mass_override_kg_a=None, cg_override_m_a=None, mass_override_kg_b=None, cg_override_m_b=None,
    mc_n=0, mc_uncertainties=None, mc_seed=12345,
):
    """Runs BOTH designs through the exact same load_files()+run_simulation()
    pipeline a single Simulate run uses (never a separate "lite" re-
    implementation), then optionally a common-random-numbers Monte Carlo
    pair (mc_n > 0) for a statistically defensible apogee difference.
    eng_path_b/eng_filename_b default to design A's own motor when not
    given - the common real case is comparing two fin options on the
    SAME airframe/motor, not two different vehicles entirely."""
    eng_path_b = eng_path_b or eng_path_a
    eng_filename_b = eng_filename_b or eng_filename_a

    out_a = os.path.join(outputs_dir, "compare_designs_a") if outputs_dir else None
    out_b = os.path.join(outputs_dir, "compare_designs_b") if outputs_dir else None

    lr_a, sim_a, summary_a = _summarize_one_design("A", ork_path_a, eng_path_a, power_off_drag_a, power_on_drag_a, out_a, ork_filename_a, eng_filename_a, simulation_name_a, mass_override_kg_a, cg_override_m_a)
    lr_b, sim_b, summary_b = _summarize_one_design("B", ork_path_b, eng_path_b, power_off_drag_b, power_on_drag_b, out_b, ork_filename_b, eng_filename_b, simulation_name_b, mass_override_kg_b, cg_override_m_b)

    apogee_diff = summary_b.apogee_agl_m - summary_a.apogee_agl_m
    result = DesignComparisonResult(design_a=summary_a, design_b=summary_b, apogee_diff_b_minus_a_m=apogee_diff)

    if mc_n and mc_n > 0:
        from bup_rocketpy import monte_carlo
        mc_a = monte_carlo.run_monte_carlo(
            lr_a.parsed_ork, lr_a.parsed_eng, lr_a.eng_path, lr_a.power_off_drag_path, lr_a.power_on_drag_path,
            sim_a.dry_mass_kg, sim_a.dry_cg_m, sim_a.i_axial_kgm2, sim_a.i_transverse_kgm2, lr_a.parsed_ork.body_tubes[0].radius if lr_a.parsed_ork.body_tubes else 0.05,
            mc_uncertainties or [], mc_n, (out_a + "_mc") if out_a else None, seed=mc_seed,
        )
        mc_b = monte_carlo.run_monte_carlo(
            lr_b.parsed_ork, lr_b.parsed_eng, lr_b.eng_path, lr_b.power_off_drag_path, lr_b.power_on_drag_path,
            sim_b.dry_mass_kg, sim_b.dry_cg_m, sim_b.i_axial_kgm2, sim_b.i_transverse_kgm2, lr_b.parsed_ork.body_tubes[0].radius if lr_b.parsed_ork.body_tubes else 0.05,
            mc_uncertainties or [], mc_n, (out_b + "_mc") if out_b else None, seed=mc_seed,
        )
        summary_a.apogee_mc_mean_m = mc_a.apogee_mean
        summary_a.apogee_mc_ci90 = (mc_a.apogee_p05, mc_a.apogee_p95)
        summary_a.mc_n_completed = mc_a.n_completed
        summary_b.apogee_mc_mean_m = mc_b.apogee_mean
        summary_b.apogee_mc_ci90 = (mc_b.apogee_p05, mc_b.apogee_p95)
        summary_b.mc_n_completed = mc_b.n_completed

        n = min(mc_a.n_completed, mc_b.n_completed)
        a_samples = np.array(mc_a.apogee_samples[:n])
        b_samples = np.array(mc_b.apogee_samples[:n])
        diffs = b_samples - a_samples
        if n > 1:
            mean_diff = float(diffs.mean())
            se = diffs.std(ddof=1) / math.sqrt(n)
            ci = (mean_diff - 1.645 * se, mean_diff + 1.645 * se)  # 90% CI, normal approx - same math as analysis.drag_comparison()
        elif n == 1:
            mean_diff, ci = float(diffs[0]), (float("nan"), float("nan"))
        else:
            mean_diff, ci = float("nan"), (float("nan"), float("nan"))
        result.apogee_mc_diff_mean_m = mean_diff
        result.apogee_mc_diff_ci90 = ci
        result.mc_n_paired = n

        if n > 1 and not (math.isnan(ci[0]) or math.isnan(ci[1])) and (ci[0] > 0 or ci[1] < 0):
            direction = "B" if mean_diff > 0 else "A"
            result.verdict = f"{direction} is {abs(mean_diff):.0f} m [{ci[0]:+.0f}, {ci[1]:+.0f}] {'higher' if direction == 'B' else 'lower (A higher)'} - the difference is real (90% CI excludes zero)."
        else:
            result.verdict = f"Apogee difference ({mean_diff:+.0f} m [{ci[0]:+.0f}, {ci[1]:+.0f}] at 90%) is not distinguishable from sampling noise with {n} paired samples - not a confirmed difference."
    else:
        result.verdict = f"Nominal-only comparison (no Monte Carlo run): B - A = {apogee_diff:+.1f} m. Run with Monte Carlo samples for a statistically defensible verdict."

    return result


def export_comparison_zip(result, zip_path):
    """One OpenRocket-format CSV per design, per this review's explicit
    requirement ("export: one OpenRocket-format CSV per design per case,
    in a zip")."""
    import zipfile
    os.makedirs(os.path.dirname(zip_path) or ".", exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for summary in (result.design_a, result.design_b):
            if summary.openrocket_csv_path and os.path.exists(summary.openrocket_csv_path):
                zf.write(summary.openrocket_csv_path, arcname=f"{summary.label}_{summary.display_name}_flight_data_openrocket_style.csv")
    return zip_path
