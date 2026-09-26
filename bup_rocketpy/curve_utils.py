"""Shared helper for every (x, y) curve this app hands to rocketpy
(2026-09-26 review crash f): rocketpy's linear interpolation
(Function._interpolation, used by both the SolidMotor thrust curve and
the power_on_drag/power_off_drag Cd-vs-Mach curves) computes a slope as
dy/dx between consecutive points - an exact duplicate x value makes
dx=0, producing the "divide by zero encountered in ... polation_1d"
warning Diego saw, and silently corrupting the interpolated curve near
that point (a real accuracy bug, not just a cosmetic warning).

Some RASP .eng exporters legitimately encode a near-instant transition
(thrust dropping to 0 right at burnout) as two points sharing the same
timestamp, so duplicates are not always bad data - the fix here nudges
the later point forward by a tiny epsilon instead of merging/dropping
it, which removes the exact-zero dx while preserving that near-instant
step almost exactly.
"""


def dedupe_sort_curve(points, eps=1e-9):
    """points: iterable of (x, y). Returns (deduped_sorted_points,
    n_duplicates_found). Always sorts by x even if no duplicates are
    found - rocketpy's interpolation also requires strictly ascending x,
    and an unsorted CSV (a real possibility for a hand-exported/edited
    file) is the same class of bug as a duplicate."""
    pts = sorted(points, key=lambda p: p[0])
    if not pts:
        return pts, 0
    out = [pts[0]]
    n_dupes = 0
    for x, y in pts[1:]:
        prev_x = out[-1][0]
        if x <= prev_x:
            x = prev_x + eps
            n_dupes += 1
        out.append((x, y))
    return out, n_dupes


def _read_csv_points(path):
    points = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.replace(",", " ").split()
            if len(parts) < 2:
                continue
            try:
                points.append((float(parts[0]), float(parts[1])))
            except ValueError:
                continue
    return points


def curve_max_x(path_or_constant):
    """2026-09-26 review item B: highest Mach a power_off/power_on drag
    CSV actually covers - None if `path_or_constant` isn't a real CSV
    (translate.DRAG_CURVE_PLACEHOLDER_CD is a bare float, not a path -
    there's no "coverage limit" to check for a constant Cd, it's already
    flagged elsewhere as low-confidence)."""
    if not isinstance(path_or_constant, str):
        return None
    points = _read_csv_points(path_or_constant)
    return max((x for x, _ in points), default=None)


def dedupe_sort_csv(src_path, dst_path, eps=1e-9):
    """Reads a 2-column headerless (x, y) CSV from src_path, applies
    dedupe_sort_curve, and writes the result to dst_path (which may be
    the same as src_path for a file this app owns exclusively, e.g. a
    temp upload - but must NOT be a caller-owned/checked-in file: an
    earlier version of this function rewrote whatever path it was given
    in place, which silently mutated Diego's checked-in
    reference/prometeo_mission44 CSVs (byte-identical content, just a
    dropped trailing newline, but still an unintended write to reference
    data) the first time a test happened to pass one of those paths
    straight through. Always write to a NEW path under the caller's own
    outputs directory instead. Returns n_duplicates_found."""
    points = _read_csv_points(src_path)
    deduped, n_dupes = dedupe_sort_curve(points, eps=eps)
    with open(dst_path, "w", encoding="utf-8") as f:
        f.write("\n".join(f"{x},{y}" for x, y in deduped))
    return n_dupes
