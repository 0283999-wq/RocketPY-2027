"""Pure-Python OpenRocket (.ork) file reader.

Handles both zip-wrapped .ork files (the normal case: a zip containing a
top-level `rocket.ork` XML entry, detected by the 'PK' zip magic bytes -
NOT by the .ork extension) and bare-XML .ork files (older exports, or
hand-edited ones).

Schema verified against 3 real files from github.com/openrocket/openrocket
core/src/main/resources/datafiles/examples/ (as directed by CLAUDE.md
Sec 4.1, since no PROMETEO/Major Tom .ork exists in this repo yet) - not
reconstructed from memory of the format.

Scope: single-stage rockets, one active motor configuration (the LASC
K/L-class competition shape this whole program targets). Multi-stage,
clustered, pod and booster components are recorded in the import log as
IGNORED rather than silently dropped or guessed at - see ImportRow.

Position resolution (the one genuinely ambiguous part of this format):
top-level stage children (nosecone, bodytube, transition...) carry NO
<position> element in every file checked - OpenRocket stacks them nose-to
-tail automatically in document order, so this reader does the same.
Components nested inside a bodytube's own <subcomponents> (fins, parachutes,
point masses, rail buttons...) DO carry an explicit
<position type="top|bottom|middle|absolute">value</position>, resolved
relative to that parent tube per _resolve_child_position(). Every resolved
position is logged as APPROXIMATED, not IMPORTED - the formula is a
reasonable reading of the OpenRocket UI's own semantics, not a value
verified against another source.
"""

import io
import math
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field


@dataclass
class ImportRow:
    component: str
    status: str  # IMPORTED / APPROXIMATED / IGNORED
    detail: str


@dataclass
class NoseCone:
    name: str
    length: float
    shape: str
    shape_parameter: float
    aft_radius: float
    position_m: float  # fore end, m from nose tip (positive = aft)
    material_density: float = None  # kg/m3, bulk material of the shell


@dataclass
class BodyTube:
    name: str
    length: float
    radius: float  # None if "auto" and no enclosing transition to infer from
    thickness: float
    position_m: float  # fore end, m from nose tip
    material_density: float = None  # kg/m3


@dataclass
class Transition:
    name: str
    length: float
    fore_radius: float
    aft_radius: float
    shape: str
    position_m: float
    material_density: float = None  # kg/m3


@dataclass
class FinSet:
    name: str
    count: int
    root_chord: float
    tip_chord: float
    span: float
    sweep_length: float
    thickness: float
    cant_angle: float
    position_m: float  # root chord leading edge, m from nose tip
    material_density: float = None  # kg/m3


@dataclass
class PointMass:
    name: str
    mass: float
    position_m: float


@dataclass
class Parachute:
    name: str
    cd: float  # None if "auto" (OpenRocket computes it internally; we can't)
    diameter: float
    deploy_event: str
    deploy_altitude: float
    deploy_delay: float
    position_m: float
    # 2026-09-26 review item D (new lettering): "reefed with line cutter" -
    # OpenRocket has NO concept of this at all, so these are always
    # user-set in the app, never parsed from the .ork. cd/diameter above
    # ARE the FULL (un-reefed) canopy's own values when is_reefed=True;
    # reefed_* describe the smaller, reefed configuration that flies
    # first, before the cutter releases it into the full canopy above.
    # deploy_event/deploy_altitude/deploy_delay above are the REEFED
    # stage's own trigger (when the reefed canopy first comes out) -
    # cutter_altitude_m/cutter_delay_s are separately when the line
    # cutter later releases it to full, a different, later event.
    is_reefed: bool = False
    reefed_diameter_m: float = None
    reefed_cd: float = None
    cutter_altitude_m: float = None
    cutter_delay_s: float = 0.0


@dataclass
class RailButtons:
    name: str
    upper_position_m: float
    lower_position_m: float


@dataclass
class MassOverride:
    component: str
    override_mass: float
    override_subcomponents_mass: bool
    override_cg_m: float = None  # m from nose tip; None if no <overridecg> was present
    override_subcomponents_cg: bool = False


@dataclass
class LaunchConditions:
    rail_length_m: float
    rail_angle_from_vertical_deg: float  # OpenRocket "rod angle", 0 = vertical
    rail_direction_deg: float
    altitude_m: float
    latitude: float
    longitude: float
    wind_average_ms: float
    wind_direction_deg: float = 0.0  # compass bearing the wind blows FROM, degrees (OpenRocket <winddirection> is in radians - converted here)

    @property
    def inclination_deg(self):
        """rocketpy Flight(inclination=...) is measured from horizontal
        (90 = vertical); OpenRocket's launchrodangle is measured from
        vertical (0 = vertical). Conversion is direct, but NOT
        cross-checked against a real flight yet - verify against the
        databranch's own t=0 zenith angle when a real .ork/CSV pair is
        available (see CLAUDE.md Sec 4.3 zenith/inclination note).
        """
        return 90.0 - self.rail_angle_from_vertical_deg


@dataclass
class ParsedRocket:
    name: str
    nose: "NoseCone | None"
    body_tubes: list = field(default_factory=list)
    transitions: list = field(default_factory=list)
    fins: list = field(default_factory=list)
    point_masses: list = field(default_factory=list)
    parachutes: list = field(default_factory=list)
    rail_buttons: "RailButtons | None" = None
    mass_overrides: list = field(default_factory=list)
    launch: "LaunchConditions | None" = None
    import_log: list = field(default_factory=list)

    def print_import_table(self):
        print(f"{'Component':<30} {'Status':<12} {'Detail'}")
        for row in self.import_log:
            print(f"{row.component:<30} {row.status:<12} {row.detail}")


def _local(tag):
    """Strip any XML namespace prefix - OpenRocket files are unprefixed in
    practice but this keeps the reader honest either way."""
    return tag.split("}")[-1]


def _find(elem, tag):
    for child in elem:
        if _local(child.tag) == tag:
            return child
    return None


def _findall(elem, tag):
    return [child for child in elem if _local(child.tag) == tag]


def _text_num(elem, default=None):
    """Handles both plain numeric text ('0.0548') and OpenRocket's
    'auto <value>' convention (radius/cd fields when auto-sizing is on -
    the value present is the currently-computed one, still usable)."""
    if elem is None or elem.text is None:
        return default
    txt = elem.text.strip()
    if txt.startswith("auto"):
        parts = txt.split()
        if len(parts) > 1:
            try:
                return float(parts[1])
            except ValueError:
                return None
        return None  # "auto" with no resolved value - genuinely unknown
    try:
        return float(txt)
    except ValueError:
        return None


