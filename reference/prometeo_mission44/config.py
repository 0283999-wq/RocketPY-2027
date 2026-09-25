"""Mission 44 PROMETEO - all simulation constants, one place, one source each.

Every number here traces to data/openrocket_exports/*.csv (OpenRocket export,
comment-header format, see scripts/build_eng_from_openrocket.py for the parser),
data/flight_data/telemetry_2026_07_04.xlsx, or a named team document. Numbers
that exist nowhere in the delivered data are marked # TODO MEASURE and listed
in docs/OPEN_ITEMS.md. Conflicts between sources are resolved here and logged
in docs/model_assumptions.md - this file holds the value actually used, not
a survey of candidates.
"""

import os

G0 = 9.80665  # m/s2, standard gravity, used for Isp back-calc below

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(REPO_ROOT, "data")
OUTPUTS_DIR = os.path.join(REPO_ROOT, "outputs")

# --------------------------------------------------------------------------
# VEHICLE - Brasil (SLR, competition) t=0 state
# --------------------------------------------------------------------------
# CRS 10.2.1 note: table given at project kickoff quoted 10.810 kg / CG 96.699 cm
# for this same t=0 row. Neither figure is what the CSV actually contains - see
# docs/model_assumptions.md "Launch mass conflict" for the full comparison and
# why we trust the CSV export over the transcribed table.
LAUNCH_MASS = 10.400  # kg. Prometeo_Launchsite_BRASIL.csv col `Mass (g)` @ t=0 = 1.04e4 g
MOTOR_MASS_LOADED = 4.7378  # kg. same file, col `Motor mass (g)` @ t=0 = 4737.823 g
MOTOR_DRY_MASS = 2.7211  # kg. same col, min value (post-burnout, casing+hardware only)
PROPELLANT_MASS = MOTOR_MASS_LOADED - MOTOR_DRY_MASS  # 2.0167 kg, matches static-fire load
DRY_MASS_NO_MOTOR = LAUNCH_MASS - MOTOR_MASS_LOADED  # 5.6622 kg. rocketpy Rocket(mass=...) wants this, not launch mass

# OpenRocket "Reference length" IS the body tube OD used for its caliber math -
# use it verbatim instead of the doc's rounded "0.110 m" so stability margins
# reproduce OpenRocket's own numbers exactly.
DIAMETER = 0.1096  # m. Prometeo_Launchsite_BRASIL.csv col `Reference length (cm)` = 10.96
RADIUS = DIAMETER / 2  # 0.0548 m
REFERENCE_AREA = 94.343e-4  # m2. same file col `Reference area (cm²)`, cross-check: pi*r^2=94.3cm2 OK

LENGTH = 1.54  # m, PROMETEO Design Evolution Report - not present in any CSV column

# CG/inertia at t=0 include the loaded motor (OpenRocket convention). The
# no-motor values rocketpy needs are derived in src/prometeo/rocket.py via
# parallel-axis subtraction - see docs/model_assumptions.md "Inertia" section
# for the worked derivation, don't just eyeball these two into Rocket().
CG_T0_WITH_MOTOR = 0.97966  # m from nose tip. col `CG location (cm)` @ t=0 = 97.966
INERTIA_LONG_T0_WITH_MOTOR = 1.612  # kg m2. col `Longitudinal moment of inertia (kg·m²)` @ t=0
INERTIA_ROT_T0_WITH_MOTOR = 0.020  # kg m2. col `Rotational moment of inertia (kg·m²)` @ t=0

CP_ASYMPTOTIC = 1.21706  # m from nose. same file, col `CP location (cm)`, max over flight (NaN before rail exit - OR only reports CP once AoA solver has airspeed)

PAYLOAD_MASS = 1.2  # kg, PEZ dispenser, Design Evolution Report
PAYLOAD_LENGTH = 0.15  # m, same source
PAYLOAD_DIAMETER = 0.088  # m, same source

