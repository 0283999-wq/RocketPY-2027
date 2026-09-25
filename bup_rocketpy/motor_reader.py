"""RASP (.eng) motor file reader, and a fallback OpenRocket-exported thrust
CSV reader (CRS 10.1.9: the .eng is mandatory for SRAD motors; the CSV path
exists only for the PROMETEO-style fallback CLAUDE.md Sec 3.2 describes -
"only as a fallback if the .eng doesn't arrive, flagged as approximate").

rocketpy's own SolidMotor(thrust_source=<path>) can read a .eng file
directly - this module exists so the app can show header metadata (motor
designation, total/propellant mass, delays) in the imported-data table
*before* handing the path to rocketpy, and so it can validate the file
before that point (CRS 10.1.9 compliance, catching a malformed upload
early instead of letting rocketpy's own error surface confuse Diego).
"""

from dataclasses import dataclass, field


@dataclass
class EngHeader:
    designation: str
    diameter_mm: float
    length_mm: float
    delays: str
    propellant_mass_kg: float
    total_mass_kg: float
    manufacturer: str


@dataclass
class ParsedEng:
    header: EngHeader
    thrust_curve: list  # [(t_s, thrust_N), ...]
    comments: list

    @property
    def total_impulse_Ns(self):
        pts = self.thrust_curve
        impulse = 0.0
        for (t0, f0), (t1, f1) in zip(pts, pts[1:]):
            impulse += (f0 + f1) / 2.0 * (t1 - t0)
        return impulse

    @property
    def burn_time_s(self):
        return self.thrust_curve[-1][0] if self.thrust_curve else 0.0

    @property
    def peak_thrust_N(self):
        return max((f for _, f in self.thrust_curve), default=0.0)


def read_eng(path):
    """Parses a RASP-format .eng file. Format (one motor per file, this
    reader takes the first): comment lines start with ';'; the header line
    is `designation diameter_mm length_mm delays propellant_kg total_kg
    manufacturer`; every following non-comment line is `time_s thrust_N`
    until the next header line or EOF.
    """
    comments = []
    header = None
    thrust_curve = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            if line.startswith(";"):
                comments.append(line.lstrip(";").strip())
                continue
            if header is None:
                parts = line.split()
                if len(parts) < 7:
                    raise ValueError(f"{path}: malformed RASP header line: {line!r}")
                header = EngHeader(
                    designation=parts[0],
                    diameter_mm=float(parts[1]),
                    length_mm=float(parts[2]),
                    delays=parts[3],
                    propellant_mass_kg=float(parts[4]),
                    total_mass_kg=float(parts[5]),
                    manufacturer=parts[6],
                )
                continue
            parts = line.split()
            if len(parts) != 2:
                # some exporters emit a trailing bare ';' data terminator line - ignore
                continue
            t, thrust = float(parts[0]), float(parts[1])
            thrust_curve.append((t, thrust))

    if header is None:
        raise ValueError(f"{path}: no RASP header line found - not a valid .eng file")
    if not thrust_curve:
        raise ValueError(f"{path}: header parsed but no thrust data points found")

    return ParsedEng(header=header, thrust_curve=thrust_curve, comments=comments)


def read_thrust_csv(path, time_col="Time (s)", thrust_col="Thrust (N)"):
    """Fallback path: a two-column CSV (either a bare time,thrust export, or
    picked out of a full OpenRocket comment-header export via io_utils-style
    column names). Returns [(t_s, thrust_N), ...]. Always flagged
    APPROXIMATE by the caller per CLAUDE.md Sec 3.2 - this has no motor
    mass/propellant-mass header the way a .eng does.
    """
    import pandas as pd

    df = pd.read_csv(path)
    if time_col not in df.columns or thrust_col not in df.columns:
        # try the OpenRocket comment-header format (see io_utils.load_openrocket_csv
        # in reference/prometeo_mission44 for the pattern this mirrors)
        with open(path, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        header_line = next((ln for ln in lines if ln.startswith("# Time (s)")), None)
        if header_line is None:
            raise ValueError(f"{path}: columns {time_col!r}/{thrust_col!r} not found, and no OpenRocket '# Time (s)' header either")
        import io as _io

        header = header_line.lstrip("#").strip().split(",")
        data_lines = [ln for ln in lines if not ln.startswith("#") and ln.strip()]
        df = pd.read_csv(_io.StringIO("".join(data_lines)), header=None, names=header)

    curve = list(zip(df[time_col].astype(float), df[thrust_col].astype(float)))
    return [pt for pt in curve if pt[0] >= 0]