def _child_text_num(elem, tag, default=None):
    return _text_num(_find(elem, tag), default)


def _material_density(elem):
    mat = _find(elem, "material")
    if mat is None:
        return None
    try:
        return float(mat.get("density"))
    except (TypeError, ValueError):
        return None


def _hollow_cylinder_mass(outer_r, inner_r, length, density):
    """2026-09-30 review: a real .ork's <innertube>/<centeringring>/
    <launchlug>/<tubefin>/<tubecoupler> almost always has a real
    <material density=...> plus enough geometry to compute its mass
    exactly like OpenRocket's own UI does (density x hollow-cylinder
    volume) - these are NOT negligible in a real rocket (e.g. an
    aluminum centering ring easily weighs tens of grams), so silently
    treating every one as zero-mass ("IGNORED... negligible") when no
    <overridemass> happens to be set was undercounting dry mass. Mirrors
    the bulkhead branch's own "prefer override, else density x volume,
    else give up" pattern. Returns None (not computable) if any input is
    missing or the geometry doesn't make sense (inner >= outer)."""
    if outer_r is None or inner_r is None or length is None or density is None:
        return None
    if inner_r >= outer_r or outer_r <= 0 or length <= 0:
        return None
    return math.pi * (outer_r**2 - inner_r**2) * length * density


def load_ork(path):
    """Returns the root <openrocket> XML Element, transparently unwrapping
    the zip container when present."""
    with open(path, "rb") as f:
        head = f.read(2)
    if head == b"PK":
        with zipfile.ZipFile(path) as z:
            inner_name = next((n for n in z.namelist() if n.endswith(".ork") or n == "rocket.ork"), None)
            if inner_name is None:
                raise ValueError(f"{path}: zip .ork with no rocket.ork/*.ork entry found ({z.namelist()})")
            data = z.read(inner_name)
    else:
        with open(path, "rb") as f:
            data = f.read()
    return ET.fromstring(data)


def _resolve_child_position(pos_elem, parent_fore_m, parent_aft_m, child_length_m, prev_sibling_aft_m, log, comp_name):
    """value is in the <position type=...> element; child_length_m is the
    child's own axial extent (0.0 for point-like components: masses,
    rail buttons, parachutes)."""
    if pos_elem is None:
        pos_type, value = "after", 0.0
    else:
        pos_type = pos_elem.get("type", "after")
        try:
            value = float(pos_elem.text) if pos_elem.text else 0.0
        except ValueError:
            value = 0.0

    if pos_type == "top":
        fore = parent_fore_m + value
    elif pos_type == "bottom":
        # 2026-09-26 review item 1: this used to be
        # `parent_aft_m - value - child_length_m`, which is backwards for
        # a NEGATIVE value (the common case - see below) and was pushing
        # every such component outside its own parent's bounds. Verified
        # against PROMETEO's real .ork (no invented case): e.g.
        # "Sistema de recuperacion" (bottom, value=-0.8773) inside the
        # 1.2 m "Fuselage" tube. The old formula gave 2.3473 m - outside
        # the whole 1.47 m airframe. OpenRocket's own UI would never let
        # a component's *nominal* position sit fully outside its parent
        # tube for a plain "bottom" offset like this, so a value this
        # large moving it further OUTSIDE on a negative offset cannot be
        # right. Flipping the sign (`+ value` instead of `- value`) puts
        # it at 0.5927 m - inside the tube, right where a recovery bay
        # would sit - and does the same for every other "bottom"-type
        # component in this file (all previously computed outside their
        # tube, all now inside it). No OpenRocket source access from this
        # sandbox to cite chapter and verse, so this is empirical, not
        # textbook - but it's the formula that stops producing physically
        # impossible positions on real, unmodified data.
        fore = parent_aft_m + value - child_length_m
    elif pos_type == "middle":
        parent_mid = (parent_fore_m + parent_aft_m) / 2.0
        fore = parent_mid - child_length_m / 2.0 + value
    elif pos_type == "absolute":
        fore = value  # OpenRocket "absolute" is already nose-tip-referenced
    elif pos_type == "after":
        fore = prev_sibling_aft_m if prev_sibling_aft_m is not None else parent_fore_m
    else:
        fore = parent_fore_m
        log.append(ImportRow(comp_name, "APPROXIMATED", f"unrecognized position type {pos_type!r}, assumed parent fore end"))
        return fore

    log.append(ImportRow(comp_name, "APPROXIMATED", f"position type={pos_type} value={value} -> {fore:.4f} m from nose (formula-derived, not independently verified)"))
    return fore


