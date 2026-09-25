# RCSM Ed.7 Rev.1 (March 2026) - rules that drive the simulation/compliance code

Source: `Rocket Challenge Standards Manual E07 R01.pdf` (effective 22 March
2026), provided by the team 2026-09-16. This file only pulls the provisions
that `common/rules.py` needs to check automatically or that change vehicle
configuration (rail length, recovery topology, payload mass). It is not a
full manual summary - read the PDF itself for anything not listed here.

## Mission categories (RKT 1.1.1, Table 1)

| Category | Propulsion | Target apogee | Min payload mass |
|---|---|---|---|
| 0.5 km solid | Solid | 500 m | 400 g |
| 1 km solid | Solid | 1000 m | 800 g |
| 3 km solid | Solid | 3000 m | 4000 g |
| Hybrid/Liquid, low | Hybrid/Liquid | (team target, uses 0.5km band) | 0 g |
| Hybrid/Liquid, mid | Hybrid/Liquid | (team target, uses 1km band) | 400 g |
| Hybrid/Liquid, high | Hybrid/Liquid | (team target, uses 3km band) | 2000 g |

Payload weigh-in at LRR accepts up to 5% under the minimum (RKT 1.1.2 note).

## Rail length (FLT 4.4.1 / 4.4.2)

- Target apogee <=1500 m: 4 m rail (LASC-provided, 40x40mm aluminum)
- Target apogee >1500 m: 6 m rail (same cross-section)

So both 3km vehicles (solid and hybrid) need the 6m rail case, unlike
Mission44/PROMETEO's 4m.

## Recovery topology (REC 8.1.1-8.1.4)

- Target apogee >1500 m AGL: **mandatory dual-event** recovery.
  - Initial deployment (drogue or reefed main): at/near apogee, reduces
    descent rate to roughly 20-45 m/s (stabilizes attitude, prevents
    tumbling, without excessive wind drift).
  - Main deployment: no higher than 500 m AGL.
- Target apogee <=1500 m AGL: exempt, single deployment event allowed
  (this is what PROMETEO/vehicle_1km_solid uses).

Both 3km vehicles need a two-stage parachute system in rocketpy
(`rocket.add_parachute("Drogue", ...)` + `rocket.add_parachute("Main", ...)`
with separate triggers), not the single altitude-triggered main PROMETEO
used.

## Flight / stability (FLT 4.3.4 - 4.3.6) - same for every category

- FLT 4.3.4: rail departure velocity >=30 m/s (or documented analysis if
  >15 m/s).
- FLT 4.3.5: static stability margin >=1.5 cal for the whole ascent.
- FLT 4.3.6: not over-stable - static margin <4 cal, dynamic margin <6 cal.

## Propulsion (PRS 5.1.3 / 5.1.4) - same for every category

- PRS 5.1.3: SRAD propulsion total impulse capped at 40,960 N s (bounds
  motor class selection for the 3km vehicles - PROMETEO's K519 was 1874 Ns,
  nowhere near the cap).
- PRS 5.1.4: thrust-to-weight >= 5:1, using max(initial thrust, average
  thrust) / takeoff weight (vehicle + payload).

## Structure (STR 6.3.2, 6.4.2) - same for every category

- STR 6.3.2: fin flutter velocity >= 1.5x max expected velocity.
- STR 6.4.2: exactly 2 rail buttons; aft-most one supports full loaded
  weight vertically.

## Hybrid/liquid specific (PRS 5.4.x) - not simulation inputs, but shape the
## vehicle_3km_hybrid design and its docs

- PRS 5.4.1: must have remote venting/offloading capability for abort.
- PRS 5.4.5: fill monitoring system required (load cell recommended).
- PRS 5.2.1/5.2.2: N2O + paraffin is an explicitly allowed combination;
  LOx/GOx and peroxide are prohibited.