# --------------------------------------------------------------------------
# OPEN ITEMS - not in any delivered file, see docs/OPEN_ITEMS.md
# --------------------------------------------------------------------------
# rocketpy needs *some* number here to fly a 6-DOF sim at all (no fins = no
# restoring moment = a numerically-fine but physically-nonsense flight). These
# are placeholders picked to be plausible for a 110mm/1.54m K-class airframe,
# NOT a measurement - Flight() will run on them but CP/static-margin output
# should be read as "roughly the right shape", not "correct". Real geometry
# supersedes these the moment the team measures it (see docs/OPEN_ITEMS.md).
FIN_COUNT = 4  # TODO CONFIRM - not in CSV, 4 assumed (common for this class)
FIN_ROOT_CHORD = 0.20  # m # TODO MEASURE
FIN_TIP_CHORD = 0.08  # m # TODO MEASURE
FIN_SPAN = 0.12  # m # TODO MEASURE
FIN_SWEEP = 0.10  # m # TODO MEASURE
FIN_POSITION_FROM_NOSE = 1.34  # m, root chord leading edge # TODO MEASURE
FIN_CANT_ANGLE = 0.0  # deg # TODO CONFIRM
NOSE_CONE_TYPE = "von karman"  # TODO CONFIRM - ogive/elliptical/von Karman unconfirmed, von Karman assumed (minimum drag, common for competition nose cones)
NOSE_CONE_LENGTH = 0.35  # m # TODO MEASURE
RAIL_BUTTON_UPPER_FROM_NOSE = 1.10  # m # TODO MEASURE
RAIL_BUTTON_LOWER_FROM_NOSE = 1.35  # m # TODO MEASURE
MOTOR_CASING_DIAMETER = 0.075  # m # TODO CONFIRM - back-calculated from grain OD 2.95in + wall clearance, not a measured casing spec
MOTOR_CASING_LENGTH = 0.280  # m # TODO CONFIRM - back-calculated from 2x grain length + bulkheads, not measured
NOZZLE_EXIT_RADIUS = 0.015  # m # TODO CONFIRM - assumed ~1.6x throat radius (typical expansion ratio), not measured
PARACHUTE_DIAMETER = None  # TODO MEASURE - cd_s below is calibrated from descent rate, but physical diameter is still needed for the mission report
BULKHEAD_AVIONICS_PEZ_POSITIONS = None  # TODO MEASURE

# --------------------------------------------------------------------------
# MOTOR - Icarus I, SRAD KNSB 65:35 (Icarus Static test, 2026-05-16)
# --------------------------------------------------------------------------
# Team calls this motor "K519" (avg thrust 519.6 N in their own OpenRocket
# report). Integrating the actual thrust column in the Brasil CSV gives a
# slightly different number - see docs/model_assumptions.md "Motor designation"
# for the full K519/K526/K554/K497 mess and why we keep the K519 label anyway
# (it's the name stamped on the case and used at the static fire).
MOTOR_DESIGNATION = "K519"  # nominal, see note above
TOTAL_IMPULSE = 1871.5  # N s. trapz(Thrust vs Time, Brasil CSV, t=0..BURNOUT) - within 0.1% of team's 1873.8 Ns
BURN_TIME = 3.57  # s. Brasil CSV event BURNOUT (not 3.60 as originally briefed - 0.8% off, inside noise)
PEAK_THRUST = 566.56  # N. Brasil CSV col `Thrust (N)` max
AVG_THRUST = TOTAL_IMPULSE / BURN_TIME  # 524.2 N
ISP_EFFECTIVE = TOTAL_IMPULSE / (PROPELLANT_MASS * G0)  # ~94.6 s

GRAIN_COUNT = 2  # BATES, Icarus Static test
GRAIN_LENGTH = 0.1397  # m (5.5 in), Icarus Static test
GRAIN_OUTER_RADIUS = 0.037465  # m (2.95 in dia / 2), Icarus Static test
GRAIN_INITIAL_INNER_RADIUS = 0.009525  # m (0.75 in dia / 2, core), Icarus Static test
GRAIN_DENSITY = 1750.0  # kg/m3, back-calc: PROPELLANT_MASS / (2 * grain_volume) = 1750.2, vs KNSB theoretical ~1841 (95% cast density - plausible)
THROAT_RADIUS = 0.009525  # m (0.75 in dia), Icarus Static test
GRAIN_SEPARATION = 0.005  # m # TODO CONFIRM - typical BATES spacer, not measured

# --------------------------------------------------------------------------
# LAUNCH SITES
# --------------------------------------------------------------------------
# Sugarcane Launch Range - LASC 2026 competition site
SLR_LATITUDE = -21.908
SLR_LONGITUDE = -48.962
SLR_ELEVATION = 495.0  # m ASL. Prometeo_Launchsite_BRASIL.csv col `Altitude above sea level (m)` @ t=0
RAIL_LENGTH = 4.0  # m. FLT 4.4.1 mandatory minimum for <=1500m category, not separately confirmed by team
RAIL_INCLINATION = 80.0  # deg from horizontal (10 deg cant). Brasil CSV col `Vertical orientation (zenith)` @ t=0
RAIL_HEADING = 90.0  # deg. Brasil CSV col `Lateral orientation (azimuth)` @ t=0
SLR_WIND_SPEED = 2.594  # m/s. Brasil CSV @ t=0
SLR_WIND_DIRECTION = 90.0  # deg. Brasil CSV @ t=0
SLR_TEMPERATURE = 11.783  # deg C. Brasil CSV @ t=0
SLR_PRESSURE = 955.195  # mbar. Brasil CSV @ t=0