def parse_rocket(root):
    log = []
    rocket_elem = _find(root, "rocket")
    if rocket_elem is None:
        raise ValueError("no <rocket> element found - is this a valid .ork?")
    name = _find(rocket_elem, "name")
    name = name.text if name is not None and name.text else "unnamed"

    stages = []
    top_sub = _find(rocket_elem, "subcomponents")
    if top_sub is not None:
        stages = _findall(top_sub, "stage")
    if len(stages) == 0:
        raise ValueError("no <stage> found under <rocket><subcomponents>")
    if len(stages) > 1:
        log.append(ImportRow("rocket", "IGNORED", f"{len(stages)} stages found - this reader only supports single-stage rockets, using stage 1 only"))

    stage = stages[0]
    stage_sub = _find(stage, "subcomponents")

    parsed = ParsedRocket(name=name, nose=None, import_log=log)
    cursor_m = 0.0  # current fore-referenced write head, m from nose tip

    for comp in (stage_sub if stage_sub is not None else []):
        tag = _local(comp.tag)
        cname_elem = _find(comp, "name")
        cname = cname_elem.text if cname_elem is not None and cname_elem.text else tag

        if tag == "nosecone":
            length = _child_text_num(comp, "length", 0.0)
            aft_radius = _child_text_num(comp, "aftradius")
            nose = NoseCone(
                name=cname,
                length=length,
                shape=(_find(comp, "shape").text if _find(comp, "shape") is not None else "ogive"),
                shape_parameter=_child_text_num(comp, "shapeparameter", 1.0),
                aft_radius=aft_radius,
                position_m=cursor_m,
                material_density=_material_density(comp),
            )
            parsed.nose = nose
            log.append(ImportRow(cname, "IMPORTED", f"length={length:.4f} m, aft_radius={aft_radius}, shape={nose.shape}"))
            _apply_overrides(comp, cname, parsed, log, component_fore_m=cursor_m)
            cursor_m += length
            _parse_subcomponents_of(comp, cursor_m - length, cursor_m, parsed, log)

        elif tag == "bodytube":
            length = _child_text_num(comp, "length", 0.0)
            radius = _child_text_num(comp, "radius")
            thickness = _child_text_num(comp, "thickness")
            tube = BodyTube(name=cname, length=length, radius=radius, thickness=thickness, position_m=cursor_m, material_density=_material_density(comp))
            parsed.body_tubes.append(tube)
            detail = f"length={length:.4f} m, radius={radius}"
            log.append(ImportRow(cname, "IMPORTED" if radius is not None else "APPROXIMATED", detail if radius is not None else detail + " (radius was 'auto' with no resolvable value - check against an adjoining tube)"))
            fore, aft = cursor_m, cursor_m + length
            cursor_m = aft
            _apply_overrides(comp, cname, parsed, log, component_fore_m=fore)
            # 2026-09-30 review: this tube's own inner radius, so a
            # <centeringring>/<innertube>/... inside it whose own
            # <outerradius> is "auto" (very common - sized to snugly fit
            # the parent's inside) can still get a real computed mass.
            bodytube_inner_radius_m = (radius - thickness) if radius is not None and thickness is not None else radius
            _parse_subcomponents_of(comp, fore, aft, parsed, log, parent_inner_radius_m=bodytube_inner_radius_m)

        elif tag == "transition":
            length = _child_text_num(comp, "length", 0.0)
            tr = Transition(
                name=cname,
                length=length,
                fore_radius=_child_text_num(comp, "foreradius"),
                aft_radius=_child_text_num(comp, "aftradius"),
                shape=(_find(comp, "shape").text if _find(comp, "shape") is not None else "conical"),
                position_m=cursor_m,
                material_density=_material_density(comp),
            )
            parsed.transitions.append(tr)
            log.append(ImportRow(cname, "IMPORTED", f"length={length:.4f} m, fore_r={tr.fore_radius}, aft_r={tr.aft_radius}"))
            fore, aft = cursor_m, cursor_m + length
            cursor_m = aft
            _apply_overrides(comp, cname, parsed, log, component_fore_m=fore)
            _parse_subcomponents_of(comp, fore, aft, parsed, log)

        elif tag in ("tubefin", "freeformfinset", "streamer", "railbutton_orphan"):
            log.append(ImportRow(cname, "IGNORED", f"<{tag}> as a top-level stage child is not handled by this reader - flag for manual review"))

        else:
            log.append(ImportRow(cname, "IGNORED", f"unhandled top-level tag <{tag}>"))

    return parsed


def _read_overridemass_cg(elem, component_fore_m=0.0):
    """Raw <overridemass>/<overridecg> read, with no side effects (no
    logging, nothing appended to `parsed`) - shared by `_apply_overrides`
    (which DOES log/record it, for components whose mass is otherwise
    estimated in translate.py's _geometric_components) and by the
    bulkhead branch below (which wants the raw value immediately, to
    prefer it over its own density-based estimate, without a second
    generic log line for the same component).
    Returns (mass_val, override_subcomponents_mass, cg_val, override_subcomponents_cg);
    mass_val/cg_val are None if that tag isn't present."""
    mass_elem = _find(elem, "overridemass")
    cg_elem = _find(elem, "overridecg")
    if mass_elem is None and cg_elem is None:
        return None, False, None, False

    sub_mass = _find(elem, "overridesubcomponentsmass")
    override_sub_mass = sub_mass is not None and sub_mass.text and sub_mass.text.strip().lower() == "true"
    sub_cg = _find(elem, "overridesubcomponentscg")
    override_sub_cg = sub_cg is not None and sub_cg.text and sub_cg.text.strip().lower() == "true"

    mass_val = _text_num(mass_elem) if mass_elem is not None else None
    # overridecg's value, like other OpenRocket position values, is an offset from this
    # component's own fore end (NOT verified against a real example carrying this tag -
    # flagged APPROXIMATED below regardless of which branch is taken).
    cg_val = component_fore_m + _text_num(cg_elem) if cg_elem is not None and _text_num(cg_elem) is not None else None
    return mass_val, override_sub_mass, cg_val, override_sub_cg


def _apply_overrides(elem, cname, parsed, log, component_fore_m=0.0):
    """Records this component's <overridemass>/<overridecg> (if any) into
    parsed.mass_overrides and the import log. 2026-09-26 review item 1:
    this used to be called for bodytube components only - PROMETEO's real
    .ork also has a per-component <overridemass> on its nosecone, its fin
    set, and its parachute (0.227/0.505/0.558 kg respectively), none of
    which were ever being read, so translate.py's geometric mass/CG
    estimate silently used the wrong mass for all three (and dropped the
    parachute's packed mass entirely - it isn't a geometric component at
    all otherwise). Now called for every component type that can carry
    these tags; translate._geometric_components looks each one up by
    name via parsed.mass_overrides, same as it already did for the one
    bodytube case."""
    mass_val, override_sub_mass, cg_val, override_sub_cg = _read_overridemass_cg(elem, component_fore_m)
    if mass_val is None and cg_val is None:
        return None

    parsed.mass_overrides.append(MassOverride(cname, mass_val, override_sub_mass, cg_val, override_sub_cg))
    detail = f"mass={mass_val}, override_subcomponents_mass={override_sub_mass}, cg={cg_val}, override_subcomponents_cg={override_sub_cg}"
    status = "IMPORTED" if mass_val is not None else "APPROXIMATED"
    log.append(ImportRow(f"{cname} (override)", status, detail + (" - overridecg offset convention not verified against a real example, treat as approximate" if cg_val is not None else "")))

    for child in elem:
        t = _local(child.tag)
        if t.startswith("override") and t not in ("overridemass", "overridesubcomponentsmass", "overridecg", "overridesubcomponentscg"):
            log.append(ImportRow(f"{cname} ({t})", "APPROXIMATED", "override tag present but not specifically handled by this reader - verify manually"))

    return mass_val


