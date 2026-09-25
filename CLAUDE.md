# stella-flight: Flight simulation and analysis for Stella Ignis (RocketPy)

> Instructions for Claude Code. Keep this file at the repo root as `CLAUDE.md` so every
> session reads it automatically and the context never has to be re-explained.
> Checked on 2026-09-24 against the project's real files (see §3 and §4).
> **This file overrides any earlier plan for this repo.**

---

## 0. The user

**Diego** studies engineering at Universidad Panamericana and is on the **Stella Ignis**
rocketry team. He designs rockets in OpenRocket through its GUI and **does not
program**, although he is willing to learn what he needs to win.

**The rule that overrides everything:** whatever you build must be usable by **loading
files and clicking buttons**. If the only way to use something is by editing Python, it
isn't finished. When Diego does have to touch code or the terminal, give him the exact
command and a one-line explanation of what it does.

**Language: the whole project is in English.** That covers the UI, code, comments,
docs, commit messages and the report. Diego may write to you in Spanish; answer him
in whatever language he uses, but everything that goes into the repo is in English.

**Diego's machine runs Windows (x64).** Every README command is PowerShell, and there
must be a `start.bat` that he can double-click.

**Save tokens:** Diego is on limited credits. Don't re-read files you have already read,
don't paste long outputs, and keep commits small and frequent. If you are missing data
or a file, **ask for it in one line** rather than inventing it or working around it.

---

## 1. What this is

A **flight simulation and analysis application** built on RocketPy (**version ≥ 1.13**;
the RCSM requires ≥ 1.1.0 and Python ≥ 3.9).

```
OpenRocket → .ork  (+ exported simulation CSV, see §4.2)
openMotor  → .eng
        ↓  THIS APP
plots · Monte Carlo · landing ellipse · 4 RCSM cases · report · .py scripts for LASC
```

**It is NOT a design tool.** Don't duplicate OpenRocket, and don't try to beat its
coefficients: the app **flies** a given design. That means no "design search", no
choosing motors or diameters, and no parametric vehicle configs. Diego designs in
OpenRocket and this app reads the result.

**Library structure:** an importable package `stella_flight/` (core, no UI) with
`stella_flight/gui/` (NiceGUI) as a separate layer. Diego's other repo, Altum, also
uses NiceGUI and may import this later. **Don't integrate with Altum now.**

---

## 2. Goals

1. Replace OpenRocket as Diego's **simulation** tool. OpenRocket stays for design only.
2. Meet the simulation deliverables in **RCSM Ed. 7 Rev. 1, section 10** (see §5).
3. Compete for the **RocketPy Computational Simulation award** and the **flight
   dynamics** award. What wins them is a **rigorous, validated, well-documented study**,
   not a pretty app.

---

## 3. Verified facts (don't contradict these; if you find contrary evidence, flag it)

### 3.1 The PROMETEO validation: how to present it so a judge can't knock it down

- At LASC 2026 (Iacanga, Brazil), **LASC officials** re-simulated PROMETEO on site with
  the data measured at the Launch Readiness Review (CRS 10.2.1). They issued a
  **verified target apogee of 1,138 m**. The flight reached **1,137 m** (SRAD telemetry),
  an error of −1 m (−0.09 %).
- **The team did not make that prediction**, and **we don't have the exact inputs the
  officials used.** Never write "our RocketPy predicted 1,138". The correct wording is:
  *"the official on-site simulation (RocketPy, CRS 10.2.1) predicted 1,138 m; the flight
  reached 1,137 m; our independent replication of the same vehicle gives X m."*
- The report the team submitted in August simulated **1,052.1 m** at 10.520 kg. The
  vehicle that flew weighed **10.370 kg** (scale), after mass reductions made in Brazil.

### 3.2 PROMETEO flight data

| | 2026-06-06 | 2026-07-04 | LASC 2026 |
|---|---|---|---|
| Site | Pachuca | Pachuca, 19.967 N, −98.856 E, **2,380 m MSL** | Iacanga SP, 21.900 S, 48.960 W, **490 m MSL** |
| Rail | — | 3.0 m | 4.0 m |
| Actual apogee AGL | 860.9 m | **1,019.9 m** | **1,137 m** |
| Prediction | none valid | 1,027.2 m (OpenRocket, −0.71 %) | 1,138 m (official LASC) |
| Descent rate | 22.0 m/s (timer-triggered deployment, faulty) | 6.0 m/s | **5.5 m/s** (5.52 predicted) |
| Telemetry available | full PDF | packet-by-packet table in `PROMETEO_Informe_Maestro_2026.md` §8.2 (ask Diego to export it) | **only the 1,137 number** |