# Pachuca / Hidalgo - this is a DESIGN-PHASE prediction run (same generic K519
# rocket config as the Brasil case), not the as-flown 4-jul configuration.
# Elevation here (2224.9 m) matches the telemetry sheet's own reference
# altitude cell almost exactly - see docs/model_assumptions.md "Pachuca
# elevation conflict".
PACHUCA_LATITUDE = 19.967
PACHUCA_LONGITUDE = -98.856
PACHUCA_ELEVATION = 2224.9  # m ASL. Prometeo_Launchsite_Pachuca.csv col `Altitude above sea level (m)` @ t=0
PACHUCA_RAIL_INCLINATION = 89.0  # deg. same file @ t=0
PACHUCA_RAIL_HEADING = 270.0  # deg. same file @ t=0

# 4 de julio - the AS-FLOWN simulation (used for Mission44_Validation). Its
# own OpenRocket run carries a *different* motor/mass than the Brasil/Pachuca
# design-sim pair (10.96 kg vs 10.400 kg, 1732 Ns vs 1871 Ns impulse) and a
# different site elevation (2380 m vs telemetry's 2224.9 m). Both are real
# discrepancies in the delivered files, not transcription errors - documented
# in docs/model_assumptions.md, NOT silently reconciled here.
JULIO4_ELEVATION_ASFLOWN_CSV = 2380.0  # m ASL, as exported in prometeo4dejulio.csv @ t=0
JULIO4_ELEVATION_TELEMETRY = 2224.9  # m ASL, telemetry sheet cell "Altitud referencia (MSL CDMX)" (Excel mis-parsed this as a date, 2224-09-01 -> day-of-year decodes to 2224.9)
JULIO4_ELEVATION = JULIO4_ELEVATION_TELEMETRY  # used for Mission44_Validation Environment - telemetry is ground truth, not a second OR run

# --------------------------------------------------------------------------
# RECOVERY
# --------------------------------------------------------------------------
# REC 8.1.6 single deployment event, altitude-triggered (not apogee) to match
# the as-flown ESP32-S3 + BMP280 avionics logic exactly.
MAIN_DEPLOY_ALTITUDE = 1017.6  # m AGL. telemetry sheet, state transition Empuje/Ascenso -> Paracaidas/Descenso happens between pkt118 (1019.9m) and pkt119 (1017.6m)
TARGET_DESCENT_RATE = -6.0  # m/s. telemetry sheet "Vel. terminal descenso" cell. NOT directly observable in the packet stream (signal lost at t=19.4s, still in the post-deployment inflation transient) - this is the team's own post-flight estimate, kept as the calibration target because it's the only number they report for it.
AVIONICS_SAMPLING_RATE = 2.5  # Hz. packet dt ~ 0.4s in telemetry Tiempo_ms column (e.g. pkt117->118: 1718523->1718923 = 400ms)
AVIONICS_LAG = 0.4  # s, one sample period, same source

# --------------------------------------------------------------------------
# TELEMETRY - real flight, 2026-07-04, Pachuca/Hidalgo (validation targets)
# --------------------------------------------------------------------------
# Team's briefing quoted 216.7 m/s2 (22.1 g) as peak acceleration; the actual
# max in the delivered Aceleracion_ms2 column is 136.2 m/s2, at the ignition
# packet (t=0). We use the number that's actually in the file - see
# docs/validation_report.md for the full comparison against OpenRocket's
# 55.9 m/s2 prediction either way.
REAL_APOGEE_AGL = 1019.9  # m. telemetry pkt 118, Altitud_m column max
REAL_MAX_VELOCITY = 121.4  # m/s. telemetry pkt 81, Velocidad_ms column max
REAL_MAX_ACCELERATION = 136.2  # m/s2. telemetry pkt 77 (t=0, ignition), Aceleracion_ms2 column max
REAL_TERMINAL_DESCENT = -6.0  # m/s. telemetry sheet summary cell (see TARGET_DESCENT_RATE note above)
REAL_SIGNAL_LOSS_T = 19.4  # s post-ignition. telemetry last coherent packet (pkt126)
REAL_SIGNAL_LOSS_ALT = 992.6  # m AGL. same packet, Altitud_m column
IGNITION_TIEMPO_MS = 1702723  # telemetry Tiempo_ms value at the Estado_Nombre="Motor ON / Ascenso" transition, t=0 reference for all REAL_* above
