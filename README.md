# Beyond UP / Stella Ignis - 2027 Program

RocketPy-only design and simulation for three vehicles targeting LASC 2027:

- `vehicles/vehicle_1km_solid/` - 1 km, solid motor
- `vehicles/vehicle_3km_solid/` - 3 km, solid motor
- `vehicles/vehicle_3km_hybrid/` - 3 km, N2O/paraffin hybrid

No OpenRocket in this program - geometry is designed and iterated directly
in RocketPy via `common/design_search.py` parametric sweeps, using
`common/rules.py` to check RCSM Ed.7 Rev.1 compliance (rail exit velocity,
stability margin, thrust-to-weight, recovery topology, payload mass) as each
candidate is evaluated. See `docs/rcsm_reference.md` for the rule text this
was built from, and `RocketPY/` (the PROMETEO Mission 44 / LASC 2026 repo)
for the reference implementation this program's structure is based on.

## Setup

```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

## Status

Scaffolding only - `common/` (rules, environment, parametric design search)
is built and smoke-tested. No vehicle has a config yet; that starts once
motor candidates and target diameter are picked per vehicle.
