"""2026-10-19 review ("check every bug" audit, findings #1-4 of the
ork_reader/translate/barrowman report): translate.py's mass/CG override
resolution had four related, confirmed gaps:

  1. A narrow per-component <overridecg> (no override_subcomponents_cg)
     was silently applied as the WHOLE ROCKET's dry CG.
  2. A per-component <overridemass> was silently DROPPED whenever that
     component's own geometric mass estimate was 0 - exactly the case
     where the override is the ONLY source of mass for it.
  3. A component's override_subcomponents_mass=True replaced the ENTIRE
     rocket's dry mass with just that one number, dropping sibling
     components (most importantly the nose cone, which ork_reader never
     nests under anything else).
  4. The "which override is the blanket one" search picked the FIRST
     override in parse order with any mass value, not specifically the
     one with override_subcomponents_mass=True.

Uses PROMETEO's real, checked-in parsed rocket (reference/
prometeo_mission44) with dataclasses.replace on its own already-parsed
mass_overrides - no invented rocket, same convention as this project's
other override-focused tests.
"""
import dataclasses
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bup_rocketpy import ork_reader, translate

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORK_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "ork", "PrometeoLasc2026.ork")


def _parsed():
    return ork_reader.read_ork(ORK_PATH)


def test_narrow_cg_override_does_not_corrupt_whole_rocket_cg():
    parsed = _parsed()
    baseline = translate.estimate_dry_mass_and_cg(parsed)
    assert baseline.cg_m is not None

    # Inject a narrow, component-only CG override (override_subcomponents_cg
    # NOT set) at a position FAR from the real geometric CG - if the bug
    # were present, the whole-rocket CG would snap to this value.
    far_cg = baseline.cg_m + 5.0  # 5 m away - nothing in this ~1.5 m rocket is really there
    parsed.mass_overrides.append(ork_reader.MassOverride(component="Fuselage", override_mass=None, override_subcomponents_mass=False, override_cg_m=far_cg, override_subcomponents_cg=False))

    result = translate.estimate_dry_mass_and_cg(parsed)
    assert result.cg_m is not None
    assert abs(result.cg_m - far_cg) > 1.0, "a narrow (non-subcomponents) CG override must NOT be applied as the whole rocket's CG"
    assert abs(result.cg_m - baseline.cg_m) < 0.05, f"with no valid whole-rocket CG override, the CG should still match the geometric estimate ({baseline.cg_m}), got {result.cg_m}"


def test_blanket_cg_override_still_applies_when_flagged():
    parsed = _parsed()
    baseline = translate.estimate_dry_mass_and_cg(parsed)
    target_cg = baseline.cg_m + 0.1
    parsed.mass_overrides.append(ork_reader.MassOverride(component="Fuselage", override_mass=None, override_subcomponents_mass=False, override_cg_m=target_cg, override_subcomponents_cg=True))
    result = translate.estimate_dry_mass_and_cg(parsed)
    assert abs(result.cg_m - target_cg) < 1e-9, "a REAL blanket (override_subcomponents_cg=True) override must still apply to the whole rocket"


def test_mass_override_applies_even_with_zero_geometric_baseline():
    parsed = _parsed()
    # Find a fin set and strip its material density so its OWN geometric
    # mass estimate is exactly 0 - the exact condition that silently
    # dropped a real override before this fix.
    fin = parsed.fins[0]
    parsed.fins[0] = dataclasses.replace(fin, material_density=None)
    override_value = 0.333
    parsed.mass_overrides.append(ork_reader.MassOverride(component=fin.name, override_mass=override_value, override_subcomponents_mass=False))

    rows = translate.component_table(parsed)
    row = next(r for r in rows if r.name == fin.name)
    assert row.mass_kg is not None and abs(row.mass_kg - override_value) < 1e-9, "component_table should show the override regardless (it already did before this fix)"

    components = translate._geometric_components(parsed)
    fin_contribution = next((c for c in components if abs(c[0] - override_value) < 1e-9), None)
    assert fin_contribution is not None, f"the {override_value} kg override should appear in _geometric_components' output even though the fin's own geometric baseline is 0 - it was being silently dropped before this fix"


def test_blanket_mass_override_still_includes_the_sibling_nose_cone():
    parsed = _parsed()
    nose_mass, _, _, _ = translate._cone_shell_mass_cg(parsed.nose.length, parsed.nose.aft_radius or 0.0, parsed.nose.material_density, parsed.nose.position_m)
    assert nose_mass > 0, "PROMETEO's real nose cone should have a resolvable geometric mass for this test to mean anything"

    blanket_value = 3.0  # an arbitrary "scale-measured" blanket total on the Fuselage, NOT including the nose cone (a sibling, not nested under it)
    parsed.mass_overrides.append(ork_reader.MassOverride(component="Fuselage", override_mass=blanket_value, override_subcomponents_mass=True))

    result = translate.estimate_dry_mass_and_cg(parsed)
    assert result.mass_kg > blanket_value, "the whole-rocket mass must be MORE than the blanket override alone - the sibling nose cone's own mass must still be added"
    assert abs(result.mass_kg - (blanket_value + nose_mass)) < 1e-6, f"expected blanket ({blanket_value}) + nose cone ({nose_mass}), got {result.mass_kg}"
    assert "nose cone" in result.source.lower()


def test_total_override_selection_prefers_the_blanket_one_not_parse_order():
    """A narrow, non-blanket override appears FIRST in parse order (on
    the nose cone), followed by a genuine blanket override elsewhere
    (on the Fuselage) - the blanket one must still be found and used,
    not skipped because a narrower one happened to come first."""
    parsed = _parsed()
    parsed.mass_overrides.insert(0, ork_reader.MassOverride(component=parsed.nose.name, override_mass=0.05, override_subcomponents_mass=False))
    blanket_value = 4.2
    parsed.mass_overrides.append(ork_reader.MassOverride(component="Fuselage", override_mass=blanket_value, override_subcomponents_mass=True))

    result = translate.estimate_dry_mass_and_cg(parsed)
    assert result.mass_kg > blanket_value, "should still be blanket + nose cone, not the geometric estimate (which would mean the blanket override was skipped)"
    assert "Fuselage" in result.source