- **The 2026-06-06 flight is NOT valid for trajectory validation** (timer-triggered
  deployment and a different configuration). Don't use it for validation.
- **The 2026-07-04 flight is the best profile validation case**: it has altitude
  vs. time. Use it for the full curve (residual RMS; OpenRocket got 24.4 m).
- Official motor: **Icarus I / K503**, KNSB 65:35, 2 BATES grains, **1,855.9 N·s**,
  514.1 N average thrust, 3.61 s burn. Older documents call it K519, K554, K526 or K497:
  **these are all the same motor under wrong names**.
- The old repo `0283999-wq/RocketPy-Prometeo-Mission-44` has a `thrust_curve.csv`
  (≈ 1,871 N·s, labelled "K519"). Use it **only as a fallback** if the `.eng` doesn't
  arrive, and flag it as approximate.
- Diego has a local `RocketPY/` folder with `Mission44_Nominal_RocketPy_v1.0.py`, which
  is probably the LASC submission. It should be committed under
  `reference/prometeo_mission44/`. When it is there, inventory its inputs (mass, Cd
  source, rail, atmosphere, `.eng`) before building the validation.

### 3.3 Why the old repo is NOT a good base (don't copy it)

It uses a constant Cd of 0.5, a "calibrated" CG instead of a measured one, a standard
atmosphere with no wind, estimated inertias, and hand-typed positions. That is exactly
what this app is meant to fix. You may reuse its **documented-uncertainty ideas** from
the Monte Carlo (`monte_carlo_analysis.py`).

### 3.4 Major Tom (3 km solid, active design): two conflicting versions

| | Diego's brief | Design log, 2026-09-22 |
|---|---|---|
| Length | 190 cm | 188 cm |
| Mass without/with motor | 13.354 / 27.012 kg | 12.21 / 25.87 kg |
| OpenRocket apogee | 2,635 m | 2,779 m |
| Stability @ M 0.3 | 2.1 cal (CG 116, CP 145) | 1.69 cal (CG 118, CP 142) |

Both versions agree on: Ø 14 cm, motor **M1739-P** (SRAD, KNSB), site 490 m MSL,
3,000 m target. **The `.ork` Diego loads is the source of truth**: the app shows what
it reads, not these tables. The design log also says the `.ork` has **only one
parachute** and no drogue (REC 8.1.1). If that's still the case, the app must **warn
about it** when running the RCSM cases.

---

## 4. Input files and their pitfalls

### 4.1 What we have and what's missing

- **There are no `.ork` or `.eng` files in the project yet.** Ask Diego for them at the
  start of Phase 1: the PROMETEO `.ork` in its **LASC configuration** (10.370 kg), the
  Major Tom `.ork`, and the openMotor `.eng` files for the K503 and the M1739-P.
- We do have 3 **OpenRocket simulation CSV exports** (these are not telemetry):
  `prometeo4dejulio.csv` (Sim 15, Pachuca), `Prometeo Launchsite Pachuca.csv` and
  `Prometeo Launchsite BRASIL.csv`. They have 58 columns (Mach, Drag coefficient, CP,
  CG, Stability, Thrust, Mass…), and events appear as `# Event X occurred at t=…` lines.
- Until Diego's files arrive, test the reader with OpenRocket's example `.ork` files
  (`github.com/openrocket/openrocket`, examples folder). GitHub is reachable from the cloud.

### 4.2 Drag: the most important pitfall

**RocketPy does NOT compute Cd from geometry.** It only computes lift and CP
(Barrowman). Cd has to be supplied as `power_off_drag` / `power_on_drag` curves vs. Mach,
which is why the old repo had a constant Cd of 0.5. Sources, in order of preference:

1. **Simulation data stored inside the `.ork`.** OpenRocket can save it: look for the
   `<databranch>` block with Mach and Drag coefficient. Use it when present.
2. **An exported OpenRocket CSV**, like the 3 above. Diego drags it in as an optional
   third file. Extract Cd vs. Mach by splitting the powered phase (Thrust > 0) from the
   coast phase, averaging over Mach bins, and **dropping points below Mach ≈ 0.05**
   (start-up noise).
3. **RocketSerializer** (`rocketserializer`, RocketPy's official tool, which LASC uses
   according to **CRS 10.1.5**). It needs Java and the OpenRocket jar. Keep it as an
   **optional cross-check** and detect whether Java is present. It matters for the award,
   because it shows our translation matches the judges'.