def _parse_subcomponents_of(parent_elem, parent_fore_m, parent_aft_m, parsed, log, parent_inner_radius_m=None):
    """parent_inner_radius_m (2026-09-30 review): the enclosing tube's own
    INNER radius, when known - a <centeringring>'s <outerradius> is very
    commonly "auto" with no resolved value (sized to snugly fit the
    parent tube's inside), which _hollow_cylinder_mass can't use on its
    own. Falling back to this lets that still-common case get a real
    APPROXIMATED mass instead of silently IGNORED. None (the default)
    when the parent's own radius/thickness aren't both resolvable."""
    sub = _find(parent_elem, "subcomponents")
    if sub is None:
        return
    prev_aft = None
    for comp in sub:
        tag = _local(comp.tag)
        cname_elem = _find(comp, "name")
        cname = cname_elem.text if cname_elem is not None and cname_elem.text else tag
        pos_elem = _find(comp, "position")

        if tag == "trapezoidfinset":
            root_chord = _child_text_num(comp, "rootchord", 0.0)
            fore = _resolve_child_position(pos_elem, parent_fore_m, parent_aft_m, root_chord, prev_aft, log, cname)
            fin = FinSet(
                name=cname,
                count=int(_child_text_num(comp, "fincount", 3)),
                root_chord=root_chord,
                tip_chord=_child_text_num(comp, "tipchord", 0.0),
                span=_child_text_num(comp, "height", 0.0),
                sweep_length=_child_text_num(comp, "sweeplength", 0.0),
                thickness=_child_text_num(comp, "thickness", 0.003),
                cant_angle=_child_text_num(comp, "cant", 0.0),
                position_m=fore,
                material_density=_material_density(comp),
            )
            parsed.fins.append(fin)
            log.append(ImportRow(cname, "IMPORTED", f"n={fin.count}, root={fin.root_chord:.4f}, tip={fin.tip_chord:.4f}, span={fin.span:.4f}, sweep={fin.sweep_length:.4f}"))
            _apply_overrides(comp, cname, parsed, log, component_fore_m=fore)
            prev_aft = fore + root_chord

        elif tag == "masscomponent":
            mass = _child_text_num(comp, "mass", 0.0)
            fore = _resolve_child_position(pos_elem, parent_fore_m, parent_aft_m, 0.0, prev_aft, log, cname)
            parsed.point_masses.append(PointMass(name=cname, mass=mass, position_m=fore))
            log.append(ImportRow(cname, "IMPORTED", f"mass={mass:.4f} kg @ {fore:.4f} m"))
            prev_aft = fore

        elif tag in ("innertube", "centeringring", "launchlug", "tubefin"):
            # These can themselves carry <subcomponents> (an inner tube is a
            # very common payload/recovery-bay mount in a real competition
            # rocket, e.g. PROMETEO's "Tubo interior") - recurse using THIS
            # component's own fore/aft as the parent frame, not the outer
            # tube's. Getting this wrong silently mis-places every mass
            # nested inside (caught via a real .ork, not an invented case).
            length = _child_text_num(comp, "length", 0.0)
            fore = _resolve_child_position(pos_elem, parent_fore_m, parent_aft_m, length, prev_aft, log, cname)
            override_mass = _read_overridemass_cg(comp, component_fore_m=fore)[0]
            # 2026-09-30 review: these are real aluminum/plywood/fiberglass
            # parts with a real <material density=...> and enough geometry
            # to compute their mass exactly like OpenRocket's own UI does
            # (density x hollow-cylinder volume) - NOT negligible in a real
            # rocket. <outerradius> is very commonly "auto" (sized to fit
            # snugly inside the parent tube) with no resolved value of its
            # own, so parent_inner_radius_m is the fallback for that case.
            outer_r = _child_text_num(comp, "outerradius")
            if outer_r is None:
                outer_r = parent_inner_radius_m
            inner_r = _child_text_num(comp, "innerradius")
            thickness = _child_text_num(comp, "thickness")
            if inner_r is None and outer_r is not None and thickness is not None:
                inner_r = outer_r - thickness
            density = _material_density(comp)
            own_inner_radius_m = inner_r if inner_r is not None else outer_r
            computed_mass = _hollow_cylinder_mass(outer_r, inner_r, length, density)
            # override_mass is not None (not a truthy check): an
            # <overridemass>0.0</overridemass> is a real, deliberate
            # override (the designer typed 0) that must not silently fall
            # through to the density-based estimate below.
            if override_mass is not None:
                parsed.point_masses.append(PointMass(name=cname, mass=override_mass, position_m=fore + length / 2.0))
                log.append(ImportRow(cname, "IMPORTED", f"mass={override_mass:.4f} kg (measured override on this <{tag}>) @ {fore + length/2.0:.4f} m. Its own subcomponents (if any) ARE still parsed, positioned relative to it."))
            elif computed_mass is not None:
                parsed.point_masses.append(PointMass(name=cname, mass=computed_mass, position_m=fore + length / 2.0))
                log.append(ImportRow(cname, "APPROXIMATED", f"mass={computed_mass:.4f} kg (hollow cylinder: outer_r={outer_r:.4f}, inner_r={inner_r:.4f}, length={length:.4f}, density={density}) @ {fore + length/2.0:.4f} m. Its own subcomponents (if any) ARE still parsed, positioned relative to it."))
            else:
                log.append(ImportRow(cname, "IGNORED", f"<{tag}> radius/thickness/material were not resolvable ('auto' with no parent tube to infer from, or no material) - cannot estimate mass, add manually if significant. Its own subcomponents (if any) ARE still parsed, positioned relative to it."))
            _parse_subcomponents_of(comp, fore, fore + length, parsed, log, parent_inner_radius_m=own_inner_radius_m)
            prev_aft = fore + length

        elif tag == "shockcord":
            log.append(ImportRow(cname, "IGNORED", "<shockcord> is a structural/mounting part with negligible or hard-to-isolate mass - not added as a point mass; add manually if it's significant"))

        elif tag == "bulkhead":
            # A bulkhead IS a real, often non-trivial mass (a solid disk) -
            # unlike innertube/centeringring/launchlug it has no
            # subcomponents of its own. Prefer a measured <overridemass>
            # when present (2026-09-26 review item 1: PROMETEO's real
            # bulkheads all carry one, e.g. 0.075 kg) over the density x
            # volume estimate, which is only a fallback for when no
            # override exists.
            length = _child_text_num(comp, "length", 0.0)
            outer_r = _child_text_num(comp, "outerradius")
            density = _material_density(comp)
            fore = _resolve_child_position(pos_elem, parent_fore_m, parent_aft_m, length, prev_aft, log, cname)
            override_mass = _read_overridemass_cg(comp, component_fore_m=fore)[0]
            if override_mass is not None:
                parsed.point_masses.append(PointMass(name=cname, mass=override_mass, position_m=fore + length / 2.0))
                log.append(ImportRow(cname, "IMPORTED", f"mass={override_mass:.4f} kg (measured override) @ {fore + length/2.0:.4f} m"))
            elif outer_r is not None and density is not None and length > 0:
                mass = math.pi * outer_r**2 * length * density
                parsed.point_masses.append(PointMass(name=cname, mass=mass, position_m=fore + length / 2.0))
                log.append(ImportRow(cname, "APPROXIMATED", f"mass={mass:.4f} kg (solid disk: r={outer_r}, length={length}, density={density}) @ {fore + length/2.0:.4f} m"))
            else:
                log.append(ImportRow(cname, "IGNORED", f"<bulkhead> radius was 'auto'/unresolvable or no material density - cannot estimate mass, add manually if significant"))
            prev_aft = fore + length

        elif tag == "parachute":
            cd_elem = _find(comp, "cd")
            cd = _text_num(cd_elem) if cd_elem is not None else None
            fore = _resolve_child_position(pos_elem, parent_fore_m, parent_aft_m, 0.0, prev_aft, log, cname)
            deploy_event = _find(comp, "deployevent")
            chute = Parachute(
                name=cname,
                cd=cd,
                diameter=_child_text_num(comp, "diameter", 0.0),
                deploy_event=(deploy_event.text if deploy_event is not None else "unknown"),
                deploy_altitude=_child_text_num(comp, "deployaltitude", 0.0),
                deploy_delay=_child_text_num(comp, "deploydelay", 0.0),
                position_m=fore,
            )
            parsed.parachutes.append(chute)
            status = "IMPORTED" if cd is not None else "APPROXIMATED"
            log.append(ImportRow(cname, status, f"diameter={chute.diameter:.4f} m, cd={cd if cd is not None else 'auto - NOT resolvable from this file, must supply manually'}, deploy={chute.deploy_event}@{chute.deploy_altitude}"))
            # 2026-09-26 review item 1: a packed parachute has real mass
            # (PROMETEO's own is 0.558 kg - more than any single mass
            # component elsewhere in this rocket) and was previously not
            # counted in the dry mass/CG at all, since a parachute isn't
            # one of translate.py's other geometric component types.
            # Recording its override here lets _geometric_components pick
            # it up the same way it already does for the one bodytube case.
            _apply_overrides(comp, cname, parsed, log, component_fore_m=fore)
            prev_aft = fore

        elif tag == "railbutton":
            # OpenRocket represents a button PAIR as one <railbutton> element
            # with instancecount=2 and instanceseparation - not two separate
            # elements. instancecount can also be 1 (single button) or >2.
            fore = _resolve_child_position(pos_elem, parent_fore_m, parent_aft_m, 0.0, prev_aft, log, cname)
            instance_count = int(_child_text_num(comp, "instancecount", 1))
            separation = _child_text_num(comp, "instanceseparation", 0.0)
            positions = [fore + i * separation for i in range(instance_count)]
            upper, lower = min(positions), max(positions)
            if parsed.rail_buttons is not None:
                log.append(ImportRow(cname, "IGNORED", "a second <railbutton> component was found - this reader only keeps one pair, first one wins"))
            else:
                parsed.rail_buttons = RailButtons(name=cname, upper_position_m=upper, lower_position_m=lower)
                log.append(ImportRow(cname, "IMPORTED", f"instancecount={instance_count}, separation={separation:.4f} m -> upper@{upper:.4f} m, lower@{lower:.4f} m"))
            prev_aft = fore

        elif tag == "tubecoupler":
            # 2026-09-28 review item 2: previously fell into the generic
            # "unhandled nested tag" IGNORED branch below, silently
            # dropping a real, often substantial measured mass (Major
            # Tom's own tube coupler carries a 1.13 kg <overridemass> -
            # part of the mass-mismatch Diego reported for this rocket).
            # Same shape as the innertube/centeringring/launchlug branch
            # above: can carry its own <subcomponents>, and an override
            # mass (when present) is the team's real measurement, not
            # this reader's own guess, so it always wins over silence.
            length = _child_text_num(comp, "length", 0.0)
            fore = _resolve_child_position(pos_elem, parent_fore_m, parent_aft_m, length, prev_aft, log, cname)
            override_mass = _read_overridemass_cg(comp, component_fore_m=fore)[0]
            # 2026-09-30 review: same hollow-cylinder density x volume
            # fallback as the innertube/centeringring branch above - a
            # tube coupler is a real part (often plywood/fiberglass) with
            # its own <material>, not automatically negligible just
            # because this .ork happens to have no <overridemass> on it.
            outer_r = _child_text_num(comp, "outerradius")
            if outer_r is None:
                outer_r = parent_inner_radius_m
            inner_r = _child_text_num(comp, "innerradius")
            thickness = _child_text_num(comp, "thickness")
            if inner_r is None and outer_r is not None and thickness is not None:
                inner_r = outer_r - thickness
            density = _material_density(comp)
            own_inner_radius_m = inner_r if inner_r is not None else outer_r
            computed_mass = _hollow_cylinder_mass(outer_r, inner_r, length, density)
            if override_mass is not None:
                parsed.point_masses.append(PointMass(name=cname, mass=override_mass, position_m=fore + length / 2.0))
                log.append(ImportRow(cname, "IMPORTED", f"mass={override_mass:.4f} kg (measured override on this <{tag}>) @ {fore + length/2.0:.4f} m. Its own subcomponents (if any) ARE still parsed, positioned relative to it."))
            elif computed_mass is not None:
                parsed.point_masses.append(PointMass(name=cname, mass=computed_mass, position_m=fore + length / 2.0))
                log.append(ImportRow(cname, "APPROXIMATED", f"mass={computed_mass:.4f} kg (hollow cylinder: outer_r={outer_r:.4f}, inner_r={inner_r:.4f}, length={length:.4f}, density={density}) @ {fore + length/2.0:.4f} m. Its own subcomponents (if any) ARE still parsed, positioned relative to it."))
            else:
                log.append(ImportRow(cname, "IGNORED", f"<{tag}> radius/thickness/material were not resolvable ('auto' with no parent tube to infer from, or no material) - cannot estimate mass, add manually if significant. Its own subcomponents (if any) ARE still parsed, positioned relative to it."))
            _parse_subcomponents_of(comp, fore, fore + length, parsed, log, parent_inner_radius_m=own_inner_radius_m)
            prev_aft = fore + length

        else:
            log.append(ImportRow(cname, "IGNORED", f"unhandled nested tag <{tag}>"))


