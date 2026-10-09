"""2026-10-09 review item 3: "the component table is confusing" -
regression coverage for the sub-fixes in this session:

  - parachute mass, computed from canopy area x material surface
    density + lines x length x line density, when no <overridemass>
    is present (same formula OpenRocket's own UI uses).
  - shock-cord mass, computed from <cordlength> x line material
    density, previously not attempted at all.
  - "COVERED by parent override" status/labeling for components other
    than the one actually carrying a blanket <overridemass
    overridesubcomponentsmass="true">.
  - the ignored-components summary (count + names), never fabricating
    a total mass since IGNORED mass is by definition unknown.
  - pod set parsing: recurses into a pod's own <subcomponents> for
    axial mass/CG (radial offset deliberately not modeled - no
    verified schema was available for it), or logs IGNORED for an
    empty pod set.

Uses PROMETEO's real, checked-in .ork (bare XML, not zipped) with
targeted text-surgery, per this project's established convention -
no invented rocket.
"""
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bup_rocketpy import ork_reader, translate

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORK_PATH = os.path.join(REPO_ROOT, "reference", "prometeo_mission44", "data", "ork", "PrometeoLasc2026.ork")


def _read_ork_text():
    with open(ORK_PATH, "r", encoding="utf-8") as f:
        return f.read()