4. With no source at all: a constant, **editable** Cd with a **red warning** and low
   confidence.

The UI must always say **where the Cd curve came from**.

### 4.3 Other known pitfalls

- **Density in OpenRocket CSVs** is rounded to 0.001 g/cm³. That gives 1.0 kg/m³ and a
  false Max-Q of 12.06 kPa when the real value is 13.77. **Never use that column to
  compute dynamic pressure**; use RocketPy's atmosphere instead.
- **The `.ork` doesn't store the thrust curve or the motor mass**, so the `.eng` is
  mandatory (CRS 10.1.9 also requires it for SRAD motors). Take total and dry mass from
  the `.eng` header.
- **OpenRocket mass and CG overrides** (`overridemass`, `overridecg`, and whether
  "override subcomponents" is on) must be honored exactly, or mass and CG won't match.
- **Coordinates:** OpenRocket measures from the nose tip. RocketPy uses
  `coordinate_system_orientation="nose_to_tail"`. Do the conversion in one place only.
- **Inertias:** the `.ork` doesn't store them directly. Compute them by summing
  components (cylinders, cones, point masses) and **label them "approximate"**.

---

## 5. What the RCSM requires (verified text)

- **CRS 10.1.3:** the submission is a `.zip` with a **runnable `.py` or `.ipynb`**, or an `.ork`.
- **CRS 10.1.5:** it only counts if a RocketPy team member or LASC staff can run it on
  their own machine.
- **CRS 10.1.6:** file name `Mission[ID]_[Case]_RocketPy_v[N]`. PROMETEO was Mission 44.
  Major Tom's ID is still pending, so make it an editable field.
- **CRS 10.1.8:** exact masses, sizes and positions.
- **CRS 10.1.9:** `.eng` for SRAD motors; parachutes with trigger, phase, size and Cd;
  control algorithms if there is an airbrake. Major Tom has an **airbrake plate**, so
  ask Diego whether it is active.
- **CRS 10.1.10–10.1.13:** **ballistic and nominal** for everyone. **Drogue-only and
  main-at-apogee** are mandatory for 3 km vehicles with drogue + main.
- **CRS 10.1.14:** the RocketPy award requires **nominal and ballistic**.
- **REC 8.1.1–8.1.4 (3 km):** dual deployment; drogue descent at 20–45 m/s; main at
  ≤ 500 m AGL and < 10 m/s. **FLT 4.3.4:** rail exit ≥ 30 m/s. **FLT 4.3.5/4.3.6:**
  static margin of 1.5–4 cal throughout the ascent. **STR 6.3.2:** flutter ≥ 1.5 × Vmax.

**Design consequence:** besides the report, the app **exports a self-contained `.py`
per case**, named per CRS 10.1.6, that anyone can run with just `pip install rocketpy`
and without our library. That is the deliverable LASC actually evaluates. Add an
automated test that runs each exported `.py` in a clean environment and compares its
apogee to the app's.

---

## 6. Phases (one commit per phase, each with a `CHANGELOG.md` entry and a plain-language `NOTES_FOR_DIEGO.md` entry)

### Phase 0: realign the repo (do this first)

The repo currently has `common/rules.py`, `common/design_search.py` and
`common/environment.py` from an earlier plan. `design_search.py` contradicts §1.
Report in 3 lines what each file does and what can move into `stella_flight/` (the
RCSM rules checker likely can). Then propose the restructure and wait for Diego's OK
before deleting anything.

### Phase 1: read the files

- A **pure-Python** `.ork` reader (ZIP + XML; some `.ork` files are uncompressed XML,
  so support both). Extract: nose cone (shape, length, shape parameter), body tubes,
  transitions and boat tails, fins (count, chords, span, sweep, thickness, cant,
  position, material, cross-section), point masses and overrides, parachutes and
  streamers (Cd, diameter, deploy event, altitude, delay), rail buttons, launch rail
  (length, angle, direction), and the launch site from the stored simulation.
- A `.eng` (RASP) reader and a thrust `.csv` reader.
- Translation into `Environment`, `SolidMotor`, `Rocket` and `Flight`.
- An **"imported / approximated / ignored" table** listing each component by name, plus
  a **confirmation step before simulating**. Nothing is ever half-imported silently.
- **Acceptance:** mass, CG and CP of the PROMETEO `.ork` within **1 %** of what
  OpenRocket shows. Ask Diego for a screenshot of the OpenRocket panel with those three
  values, or take them from the first row of the exported CSV (CG, CP and Mass at t = 0).

### Phase 2: simulation and validation

