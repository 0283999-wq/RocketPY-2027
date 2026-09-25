# Morning report - autonomous overnight run, 2026-09-26

Follow-up to your review: item 0 (upload bug) fixed, item 1 (code-to-code
bug hunt) investigated deeply, item 2 (UI redesign) built, item 3 (all
remaining phases) built. Everything below is genuinely tested against
your real `PrometeoLasc2026.ork` + `Icarus_I_K519.eng` - not just written.

## Status by item/phase

| # | Item | Status | One line |
|---|---|---|---|
| 0 | Upload bug | **Fixed** | Real cause: NiceGUI 3.17.1's `e.file` API, not `e.content`; handlers needed to be `async`. Permanent Playwright test added, runs real Chromium. |
| 1 | Code-to-code vs OpenRocket | **Investigated, not resolved** | Confirmed real (+10.2%/+9.4%, not weather - see below). Reference area/Cd/impulse/density all ruled out with hard numbers. Root cause NOT isolated - see PROGRESS.md. |
| 2 | UI redesign | **Done** | Gold/wine theme, sidebar, all 8 pages, dark mode, 8 real screenshots in `docs/screenshots/`. |
| 3 | Phase 4 - Monte Carlo | **Done** | Found & fixed 3 real bugs in rocketpy's own Stochastic classes (see below). N=20 works, 0 excluded, sane 90% interval. |
| 3 | Phase 5 - 4 RCSM cases | **Done** | Ballistic/Nominal/Drogue-only/Main-at-apogee all build; single-deploy warns cleanly (your rule), doesn't crash. |
| 3 | Phase 5 - report + LASC zip | **Done** | PDF+DOCX (validation section first, correct wording), zip proven runnable in a clean venv. |
| 3 | Phase 6 - weathercocking + drag comparison | **Done** | Found & fixed a 4th Stochastic-class bug (seeding). Common-random-numbers comparison verified exact (0.0 diff on identical curves). |
| 3 | Major Tom | **Blocked** | `.ork` still not in the repo - nothing to test against. |
| - | Monte Carlo background/cancel, Leaflet map | **Scope-cut** | Documented in PROGRESS.md, not silently dropped. |

Full detail on everything: `PROGRESS.md`. Every commit: `CHANGELOG.md`.

## Validation numbers

| | Predicted | Flight (real) | Error |
|---|---|---|---|
| **V1** (2026-07-04) | 1124.1 m | 1019.9 m | **+10.2%** |
| **V2** (LASC) | 1196.9 m | 1137.0 m | **+5.3%** |

Unchanged from last night (didn't re-tune). New tonight: a **code-to-code
check against OpenRocket's own two CSV sims**, using its exact inputs (no
weather uncertainty at all): Brasil-config **+10.17%**, July4 **+9.43%**.
July4's gap is explained (wrong motor file used - already documented in
`config.py`). Brasil's is NOT explained - ruled out with hard numbers:
reference area (exact match), Cd at Mach 0.3 (<0.1% off both curves),
motor impulse/burn time (exact), atmosphere density/gravity (exact). One
open lead: rail-exit speed is actually *slower* in our sim (15.6 vs 16.8
m/s), which rules out the obvious "too little drag" theory. Not tuned.

## 4 real rocketpy==1.13.0 bugs found and worked around tonight

All in rocketpy's own Stochastic subsystem (it ships with a "still under
testing" warning - these are real, not usage mistakes):
1. `MonteCarlo.simulate()`'s default export list references a Flight
   attribute that crashes on any unstable sample.
2. `StochasticRocket.create_object()` silently drops an overridden CG
   unless re-passed explicitly.
3. `StochasticRocket.add_nose()`/`add_trapezoidal_fins()` crash on a
   plain surface (internal kwarg mismatch).
4. None of the 4 Stochastic classes forward `seed=` to their base class,
   and setting the RNG after construction doesn't work either (already
   bound). Fixed with a narrowly-scoped monkeypatch, verified exact.

#2+#3 combined were the nastiest: every Monte Carlo sample had literally
no aerosurfaces, producing a consistent ~-8.5 cal "instability" with
nothing to do with the actual uncertainties - easy to misdiagnose.

## What you need to do (PowerShell)

```powershell
cd C:\path\to\rocketpy-2027
git pull origin main
.\start.bat
```

First run installs everything (~3-5 min now, more dependencies than last
night - nicegui, playwright, python-docx, reportlab). Drag in
`PrometeoLasc2026.ork` + `Icarus_I_K519.eng` on the **Simulate** page,
click Load, open **Advanced**, enter `5.6622` for dry mass and `0.6279`
for dry CG, click Simulate. Then look at the sidebar - Rocket, Monte
Carlo, RCSM Cases, Analysis, History, Exports, Validation all work off
that same loaded rocket.

## What I need from you

1. **Set a whole-rocket `overridemass`+`overridecg` in OpenRocket** on
   `PrometeoLasc2026.ork` - the one input the app can't substitute for.
2. **Look at the actual app yourself** - I tested with an automated
   browser (screenshots in `docs/screenshots/`), but nothing replaces you
   clicking around with a real mouse.
3. **Major Tom's `.ork`** (+ `.eng` files) - still not in the repo;
   nothing to test the app's second vehicle against.
4. **Real Iacanga weather** for V2, and the **exact LASC date/time** -
   same ask as last night, still pending.
5. **Logo files** (`logo_gold.png`/`logo_wine.png` in
   `bup_rocketpy/gui/assets/`) whenever the rebrand assets exist - the
   header currently shows a plain text wordmark.
6. **Decide**: is the +10% OpenRocket gap (item 1) worth more investigation
   time before trusting any of this app's absolute numbers, or is relative
   comparison (Monte Carlo, drag comparison, weathercocking) good enough
   for now while that's still open?