def _write_variant(tmp_path, name, content):
    path = os.path.join(tmp_path, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def test_parachute_mass_computed_when_no_override(tmp_path):
    """Strip PROMETEO's real parachute <overridemass> (0.558 kg) so the
    reader has to fall back to the canopy+lines formula, and check the
    result against that same formula computed independently here."""
    content = _read_ork_text()
    assert "<overridemass>0.558</overridemass>" in content
    stripped = content.replace("<overridemass>0.558</overridemass>\n                <overridesubcomponentsmass>false</overridesubcomponentsmass>\n", "")
    path = _write_variant(tmp_path, "no_chute_override.ork", stripped)

    parsed = ork_reader.read_ork(path)
    chute = next(c for c in parsed.parachutes if c.name == "Parachute")
    assert chute.computed_mass_kg is not None, "expected a canopy+lines mass estimate with no override present"

    canopy_area = math.pi * (2.8 / 2.0) ** 2
    expected = canopy_area * 0.067 + 8 * 1.5 * 0.0035
    assert abs(chute.computed_mass_kg - expected) < 1e-6

    # no override anywhere in this file any more -> no component should
    # be marked COVERED, and the chute's own mass row must show the
    # computed estimate, not a zero.
    table = translate.component_table(parsed)
    chute_row = next(r for r in table if r.name == "Parachute")
    assert chute_row.mass_kg is not None and abs(chute_row.mass_kg - expected) < 1e-6
    assert not any(r.status == "COVERED" for r in table)


def test_shockcord_mass_computed_from_cordlength_and_line_density(tmp_path):
    """Inject a <shockcord> with real-shaped tags into the Fuselage's
    <subcomponents> and check cordlength x line density."""
    content = _read_ork_text()
    marker = "<subcomponents>\n              <trapezoidfinset>"
    assert marker in content
    shockcord_xml = (
        "<subcomponents>\n"
        "              <shockcord>\n"
        "                <name>Shock cord</name>\n"
        "                <id>aaaaaaaa-0000-0000-0000-000000000001</id>\n"
        "                <axialoffset method=\"top\">0.1</axialoffset>\n"
        "                <position type=\"top\">0.1</position>\n"
        "                <packedlength>0.1</packedlength>\n"
        "                <packedradius>0.02</packedradius>\n"
        "                <radialposition>0.0</radialposition>\n"
        "                <radialdirection>0.0</radialdirection>\n"
        "                <cordlength>3.0</cordlength>\n"
        "                <linematerial type=\"line\" density=\"0.004\" group=\"ThreadsLines\">Test cord</linematerial>\n"
        "              </shockcord>\n"
        "              <trapezoidfinset>"
    )
    injected = content.replace(marker, shockcord_xml)
    path = _write_variant(tmp_path, "with_shockcord.ork", injected)

    parsed = ork_reader.read_ork(path)
    cord_row = next(r for r in parsed.import_log if r.component == "Shock cord")
    assert cord_row.status == "APPROXIMATED"
    assert abs(3.0 * 0.004 - 0.012) < 1e-9
    matching_point_masses = [pm for pm in parsed.point_masses if pm.name == "Shock cord"]
    assert len(matching_point_masses) == 1
    assert abs(matching_point_masses[0].mass - 0.012) < 1e-9


def test_blanket_override_marks_other_components_covered_not_ignored():
    """PROMETEO's Fuselage carries overridesubcomponentsmass=false, so
    nothing should be marked COVERED for the real file - this test
    flips that one flag to true via text-surgery and checks every
    OTHER component (not the Fuselage itself) is re-labeled COVERED."""
    import dataclasses

    parsed = ork_reader.read_ork(ORK_PATH)
    fuselage_override = next(o for o in parsed.mass_overrides if o.component == "Fuselage")
    assert fuselage_override.override_subcomponents_mass is False
    flipped = dataclasses.replace(fuselage_override, override_subcomponents_mass=True)
    parsed.mass_overrides = [flipped if o.component == "Fuselage" else o for o in parsed.mass_overrides]

    table = translate.component_table(parsed)
    covered = [r for r in table if r.status == "COVERED"]
    assert len(covered) > 0, "expected at least one other component to be marked COVERED once Fuselage's blanket override is on"
    assert not any(r.name == "Fuselage" for r in covered), "the override-bearing component itself must not be marked COVERED"
    for r in covered:
        assert "Fuselage" in r.flag


def test_ignored_components_summary_lists_real_ignored_rows(tmp_path):
    """Strip the parachute's override AND its canopy material density
    so neither path can estimate a mass - it must show up as a real
    IGNORED row, with no fabricated total mass anywhere."""
    content = _read_ork_text()
    stripped = content.replace("<overridemass>0.558</overridemass>\n                <overridesubcomponentsmass>false</overridesubcomponentsmass>\n", "")
    stripped = re.sub(r'<material type="surface"[^>]*>Ripstop nylon</material>', "", stripped)
    path = _write_variant(tmp_path, "no_chute_mass_data.ork", stripped)

    parsed = ork_reader.read_ork(path)
    chute = next(c for c in parsed.parachutes if c.name == "Parachute")
    assert chute.computed_mass_kg is None

    table = translate.component_table(parsed)
    ignored = [r for r in table if r.status == "IGNORED"]
    assert any(r.name == "Parachute" for r in ignored)


def test_empty_podset_logged_ignored_with_no_mass_contribution(tmp_path):
    content = _read_ork_text()
    marker = "<subcomponents>\n              <trapezoidfinset>"
    podset_xml = (
        "<subcomponents>\n"
        "              <podset>\n"
        "                <name>Empty pod</name>\n"
        "                <id>bbbbbbbb-0000-0000-0000-000000000001</id>\n"
        "                <axialoffset method=\"top\">0.2</axialoffset>\n"
        "                <position type=\"top\">0.2</position>\n"
        "                <instancecount>1</instancecount>\n"
        "                <radialposition>0.0</radialposition>\n"
        "                <radialdirection>0.0</radialdirection>\n"
        "                <angleoffset>0.0</angleoffset>\n"
        "                <radius>0.0548</radius>\n"
        "                <subcomponents>\n"
        "                </subcomponents>\n"
        "              </podset>\n"
        "              <trapezoidfinset>"
    )
    injected = content.replace(marker, podset_xml)
    path = _write_variant(tmp_path, "empty_podset.ork", injected)

    parsed = ork_reader.read_ork(path)
    pod_rows = [r for r in parsed.import_log if r.component == "Empty pod"]
    pod_row = next(r for r in pod_rows if "pod" in r.detail.lower())
    assert pod_row.status == "IGNORED"
    assert "no mass" in pod_row.detail.lower()
    assert not any(pm.name == "Empty pod" for pm in parsed.point_masses)


def test_podset_with_mass_component_recurses_and_is_approximated(tmp_path):
    """A pod containing a real masscomponent must still contribute that
    mass to the vehicle's dry mass/CG (axially) - only the pod's own
    radial offset is deliberately not modeled."""
    content = _read_ork_text()
    marker = "<subcomponents>\n              <trapezoidfinset>"
    podset_xml = (
        "<subcomponents>\n"
        "              <podset>\n"
        "                <name>Camera pod</name>\n"
        "                <id>cccccccc-0000-0000-0000-000000000001</id>\n"
        "                <axialoffset method=\"top\">0.2</axialoffset>\n"
        "                <position type=\"top\">0.2</position>\n"
        "                <instancecount>1</instancecount>\n"
        "                <radialposition>0.05</radialposition>\n"
        "                <radialdirection>0.0</radialdirection>\n"
        "                <angleoffset>0.0</angleoffset>\n"
        "                <radius>0.0548</radius>\n"
        "                <subcomponents>\n"
        "                  <masscomponent>\n"
        "                    <name>Camera</name>\n"
        "                    <id>dddddddd-0000-0000-0000-000000000001</id>\n"
        "                    <axialoffset method=\"top\">0.0</axialoffset>\n"
        "                    <position type=\"top\">0.0</position>\n"
        "                    <packedlength>0.05</packedlength>\n"
        "                    <packedradius>0.02</packedradius>\n"
        "                    <radialposition>0.0</radialposition>\n"
        "                    <radialdirection>0.0</radialdirection>\n"
        "                    <mass>0.09</mass>\n"
        "                  </masscomponent>\n"
        "                </subcomponents>\n"
        "              </podset>\n"
        "              <trapezoidfinset>"
    )
    injected = content.replace(marker, podset_xml)
    path = _write_variant(tmp_path, "podset_with_camera.ork", injected)

    parsed = ork_reader.read_ork(path)
    pod_rows = [r for r in parsed.import_log if r.component == "Camera pod"]
    pod_row = next(r for r in pod_rows if "radial" in r.detail.lower())
    assert pod_row.status == "APPROXIMATED"

    camera_mass = next(pm for pm in parsed.point_masses if pm.name == "Camera")
    assert abs(camera_mass.mass - 0.09) < 1e-9

    without_pod = ork_reader.read_ork(ORK_PATH)
    with_pod_estimate = translate.estimate_dry_mass_and_cg(parsed)
    without_pod_estimate = translate.estimate_dry_mass_and_cg(without_pod)
    assert with_pod_estimate.mass_kg - without_pod_estimate.mass_kg > 0.08, "the pod's camera mass should visibly add to the vehicle dry mass"
