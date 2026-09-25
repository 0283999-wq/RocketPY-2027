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
        fore = parent_aft_m - value - child_length_m
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
            _parse_subcomponents_of(comp, fore, aft, parsed, log)

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
            _parse_subcomponents_of(comp, fore, aft, parsed, log)

        elif tag in ("tubefin", "freeformfinset", "streamer", "railbutton_orphan"):
            log.append(ImportRow(cname, "IGNORED", f"<{tag}> as a top-level stage child is not handled by this reader - flag for manual review"))

        else:
            log.append(ImportRow(cname, "IGNORED", f"unhandled top-level tag <{tag}>"))

    return parsed


def _apply_overrides(bodytube_elem, cname, parsed, log, component_fore_m=0.0):
    mass_elem = _find(bodytube_elem, "overridemass")
    cg_elem = _find(bodytube_elem, "overridecg")
    if mass_elem is None and cg_elem is None:
        return

    sub_mass = _find(bodytube_elem, "overridesubcomponentsmass")
    override_sub_mass = sub_mass is not None and sub_mass.text and sub_mass.text.strip().lower() == "true"
    sub_cg = _find(bodytube_elem, "overridesubcomponentscg")
    override_sub_cg = sub_cg is not None and sub_cg.text and sub_cg.text.strip().lower() == "true"

    mass_val = _text_num(mass_elem) if mass_elem is not None else None
    # overridecg's value, like other OpenRocket position values, is an offset from this
    # component's own fore end (NOT verified against a real example carrying this tag -
    # flagged APPROXIMATED below regardless of which branch is taken).
    cg_val = component_fore_m + _text_num(cg_elem) if cg_elem is not None and _text_num(cg_elem) is not None else None

    parsed.mass_overrides.append(MassOverride(cname, mass_val, override_sub_mass, cg_val, override_sub_cg))
    detail = f"mass={mass_val}, override_subcomponents_mass={override_sub_mass}, cg={cg_val}, override_subcomponents_cg={override_sub_cg}"
    status = "IMPORTED" if mass_elem is not None else "APPROXIMATED"
    log.append(ImportRow(f"{cname} (override)", status, detail + (" - overridecg offset convention not verified against a real example, treat as approximate" if cg_elem is not None else "")))

    for child in bodytube_elem:
        t = _local(child.tag)
        if t.startswith("override") and t not in ("overridemass", "overridesubcomponentsmass", "overridecg", "overridesubcomponentscg"):
            log.append(ImportRow(f"{cname} ({t})", "APPROXIMATED", "override tag present but not specifically handled by this reader - verify manually"))


def _parse_subcomponents_of(parent_elem, parent_fore_m, parent_aft_m, parsed, log):
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
            prev_aft = fore + root_chord

        elif tag == "masscomponent":
            mass = _child_text_num(comp, "mass", 0.0)
            fore = _resolve_child_position(pos_elem, parent_fore_m, parent_aft_m, 0.0, prev_aft, log, cname)
            parsed.point_masses.append(PointMass(name=cname, mass=mass, position_m=fore))
            log.append(ImportRow(cname, "IMPORTED", f"mass={mass:.4f} kg @ {fore:.4f} m"))
            prev_aft = fore

        elif tag in ("shockcord", "innertube", "centeringring", "launchlug"):
            log.append(ImportRow(cname, "IGNORED", f"<{tag}> is a structural/mounting part with negligible or hard-to-isolate mass - not added as a point mass; add manually if it's significant"))

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
    )


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
    return parsed
