"""The "Calculations" page (2026-10-19 review): "a new page dedicated to
the calculations... for me to check them at hand." Every number here is
computed by the SAME functions the rest of the app actually uses to fly
the currently loaded rocket (translate.py, barrowman.py, flutter.py,
recovery.py, ork_reader.py) - this page never recomputes anything with
its own separate formula, it just shows the formula AND the real numbers
that function used, side by side, so a reader can redo the arithmetic
on paper and get the same answer the app reports everywhere else.

All positions shown are "m from nose tip" (ork_reader.py's own
convention), matching every other page in this app - not rocketpy's own
internal sign convention.
"""
import math
import os

from nicegui import ui

from bup_rocketpy.gui import components, layout, state
from bup_rocketpy import barrowman, flutter, recovery, translate

s = state.state
OUTPUTS_DIR = os.path.join(os.getcwd(), "outputs", "gui_run")


def _fmt(v, decimals=4, unit=""):
    if v is None:
        return "n/a"
    try:
        if isinstance(v, bool):
            return str(v)
        return f"{v:.{decimals}f}{(' ' + unit) if unit else ''}"
    except (TypeError, ValueError):
        return str(v)


def _formula_row(label, value):
    with ui.row().classes("items-baseline gap-2"):
        ui.label(label).classes("text-sm font-mono").style("color: var(--bup-muted)")
        ui.label(value).classes("text-sm font-mono font-bold")


