"""2026-09-26 review item B's "real fix" half: detect whether Java (and
therefore RocketSerializer, the tool LASC itself uses per CRS 10.1.5) is
usable on this machine, so the app can tell Diego the right next step
instead of a generic "no wide-Mach Cd curve" dead end.

SCOPE CUT, stated plainly rather than silently skipped: this module only
DETECTS a usable Java - it does not invoke RocketSerializer itself.
Actually running it needs the `rocketserializer` PyPI package (not
installed - not even a rocketpy dependency) AND an OpenRocket .jar to
point it at, and its CLI's exact invocation/output format isn't
something this sandbox can verify (no Java, no OpenRocket install, no
internet access to check the package's real interface). Writing that
integration blind, un-runnable and un-testable here, would risk shipping
broken code with more confidence than it deserves - exactly what
CLAUDE.md Rule 2 ("never invent data") is about. Detection is honest and
testable; the invocation isn't, yet.
"""
import os
import shutil

# Where the official Windows OpenRocket installer places its bundled JRE
# (per Diego's own report of the layout) - checked BEFORE a bare "java"
# on PATH, since a machine can have OpenRocket without a separate Java
# install at all.
WINDOWS_BUNDLED_JRE_CANDIDATES = [
    r"C:\Program Files\OpenRocket\jre\bin\java.exe",
    r"C:\Program Files (x86)\OpenRocket\jre\bin\java.exe",
]


def find_java():
    """Returns (java_path, source) if a usable `java` executable is
    found, else (None, None). Checks OpenRocket's own bundled JRE first
    (most likely to actually be present on a rocketry team's machine),
    then falls back to whatever `java` resolves to on PATH."""
    for candidate in WINDOWS_BUNDLED_JRE_CANDIDATES:
        if os.path.isfile(candidate):
            return candidate, "OpenRocket's bundled JRE"
    on_path = shutil.which("java")
    if on_path:
        return on_path, "java on PATH"
    return None, None


def rocketserializer_status_message():
    """Plain-English status for the Analysis/Validation page and the
    report's Aerodynamics section - CLAUDE.md Sec 4.2 point 3's "detect
    whether Java is present" requirement."""
    java_path, source = find_java()
    if java_path:
        return (
            f"Java found ({source}: {java_path}), but this app does not yet run RocketSerializer automatically "
            "(needs the separate `rocketserializer` package plus your OpenRocket .jar - not wired up this session, "
            "see rocketserializer_check.py's docstring for why). "
            "For now: run an OpenRocket simulation with this exact motor at a high enough angle/altitude to reach "
            "your real max Mach, and save the .ork - the stored data will cover the real Mach range."
        )
    return (
        "No usable Java found on this machine, so RocketSerializer (the drag-curve tool LASC itself uses, CRS 10.1.5) "
        "isn't available as a cross-check. Run an OpenRocket simulation with this exact motor and save the .ork so "
        "the stored data covers your real Mach range - that's the direct fix for the extrapolation warning above."
    )