- **Selectable** atmosphere: standard, **Open-Meteo** (forecast and historical
  pressure-level data, no account needed, built as a `custom_atmosphere`), RocketPy's
  native GFS, a Wyoming sounding, or a user file. Downloads happen **on Diego's
  machine** (the cloud can't reach those servers), so test with mocked data and cache
  every downloaded profile next to its result for reproducibility.
- **Validation as a permanent automated test (pytest):**
  - **V1, 2026-07-04 (profile):** apogee vs. **1,019.9 m**, plus altitude-residual RMS
    against the telemetry packet table.
  - **V2, LASC (apogee):** the LASC `.ork` + 10.370 kg + historical Iacanga weather on
    flight day, vs. **1,137 m**. Ask Diego for the date, launch time (≈ 12:00 local) and
    rail angle.
  - Tolerance **±5 %**. **If it fails, stop and report it** with a breakdown of causes
    (Cd, mass, thrust, wind). Don't tune anything by hand to make it pass.
  - Until both pass, **every result shows "PROVISIONAL" on screen**.
- Plots vs. time: altitude, velocity, Mach, acceleration, static margin and angle of
  attack; plus the 3D trajectory.

### Phase 3: user interface (NiceGUI, English)

Drag in `.ork` + `.eng` (+ optional OpenRocket CSV) → imported-data table →
**Simulate** button, with a progress bar and the current step's name → big numbers
(apogee, Vmax, max Mach, max acceleration, rail exit velocity, flight time, minimum
static margin) → plots → export to CSV and PNG. `start.bat` creates the virtual
environment on first run and opens the browser.

### Phase 4: Monte Carlo and landing ellipse

- Use RocketPy's `StochasticEnvironment`, `StochasticSolidMotor`, `StochasticRocket`,
  `StochasticFlight` and `MonteCarlo`.
- Vary: wind (magnitude and direction, or forecast ensemble members), dry mass, total
  impulse, Cd factor, rail inclination and heading, deployment delays, and parachute Cd·S.
- **Every uncertainty is editable and shows its source.** If it has no source, label it
  "no source, low confidence".
- Outputs: an apogee histogram with the mean and a **90 % interval** ("3,000 ± 120 m at
  90 % confidence"), and **1σ/2σ/3σ landing ellipses** on a map of the site (Leaflet in
  NiceGUI), for both drogue and main.
- Runs **in the background**, with progress, **cancellable**, saving partial results.
  Default N = 200, editable.

### Phase 5: RCSM cases and report

- Four buttons: **Ballistic, Nominal, Drogue-only and Main-at-apogee**. If the `.ork` has
  no drogue, the last two say so clearly instead of crashing.
- Automatic compliance check against the rules in §5 (rail exit, static margin, drogue
  and main velocities, flutter when data is available).
- **Report** in PDF and DOCX: every case, the plots, the Monte Carlo, the ellipse, the
  compliance check, the assumptions with their sources, and **the validation section
  up front** (V1 + V2, worded as in §3.1).
- **LASC `.zip` package:** the per-case `.py` files named per CRS 10.1.6, plus the
  `.eng`, `.ork` and Cd curves.

### Phase 6: questions only RocketPy can answer

1. **Weathercocking:** sweep apogee vs. static margin, with the site's real wind and a
   Monte Carlo at each point. Move the margin by changing a ballast mass in the nose cone,
   which is how Diego would do it on the real rocket. Search for the optimum **within
   1.5–4 cal** (FLT 4.3.5). It will probably land on the lower bound, and the app must
   say so.
2. **Drag comparison:** load two `power_off_drag` / `power_on_drag` pairs (CSV or
   OpenRocket export) and run each one's Monte Carlo **with the same random seeds**
   (common random numbers). Report the apogee difference with its interval. Example
   answer: "switching the nose cone gives +40 m [+25, +55] at 90 %, so the difference is real."

---

## 7. Rules

1. **Always a UI.**
2. **Never invent data.** Every coefficient and uncertainty carries its source. If there
   is none, it becomes an editable field with a warning and low confidence.
3. **Validate before trusting**, and show "PROVISIONAL" until V1 and V2 pass.
4. An importable library, with the UI kept separate.
5. **English everywhere in the repo.** **SI units in the core**; convert only for display.
6. One commit per phase, with a CHANGELOG entry and a note for Diego.
7. Developed in the cloud, run on Diego's Windows machine. The README gives the exact
   commands (`git pull`, then double-click `start.bat`).
8. Pin versions in `requirements.txt` (rocketpy, nicegui, etc.) so what passed the tests
   in the cloud is exactly what Diego runs.