def parse_launch_conditions(root):
    sims = _find(root, "simulations")
    if sims is None:
        return None
    sim = _find(sims, "simulation")
    if sim is None:
        return None
    cond = _find(sim, "conditions")
    if cond is None:
        return None
    return LaunchConditions(
        rail_length_m=_child_text_num(cond, "launchrodlength", 1.0),
        rail_angle_from_vertical_deg=_child_text_num(cond, "launchrodangle", 0.0),
        rail_direction_deg=_child_text_num(cond, "launchroddirection", 0.0),
        altitude_m=_child_text_num(cond, "launchaltitude", 0.0),
        latitude=_child_text_num(cond, "launchlatitude", 0.0),
        longitude=_child_text_num(cond, "launchlongitude", 0.0),
        wind_average_ms=_child_text_num(cond, "windaverage", 0.0),
        wind_direction_deg=math.degrees(_child_text_num(cond, "winddirection", 0.0)),
    )


@dataclass
class SimulationReference:
    """OpenRocket's own numbers for one stored <simulation> - used as the
    "OpenRocket reference" for Phase 1's acceptance check (mass/CG/CP within
    1%). This is NOT flight data and must never be called "validated" -
    only a check against real telemetry earns that word (see CLAUDE.md
    Sec 3.1's wording rule and Phase 2's V1/V2 tests)."""
    name: str
    mass_with_motor_t0_kg: float
    motor_mass_t0_kg: float
    cg_with_motor_t0_m: float  # m from nose tip, t=0 (on the pad, includes motor)
    cp_asymptotic_m: float  # m from nose tip, max stored CP (before AoA/Mach noise)
    i_long_t0: float  # kg m2, "Longitudinal moment of inertia" @ t=0, with motor
    i_rot_t0: float  # kg m2, "Rotational moment of inertia" @ t=0, with motor
    reference_length_m: float  # OpenRocket's own aerodynamic reference length - the rocket's MAX diameter when <referencetype>maximum</referencetype> (the common default; see reference_length_is_max_diameter)
    reference_area_m2: float
    apogee_agl_m: float
    max_velocity_ms: float
    rail_exit_velocity_ms: float
    max_acceleration_ms2: float = None  # 2026-09-28 review item 2: <flightdata maxacceleration="..."> - boost-phase peak, same convention as pipeline.SimResult.max_acceleration_ms2
    max_mach: float = None  # <flightdata maxmach="...">
    cp_at_mach_0_3_m: float = None  # 2026-09-28 review item 2: "CP location" from the recorded datapoint whose "Mach number" is closest to 0.3 - OpenRocket's own design-view stability readout uses Mach 0.3 as its default reference Mach (CLAUDE.md's own "Stability @ M 0.3" convention), which isn't separately persisted in the file, so this is the closest available real number: an ACTUAL simulated aerodynamic state, not an interpolation/guess.
    cp_at_mach_0_3_actual_mach: float = None  # the nearest row's real Mach (for the UI to show "closest recorded point: Mach X, not exactly 0.300")
    reference_length_is_max_diameter: bool = False  # True only when the .ork declares <referencetype>maximum</referencetype> - otherwise reference_length_m is NOT necessarily the max diameter and must not be shown as one
    # 2026-09-30 review item 7: the atmosphere OpenRocket's own stored
    # simulation actually used at t=0 (liftoff) - a real case found this
    # differs from what this app's standard-atmosphere model computes at
    # the same elevation, enough to shift the reported Mach number
    # (0.984 vs. 0.960) even when the simulated SPEED agreed closely
    # (321.5 vs. 322 m/s) - i.e. a different assumed temperature, not a
    # wrong speed prediction. All raw SI units straight from the
    # databranch (Kelvin, Pa, m/s, radians).
    air_temp_k_t0: float = None
    air_pressure_pa_t0: float = None
    wind_speed_ms_t0: float = None
    wind_direction_rad_t0: float = None
    speed_of_sound_ms_t0: float = None


