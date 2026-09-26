"""2026-09-26 review item H.2: competition profiles registry. CLAUDE.md
Rule 2 ("never invent data") means ENMICE/IREC must NOT claim a verified
compliance ruleset this project has never actually been given - these
tests lock that honesty in, plus the LASC naming template staying
byte-identical to CRS 10.1.6's hardcoded default.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bup_rocketpy import case_export, competition_profiles


def test_lasc_profile_has_the_verified_rcsm_ruleset():
    profile = competition_profiles.get_profile("lasc")
    assert profile.compliance_ruleset == "RCSM_ED7_REV1"
    assert "RCSM" in profile.rules_status


def test_enmice_and_irec_do_not_claim_a_verified_ruleset():
    for key in ("enmice", "irec"):
        profile = competition_profiles.get_profile(key)
        assert profile.compliance_ruleset is None, f"{key} must not claim a verified ruleset - none exists in this project"
        assert "NOT VERIFIED" in profile.rules_status


def test_unknown_key_falls_back_to_the_default_profile():
    assert competition_profiles.get_profile("some_typo") is competition_profiles.PROFILES[competition_profiles.DEFAULT_PROFILE_KEY]


def test_lasc_mission_id_template_matches_crs_10_1_6_exactly():
    profile = competition_profiles.get_profile("lasc")
    formatted = competition_profiles.format_mission_id(profile, "44", "Nominal", 1)
    assert formatted == "Mission44_Nominal_RocketPy_v1"


def test_generate_case_script_uses_profile_template_when_given():
    """Also a regression guard for the default (no-template) path: the
    added `mission_id_template` param must not change CRS 10.1.6's exact
    naming for every existing caller that omits it - see
    `default_filename` below."""
    from bup_rocketpy.motor_reader import read_eng
    from bup_rocketpy.ork_reader import read_ork

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ork_path = os.path.join(repo_root, "reference", "prometeo_mission44", "data", "ork", "PrometeoLasc2026.ork")
    eng_path = os.path.join(repo_root, "reference", "prometeo_mission44", "data", "motors", "Icarus_I_K519.eng")
    parsed = read_ork(ork_path)
    parsed_eng = read_eng(eng_path)

    profile = competition_profiles.get_profile("enmice")
    filename, _ = case_export.generate_case_script(
        mission_id="7", case_name="Nominal", version=1,
        parsed=parsed, parsed_eng=parsed_eng, eng_filename="motor.eng",
        power_off_drag_filename="a.csv", power_on_drag_filename="b.csv",
        dry_mass_kg=5.66, dry_cg_m=0.63, i_axial=0.05, i_transverse=1.5, radius_m=0.07,
        include_recovery=False, mission_id_template=profile.mission_id_template,
    )
    assert filename == "ENMICE_7_Nominal_RocketPy_v1.py"

    default_filename, _ = case_export.generate_case_script(
        mission_id="7", case_name="Nominal", version=1,
        parsed=parsed, parsed_eng=parsed_eng, eng_filename="motor.eng",
        power_off_drag_filename="a.csv", power_on_drag_filename="b.csv",
        dry_mass_kg=5.66, dry_cg_m=0.63, i_axial=0.05, i_transverse=1.5, radius_m=0.07,
        include_recovery=False,
    )
    assert default_filename == "Mission7_Nominal_RocketPy_v1.py"


if __name__ == "__main__":
    test_lasc_profile_has_the_verified_rcsm_ruleset()
    test_enmice_and_irec_do_not_claim_a_verified_ruleset()
    test_unknown_key_falls_back_to_the_default_profile()
    test_lasc_mission_id_template_matches_crs_10_1_6_exactly()
    test_generate_case_script_uses_profile_template_when_given()
    print("\nCOMPETITION PROFILES: OK")

