"""Competition profiles (2026-09-26 review item H.2): a small, data-
driven registry so the Exports page's mission-ID naming and the RCSM
Cases page's compliance ruleset both come from ONE place the user picks,
instead of always assuming LASC.

CLAUDE.md Rule 2: "Never invent data." This project has verified rule
text for exactly ONE competition's simulation deliverables: LASC's RCSM
Ed.7 Rev.1 (CLAUDE.md Sec 5, `bup_rocketpy/rcsm.py`). ENMICE and IREC are
included here as real, selectable profiles (so the naming/site fields
exist and a teammate can extend them), but their `compliance_ruleset` is
deliberately None and their `rules_status` says so on screen - this app
does NOT claim to check ENMICE/IREC rules it has never actually been
given. Extending a profile with real verified rules later is a data
change in this file, not a code change.
"""
from dataclasses import dataclass, field


@dataclass
class CompetitionProfile:
    key: str
    display_name: str
    compliance_ruleset: str  # None, or "RCSM_ED7_REV1" (the only ruleset rcsm.py actually implements)
    rules_status: str  # what a user sees about how trustworthy the compliance check is for this profile
    mission_id_template: str  # e.g. "Mission{id}_{case}_RocketPy_v{version}" - CRS 10.1.6 for LASC
    default_site_lat: float = None
    default_site_lon: float = None
    default_site_altitude_m: float = None
    default_site_label: str = ""
    notes: str = ""


PROFILES = {
    "test_flight": CompetitionProfile(
        key="test_flight", display_name="Test flight (no competition)",
        compliance_ruleset=None,
        rules_status="No competition rules apply - this is a plain simulation, run any flight cases you want.",
        mission_id_template="Test{id}_{case}_RocketPy_v{version}",
        notes="Use this for club test flights, subscale tests, and anything not submitted to a competition.",
    ),
    "lasc": CompetitionProfile(
        key="lasc", display_name="LASC (Latin America Space Challenge)",
        compliance_ruleset="RCSM_ED7_REV1",
        rules_status="Verified: RCSM Ed.7 Rev.1 (CLAUDE.md Sec 5) - rail exit, static margin, recovery event timing/rates all checked on the RCSM Cases page.",
        mission_id_template="Mission{id}_{case}_RocketPy_v{version}",  # CRS 10.1.6, verified
        default_site_lat=-21.900, default_site_lon=-48.960, default_site_altitude_m=490.0,
        default_site_label="Sugarcane Launch Range, Iacanga SP, Brazil",
        notes="CRS 10.1.3/10.1.5: submission must be a runnable .py/.ipynb or .ork a RocketPy/LASC team member can run standalone - see the Exports page's LASC .zip button.",
    ),
    "enmice": CompetitionProfile(
        key="enmice", display_name="ENMICE",
        compliance_ruleset=None,
        rules_status="NOT VERIFIED - this project has no confirmed ENMICE simulation-deliverable rule text yet. The RCSM Cases page will still run Ballistic/Nominal/Drogue-only/Main-at-apogee, but does NOT check them against ENMICE's own pass/fail criteria. Ask Diego for ENMICE's rules before relying on this for a real submission.",
        mission_id_template="ENMICE_{id}_{case}_RocketPy_v{version}",
        notes="Placeholder profile - site/naming fields are editable defaults, not verified competition requirements.",
    ),
    "irec": CompetitionProfile(
        key="irec", display_name="IREC (Spaceport America Cup)",
        compliance_ruleset=None,
        rules_status="NOT VERIFIED - this project has no confirmed IREC simulation-deliverable rule text yet. The RCSM Cases page will still run Ballistic/Nominal/Drogue-only/Main-at-apogee, but does NOT check them against IREC's own pass/fail criteria. Ask Diego for IREC's rules before relying on this for a real submission.",
        mission_id_template="IREC_{id}_{case}_RocketPy_v{version}",
        default_site_lat=32.990, default_site_lon=-106.972, default_site_altitude_m=1401.0,
        default_site_label="Spaceport America, NM, USA (public coordinates - verify altitude/site details before use)",
        notes="Placeholder profile - site/naming fields are editable defaults, not verified competition requirements.",
    ),
}

DEFAULT_PROFILE_KEY = "test_flight"


def get_profile(key):
    return PROFILES.get(key, PROFILES[DEFAULT_PROFILE_KEY])


def format_mission_id(profile, mission_id, case_name, version):
    return profile.mission_id_template.format(id=mission_id, case=case_name, version=version)