def parse_stored_simulation_references(path):
    """Returns {simulation_name: SimulationReference} for every stored
    <simulation><flightdata><databranch> in the file. Reads the raw XML
    text directly (not the ElementTree root) since a databranch can hold
    tens of thousands of <datapoint> rows - regex-scanning the text for
    the handful of numbers needed is far cheaper than parsing every
    datapoint into an Element."""
    import re

    with open(path, "rb") as f:
        head = f.read(2)
    if head == b"PK":
        with zipfile.ZipFile(path) as z:
            inner_name = next((n for n in z.namelist() if n.endswith(".ork") or n == "rocket.ork"), None)
            data = z.read(inner_name).decode("utf-8")
    else:
        with open(path, encoding="utf-8", errors="replace") as f:
            data = f.read()

    header_m = re.search(r'types="([^"]+)"', data)
    if header_m is None:
        return {}
    header = header_m.group(1).split(",")
    idx = {name: i for i, name in enumerate(header)}

    # <referencetype> is a whole-rocket design setting (not per-simulation) -
    # "maximum" is OpenRocket's common default and the only value under
    # which "Reference length"/"Reference area" are the rocket's own max
    # diameter/area; any other value (e.g. "userdefined") means those
    # columns are NOT necessarily the max diameter, so callers must not
    # show them as one - see reference_length_is_max_diameter.
    reftype_m = re.search(r"<referencetype>([^<]+)</referencetype>", data.split("<simulations>")[0])
    reference_length_is_max_diameter = reftype_m is not None and reftype_m.group(1).strip() == "maximum"

    out = {}
    for branch_m in re.finditer(r'<simulation[^>]*>\s*<name>([^<]+)</name>.*?<flightdata ([^>]*)>(.*?)</simulation>', data, re.S):
        sim_name, attrs, body = branch_m.group(1), branch_m.group(2), branch_m.group(3)

        def attr(a, default=None):
            m = re.search(a + r'="([^"]+)"', attrs)
            return float(m.group(1)) if m else default

        points = re.findall(r"<datapoint>([^<]+)</datapoint>", body)
        if not points:
            continue
        t0 = points[0].split(",")

        def val(row, col, cast=float):
            try:
                v = row[idx[col]]
                return cast(v) if v != "NaN" else None
            except (KeyError, ValueError, IndexError):
                return None

        cps = [v for row in points if (v := val(row.split(","), "CP location")) is not None]

        # 2026-09-28 review item 2: the recorded datapoint whose own "Mach
        # number" is closest to 0.3 - OpenRocket's own default reference
        # Mach for its design-view stability readout, not persisted
        # anywhere else in the file. An ACTUAL simulated aerodynamic
        # state (real CP at whatever Mach that row really is), not an
        # interpolation - cp_at_mach_0_3_actual_mach lets the UI say how
        # close the match really was.
        cp_at_m03, actual_mach = None, None
        best_gap = None
        for row in points:
            cols = row.split(",")
            mach = val(cols, "Mach number")
            if mach is None:
                continue
            gap = abs(mach - 0.3)
            if best_gap is None or gap < best_gap:
                cp_here = val(cols, "CP location")
                if cp_here is not None:
                    best_gap, cp_at_m03, actual_mach = gap, cp_here, mach

        out[sim_name] = SimulationReference(
            name=sim_name,
            mass_with_motor_t0_kg=val(t0, "Mass"),
            motor_mass_t0_kg=val(t0, "Motor mass"),
            cg_with_motor_t0_m=val(t0, "CG location"),
            cp_asymptotic_m=max(cps) if cps else None,
            i_long_t0=val(t0, "Longitudinal moment of inertia"),
            i_rot_t0=val(t0, "Rotational moment of inertia"),
            reference_length_m=val(t0, "Reference length"),
            reference_area_m2=val(t0, "Reference area"),
            apogee_agl_m=attr("maxaltitude"),
            max_velocity_ms=attr("maxvelocity"),
            rail_exit_velocity_ms=attr("launchrodvelocity"),
            max_acceleration_ms2=attr("maxacceleration"),
            max_mach=attr("maxmach"),
            cp_at_mach_0_3_m=cp_at_m03,
            cp_at_mach_0_3_actual_mach=actual_mach,
            reference_length_is_max_diameter=reference_length_is_max_diameter,
            air_temp_k_t0=val(t0, "Air temperature"),
            air_pressure_pa_t0=val(t0, "Air pressure"),
            wind_speed_ms_t0=val(t0, "Wind velocity"),
            wind_direction_rad_t0=val(t0, "Wind direction"),
            speed_of_sound_ms_t0=val(t0, "Speed of sound"),
        )
    return out