@ui.page("/calculations")
def calculations_page():
    with layout.layout("Calculations", current_path="/calculations"):
        components.page_header("Calculations", "Every formula this app actually uses, with the current rocket's real numbers plugged in - redo any of these by hand and you should get the same answer shown elsewhere in the app.")
        if s["load_result"] is None or s["sim_result"] is None:
            components.empty_state("calculate", "Load files and click Simulate on the Simulate page first - this page shows the calculations for whatever rocket is currently loaded.", action_label="Go to Simulate", on_action=lambda: ui.navigate.to("/simulate"))
            return

        parsed = s["load_result"].parsed_ork
        sim = s["sim_result"]
        flight = sim.flight
        rocket = flight.rocket
        env = flight.env
        radius = rocket.radius

        # --- Mass and center of gravity ---
        with components.card(classes="w-full"):
            ui.label("1. Dry mass and center of gravity").classes("font-bold")
            ui.label("CG = (sum of each component's mass x its own position from the nose) / (total mass). Source: translate.py's component_table() / estimate_dry_mass_and_cg().").classes("text-xs").style("color: var(--bup-muted)")
            rows = translate.component_table(parsed)
            countable = [r for r in rows if r.mass_kg is not None and r.position_m is not None]
            with ui.grid(columns=4).classes("gap-2 w-full mt-2"):
                for header in ["Component", "Position from nose (m)", "Mass (kg)", "mass x position (kg*m)"]:
                    ui.label(header).classes("font-bold text-xs")
                for row in countable:
                    moment = row.mass_kg * row.position_m
                    ui.label(row.name).classes("text-sm")
                    ui.label(f"{row.position_m:.4f}").classes("text-sm font-mono")
                    ui.label(f"{row.mass_kg:.4f}").classes("text-sm font-mono")
                    ui.label(f"{moment:.5f}").classes("text-sm font-mono")
            total_mass = sum(r.mass_kg for r in countable)
            total_moment = sum(r.mass_kg * r.position_m for r in countable)
            ui.label(f"Components with unknown mass (IGNORED/COVERED, excluded from this table): {len(rows) - len(countable)}").classes("text-xs mt-1").style("color: var(--bup-muted)")
            _formula_row("Sum of mass", f"{total_mass:.4f} kg")
            _formula_row("Sum of (mass x position)", f"{total_moment:.5f} kg*m")
            _formula_row("CG = sum(mass x position) / sum(mass)", f"{total_moment:.5f} / {total_mass:.4f} = {(total_moment / total_mass if total_mass else float('nan')):.4f} m from nose")
            ui.label(f"Dry mass/CG actually used to build this flight: {s['dry_mass_kg']:.4f} kg @ {s['dry_cg_m']:.4f} m (source: {s['mass_source']}).").classes("text-sm mt-2 font-bold")
            if s["dry_mass_override"] is not None or s["dry_cg_override"] is not None:
                ui.label("A manual override is active - the table above is the GEOMETRIC estimate for reference; the number actually flown may be the typed override instead (see the mass source line above).").classes("text-xs mt-1").style("color: var(--bup-warning)")

        # --- Center of pressure (Barrowman) ---
        with components.card(classes="w-full mt-4"):
            ui.label("2. Center of pressure - Barrowman (1966) hand calculation").classes("font-bold")
            ui.label("Independent cross-check against RocketPy's own (more complete) CP, computed from nose + fin normal-force slopes only - the classical textbook method. Source: barrowman.py's hand_calc_cp(). Neglects body tube/transition lift (standard simplification).").classes("text-xs").style("color: var(--bup-muted)")
            cp_calc = barrowman.hand_calc_cp(parsed)
            if cp_calc is None:
                ui.label("Could not compute - this rocket has no nose cone or no fins parsed.").classes("text-sm mt-2").style("color: var(--bup-error)")
            else:
                _formula_row("Nose: Cn_alpha (fixed, slender-body theory)", "2.0")
                _formula_row("Nose: CP position = k x nose length", f"{cp_calc['nose_cp_m']:.4f} m from nose")
                for fd in cp_calc["fin_details"]:
                    ui.label(f"Fin set \"{fd['name']}\":").classes("text-sm font-bold mt-1")
                    _formula_row("  Cn_alpha (Barrowman trapezoid formula, body radius " + f"{fd['body_radius_m']:.4f} m)", f"{fd['cn_alpha']:.4f} /rad")
                    _formula_row("  CP position (root-chord centroid + sweep)", f"{fd['cp_m']:.4f} m from nose")
                _formula_row("Total Cn_alpha = nose + sum(fins)", f"2.0 + {cp_calc['fins_cn_alpha']:.4f} = {cp_calc['cn_alpha_total']:.4f}")
                _formula_row("CP = (nose: Cn_alpha x CP + fins: Cn_alpha x CP) / total Cn_alpha", f"{cp_calc['cp_m']:.4f} m from nose")
                ui.label(f"RocketPy's own CP at Mach 0.3 (what the app actually flies): {-rocket.cp_position(0.3):.4f} m from nose. A gap of a few % from the hand-calc above is expected (body/transition lift is real but neglected here) - a much bigger gap is worth investigating.").classes("text-sm mt-2 font-bold")

        # --- Static margin ---
        with components.card(classes="w-full mt-4"):
            ui.label("3. Static margin").classes("font-bold")
            ui.label("Static margin (calibers) = (CP - CG) / (2 x body radius). A POSITIVE margin means CP is behind CG (aft of CG, towards the tail) - the rocket is aerodynamically stable. FLT 4.3.5/4.3.6 requires 1.5-4 cal throughout the ascent.").classes("text-xs").style("color: var(--bup-muted)")
            cg0 = -rocket.center_of_mass(0)
            cp03 = -rocket.cp_position(0.3)
            cp0 = -rocket.cp_position(0)
            margin_mach03 = (cp03 - cg0) / (2 * radius)
            margin_mach0 = (cp0 - cg0) / (2 * radius)
            _formula_row("CG at liftoff (t=0)", f"{cg0:.4f} m from nose")
            _formula_row("CP at Mach 0.3 (OpenRocket's own convention)", f"{cp03:.4f} m from nose")
            _formula_row("Margin @ Mach 0.3 = (CP - CG) / (2 x radius)", f"({cp03:.4f} - {cg0:.4f}) / (2 x {radius:.4f}) = {margin_mach03:.3f} cal")
            _formula_row("CP at Mach 0 (near-liftoff speed)", f"{cp0:.4f} m from nose")
            _formula_row("Margin @ Mach 0 = (CP - CG) / (2 x radius)", f"({cp0:.4f} - {cg0:.4f}) / (2 x {radius:.4f}) = {margin_mach0:.3f} cal")
            ui.label(f"Worst case across the WHOLE ascent (what FLT 4.3.5/4.3.6 is actually judged on): min {sim.min_static_margin_cal:.3f} cal, max {sim.max_static_margin_cal:.3f} cal (Mach-varying); Mach-0 variant: min {sim.min_static_margin_mach0_cal:.3f} cal, max {sim.max_static_margin_mach0_cal:.3f} cal.").classes("text-sm mt-2 font-bold")

        # --- Rail exit velocity ---
        with components.card(classes="w-full mt-4"):
            ui.label("4. Rail exit velocity").classes("font-bold")
            ui.label("RocketPy and OpenRocket use DIFFERENT definitions of 'off the rail' - see the Rocket page's OpenRocket comparison card for both numbers side by side. This section explains RocketPy's own convention, which is the one the app judges FLT 4.3.4 (>= 30 m/s) on.").classes("text-xs").style("color: var(--bup-muted)")
            from bup_rocketpy.ork_reader import airframe_length_m
            rail_length = parsed.launch.rail_length_m if parsed.launch else None
            upper_button = parsed.rail_buttons.upper_position_m if parsed.rail_buttons else None
            nozzle_pos = airframe_length_m(parsed)
            if rail_length is not None and upper_button is not None:
                effective_rail = rail_length - abs(nozzle_pos - upper_button)
                _formula_row("Rail length (from the .ork's own launch conditions)", f"{rail_length:.4f} m")
                _formula_row("Nozzle position (tail end of the airframe, from nose)", f"{nozzle_pos:.4f} m")
                _formula_row("Upper rail button position (from nose)", f"{upper_button:.4f} m")
                _formula_row("Effective rail travel = rail length - |nozzle - upper button|", f"{rail_length:.4f} - |{nozzle_pos:.4f} - {upper_button:.4f}| = {effective_rail:.4f} m")
                ui.label("RocketPy triggers rail exit the instant the UPPER RAIL BUTTON has traveled this effective distance - not when the full rocket has traveled the full rail length (OpenRocket's own convention). Both are valid, different conventions, not a bug - see RocketPy's flight.py source for the exact mechanism.").classes("text-xs mt-1").style("color: var(--bup-muted)")
            else:
                ui.label("Rail length or rail button position not available for this rocket - cannot show the formula's inputs.").classes("text-sm").style("color: var(--bup-warning)")
            ui.label(f"Rail exit velocity actually reached in this flight: {sim.rail_exit_velocity_ms:.3f} m/s (FLT 4.3.4 requires >= 30 m/s).").classes("text-sm mt-2 font-bold")

        # --- Fin flutter ---
        with components.card(classes="w-full mt-4"):
            ui.label("5. Fin flutter velocity - NACA TN 4197").classes("font-bold")
            ui.label("V_flutter = a x sqrt(G / (1.337 x AR^3 x P x (taper+1) / (2 x (AR+2) x (t/c)^3))), where AR = aspect ratio, taper = tip_chord/root_chord, t/c = thickness/root_chord, a = speed of sound, P = static pressure, G = shear modulus. Source: flutter.py's hand_calc_flutter_velocity(). STR 6.3.2 requires flutter velocity >= 1.5x the vehicle's own max speed.").classes("text-xs").style("color: var(--bup-muted)")
            speed_of_sound = env.speed_of_sound(env.elevation)
            pressure = env.pressure(env.elevation)
            shear_g = s.get("flutter_shear_modulus_pa")
            shear_source = s.get("flutter_shear_modulus_source")
            manual_override = s.get("flutter_manual_override_ms")
            manual_source = s.get("flutter_manual_override_source")
            if not parsed.fins:
                ui.label("No fins parsed for this rocket - flutter cannot be computed.").classes("text-sm").style("color: var(--bup-warning)")
            else:
                for finset in parsed.fins:
                    result = flutter.hand_calc_flutter_velocity(finset, speed_of_sound, pressure, shear_g, shear_source, is_freeform=(finset.shape != "trapezoid"))
                    ui.label(f"Fin set \"{finset.name}\" ({finset.shape}):").classes("text-sm font-bold mt-1")
                    if result is None:
                        ui.label("  Could not compute (zero chord/span/thickness).").classes("text-sm").style("color: var(--bup-muted)")
                        continue
                    _formula_row("  Aspect ratio AR = 2 x span / (root + tip chord)", f"{result.aspect_ratio:.4f}")
                    _formula_row("  Taper ratio = tip chord / root chord", f"{result.taper_ratio:.4f}")
                    _formula_row("  Thickness ratio t/c = thickness / root chord", f"{result.thickness_ratio:.4f}")
                    _formula_row("  Speed of sound a (at launch altitude)", f"{speed_of_sound:.2f} m/s")
                    _formula_row("  Static pressure P (at launch altitude)", f"{pressure:.1f} Pa")
                    _formula_row("  Shear modulus G", f"{result.shear_modulus_pa:.3e} Pa ({result.shear_modulus_source})")
                    _formula_row("  V_flutter", f"{result.flutter_velocity_ms:.2f} m/s ({result.source})")
            worst = flutter.worst_case_flutter(parsed, speed_of_sound, pressure, shear_g, shear_source, manual_override, manual_source)
            if worst is not None:
                margin = worst.flutter_velocity_ms / sim.max_speed_ms if sim.max_speed_ms else None
                ui.label(f"Worst case across all fin sets (what STR 6.3.2 is judged on): {worst.flutter_velocity_ms:.2f} m/s. Max speed reached this flight: {sim.max_speed_ms:.2f} m/s. Margin = {margin:.2f}x (needs >= 1.5x).").classes("text-sm mt-2 font-bold")

        # --- Parachute and shock-cord mass ---
        with components.card(classes="w-full mt-4"):
            ui.label("6. Parachute and shock-cord mass (when not manually overridden)").classes("font-bold")
            ui.label("OpenRocket's own formulas: parachute mass = canopy area (pi x (diameter/2)^2) x canopy material surface density, plus shroud lines (count x length x line density). Shock-cord mass = cord length x line material density. Source: ork_reader.py's parachute/shockcord parsing.").classes("text-xs").style("color: var(--bup-muted)")
            any_shown = False
            for chute in parsed.parachutes:
                if chute.computed_mass_kg is None:
                    continue
                any_shown = True
                canopy_area = math.pi * (chute.diameter / 2.0) ** 2
                ui.label(f"Parachute \"{chute.name}\":").classes("text-sm font-bold mt-1")
                _formula_row("  Canopy area = pi x (diameter/2)^2", f"pi x ({chute.diameter:.4f}/2)^2 = {canopy_area:.5f} m^2")
                _formula_row("  Computed mass (canopy + lines)", f"{chute.computed_mass_kg:.4f} kg")
            if not any_shown:
                ui.label("No parachute on this rocket has a geometry-computed mass (either all have a manual <overridemass>, or none have enough material/canopy data to estimate from).").classes("text-sm").style("color: var(--bup-muted)")

        # --- Descent rate (recovery) ---
        with components.card(classes="w-full mt-4"):
            ui.label("7. Parachute descent rate - hand terminal velocity").classes("font-bold")
            ui.label("v_terminal = sqrt(2 x m x g / (rho x Cd x S)), where m = descent mass, rho = air density at that altitude, Cd x S = parachute drag area. Source: recovery.py's _hand_terminal_velocity(). An independent cross-check against the simulated descent rate - if they disagree by a lot, something (mass, Cd x S, or the simulation) is worth a second look.").classes("text-xs").style("color: var(--bup-muted)")
            panel_rows = recovery.recovery_panel(flight, env, sim.descent_mass_kg) if sim.descent_mass_kg else []
            if not panel_rows:
                ui.label("No parachute deployment recorded in this flight (e.g. the Ballistic case, or no recovery system).").classes("text-sm").style("color: var(--bup-muted)")
            for row in panel_rows:
                ui.label(f"\"{row.name}\" (deployed at {row.deploy_altitude_agl_m:.0f} m AGL):").classes("text-sm font-bold mt-1")
                _formula_row("  Cd x S (drag area)", f"{row.cd_s_m2:.4f} m^2")
                _formula_row("  Hand terminal velocity at deploy altitude", f"{row.hand_terminal_velocity_at_deploy_alt_ms:.2f} m/s")
                _formula_row("  Hand terminal velocity at ground level", f"{row.hand_terminal_velocity_at_ground_ms:.2f} m/s")
                _formula_row("  Simulated descent rate under this canopy", f"{row.descent_rate_sim_ms:.2f} m/s")
                _formula_row("  Difference (sim - hand) / hand, at deploy altitude", f"{row.diff_pct_at_deploy_alt:+.1f}%")
                if row.note:
                    ui.label(f"  Note: {row.note}").classes("text-xs").style("color: var(--bup-warning)")