def extract_drag_curves_from_stored_sim(path, sim_name=None, aoa_limit_deg=2.0, mach_round=3):
    """CLAUDE.md Sec 4.2's TOP-preference Cd source: the <databranch> data
    OpenRocket already saved inside the .ork itself - no separate CSV
    upload needed for the common case. Mirrors
    reference/prometeo_mission44/scripts/extract_drag_curves.py's method
    (boost = Thrust>0, coast = Thrust==0 from BURNOUT TO APOGEE ONLY;
    both filtered to |AoA|<aoa_limit_deg so induced drag from a pitched-
    over rocket doesn't contaminate the zero-yaw Barrowman curve rocketpy
    wants), applied to the .ork's OWN stored flight instead of an
    exported CSV.

    2026-09-26 review item A: this used to keep every Thrust==0 point
    all the way to the END of the stored sim, not just to apogee. Past
    apogee, OpenRocket's "Axial drag coefficient" includes the deployed
    parachute's drag (the databranch has no separate "chute deployed"
    flag - it's baked into the aggregate axial Cd once one is out), so
    the coast/power-off curve was being contaminated with descent-under-
    canopy Cd values (Diego found this directly: 589.775 from Mach 0.02
    to 0.212, 68 points, in an exported zip's power_off_drag.csv). Fixed
    by tracking "Vertical velocity" and stopping coast collection the
    moment it goes negative (past apogee) - matches the reference
    script's own BURNOUT..APOGEE bound exactly, which was ALREADY correct
    (it doesn't have this bug; only this live in-app path did).

    Returns (power_on_points, power_off_points), each a sorted list of
    (mach, cd) tuples ready to write straight to a headerless 2-column CSV
    for rocketpy's power_on_drag/power_off_drag. Returns (None, None) if
    the requested simulation has no stored databranch at all (a .ork can
    be geometry-only, with no simulation ever run in OpenRocket)."""
    import re
    from collections import defaultdict

    with open(path, "rb") as f:
        head = f.read(2)
    if head == b"PK":
        with zipfile.ZipFile(path) as z:
            inner_name = next((n for n in z.namelist() if n.endswith(".ork") or n == "rocket.ork"), None)
            data = z.read(inner_name).decode("utf-8")
    else:
        with open(path, encoding="utf-8", errors="replace") as f:
            data = f.read()

    header_m = re.search(r'types="([^"]+)"', data)
    if header_m is None:
        return None, None
    header = header_m.group(1).split(",")
    idx = {name: i for i, name in enumerate(header)}
    required = ["Time", "Mach number", "Axial drag coefficient", "Thrust", "Angle of attack", "Vertical velocity"]
    if not all(r in idx for r in required):
        return None, None

    sim_block_m = None
    for m in re.finditer(r'<simulation[^>]*>\s*<name>([^<]+)</name>.*?<flightdata[^>]*>(.*?)</simulation>', data, re.S):
        if sim_name is None or m.group(1) == sim_name:
            sim_block_m = m
            break
    if sim_block_m is None:
        return None, None

    points = re.findall(r"<datapoint>([^<]+)</datapoint>", sim_block_m.group(2))

    def bin_avg(rows):
        bins = defaultdict(list)
        for mach, cd in rows:
            bins[round(mach, mach_round)].append(cd)
        return sorted((m, sum(v) / len(v)) for m, v in bins.items())

    boost, coast = [], []
    burned_out = False
    apogee_reached = False
    for row in points:
        vals = row.split(",")
        try:
            t, mach, cd, thrust, aoa, vertical_velocity = (float(vals[idx[c]]) for c in required)
        except (ValueError, IndexError):
            continue
        if mach != mach or cd != cd:  # NaN check
            continue
        if vertical_velocity < 0:
            apogee_reached = True  # descending - never collect coast points past this, even if aoa/thrust would otherwise pass
        if abs(aoa) >= aoa_limit_deg:
            continue
        if thrust > 0:
            boost.append((mach, cd))
        elif thrust == 0 and not apogee_reached and (boost or burned_out):
            burned_out = True
            coast.append((mach, cd))

    return bin_avg(boost), bin_avg(coast)


def read_ork(path):
    """Top-level entry point: load + parse geometry + parse launch
    conditions (from the first stored simulation), all in one call."""
    root = load_ork(path)
    parsed = parse_rocket(root)
    parsed.launch = parse_launch_conditions(root)
    if parsed.launch is None:
        parsed.import_log.append(ImportRow("launch conditions", "IGNORED", "no <simulations><simulation><conditions> found in this file - rail/site must be supplied separately"))
    else:
        parsed.import_log.append(ImportRow("launch conditions", "IMPORTED", f"rail={parsed.launch.rail_length_m} m, rod_angle={parsed.launch.rail_angle_from_vertical_deg} deg from vertical, alt={parsed.launch.altitude_m} m"))

    for name, pos in components_outside_airframe(parsed):
        airframe_end_m = airframe_length_m(parsed)
        parsed.import_log.append(ImportRow(
            name, "APPROXIMATED",
            f"WARNING: resolved position {pos:.4f} m is OUTSIDE the modeled airframe (0 to {airframe_end_m:.4f} m). "
            "Re-check this component's position in OpenRocket before trusting the simulation - see "
            "bup_rocketpy.ork_reader.components_outside_airframe (also used to BLOCK Simulate in the app, "
            "2026-09-26 review item 2).",
        ))
    return parsed


def airframe_length_m(parsed):
    """Nose tip to the aft-most point of ANY airframe component, m - the
    modeled rocket's own total length, used both as the sanity bound for
    components_outside_airframe() and (2026-09-27 review item 1c) as the
    ONE place every other "rocket length" computation in the app should
    call, instead of each re-deriving its own (previously
    body-tubes-only) formula. A transition/boat-tail placed AFTER the
    last body tube - a common real layout for a tapered motor mount -
    was silently excluded from every one of those duplicated formulas,
    under-stating both the reported length AND (in translate.build_rocket
    and translate.derive_dry_mass_and_inertia_from_with_motor, which
    assumes the motor/nozzle sits at this airframe's own aft end) the
    assumed motor position - part of the real Major Tom mass/CG
    mismatch Diego reported (2026-09-27 review item 1)."""
    nose_len = parsed.nose.length if parsed.nose is not None else 0.0
    tube_end = max((t.position_m + t.length for t in parsed.body_tubes), default=nose_len)
    transition_end = max((tr.position_m + tr.length for tr in parsed.transitions), default=0.0)
    return max(nose_len, tube_end, transition_end)


def fin_envelope_end_m(parsed):
    """2026-09-28 review item 2: the aft-most point of any fin's SWEPT
    TIP (root_position + max(root_chord, sweep_length + tip_chord)) -
    can extend past airframe_length_m() for a swept-back fin (a fin
    whose root trailing edge lands at the airframe's own aft end, but
    whose swept tip trailing edge reaches further back still). Kept
    SEPARATE from airframe_length_m() rather than folded into it:
    airframe_length_m() is also used to place the motor
    (translate.build_rocket/derive_dry_mass_and_inertia_from_with_motor
    assume the motor sits at the STRUCTURAL airframe's own aft end,
    which the fin surface's extent has no bearing on - a swept fin
    overhanging the tail doesn't move where the motor mount is).

    2026-09-30 review item 4 correction: an earlier version of this
    docstring reported that folding fin overhang into the DISPLAYED
    "Overall length" made a real comparison against OpenRocket WORSE,
    based on one specific design's numbers at the time. Diego's own
    explicit, current instruction is unambiguous - "Overall length = the
    most-aft point of ANY component, including swept fin tips that
    overhang the tail" - and a separate real case now shows the
    opposite: OpenRocket's own reported length (194 cm) matches
    reported_length_m() below (which includes this function), not
    airframe_length_m() alone (189.5 cm). Whether fin overhang belongs
    in OpenRocket's own "Length" figure evidently depends on the
    specific fin geometry/OpenRocket version; per Diego's instruction,
    it is now ALWAYS included in what this app reports and displays as
    the vehicle's overall length - see reported_length_m()."""
    return max(
        (f.position_m + max(f.root_chord, f.sweep_length + f.tip_chord) for f in parsed.fins),
        default=0.0,
    )


def reported_length_m(parsed):
    """2026-09-30 review item 4: the vehicle's overall length as shown to
    a reader (Rocket page, OpenRocket comparison card, report) - the
    most-aft point of ANY component, including swept fin tip overhang
    (see fin_envelope_end_m()'s docstring for why this differs from
    airframe_length_m(), which stays structural-only for motor
    placement/bounds-checking and must NOT be changed to this)."""
    return max(airframe_length_m(parsed), fin_envelope_end_m(parsed))


def components_outside_airframe(parsed):
    """2026-09-26 review item 2: "never hang" - returns a list of
    (component_name, resolved_position_m) for every point mass, fin set
    and parachute whose resolved axial position falls outside [0,
    airframe_length_m(parsed)]. This is exactly the class of bug item 1
    fixed (a wrong 'bottom' sign pushing a component's resolved position
    way outside its own airframe) - callers (the app's Simulate button)
    should treat a non-empty result as a hard stop, not a warning, since
    a component modeled outside the airframe is exactly what produced the
    -1.41 cal margin / hung simulation this review reports."""
    airframe_end_m = airframe_length_m(parsed)
    out = []
    for pm in parsed.point_masses:
        if pm.position_m < 0 or pm.position_m > airframe_end_m:
            out.append((pm.name, pm.position_m))
    for fin in parsed.fins:
        if fin.position_m < 0 or fin.position_m + fin.root_chord > airframe_end_m:
            out.append((fin.name, fin.position_m))
    for chute in parsed.parachutes:
        if chute.position_m < 0 or chute.position_m > airframe_end_m:
            out.append((chute.name, chute.position_m))
    return out
