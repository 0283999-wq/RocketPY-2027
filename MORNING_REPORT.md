# Morning report - autonomous overnight run, 2026-09-25

## Status by phase

| Phase | Status | One line |
|---|---|---|
| 0 - repo restructure | **Done** | `common/` -> `stella_flight/`, design_search.py removed |
| 1 - `.ork`/`.eng` readers + translation | **Done** | Real `.ork` acceptance test passing (CP/diameter <0.5% err); dry-mass gap (19%) found, explained, not hidden |
| 2 - V1/V2 validation | **Done, both PROVISIONAL** | V1 +10.2% err, V2 +5.3% err (see below) - honest results, not tuned |
| 3 - NiceGUI app + `start.bat` | **Done** | Upload -> table -> Simulate -> numbers/plots/CSV; headless-tested, **not** browser-tested (no display here) |
| 5 - Ballistic + Nominal export | **Done** | Self-contained `.py` files proven in a genuinely clean venv, 0.003% match |
| 4 - Monte Carlo + landing ellipse | **Not started** | Your lowest priority; ran out of tonight's budget after 1-3 |
| 5 (rest) - drogue-only/main-at-apogee, PDF/DOCX report, `.zip` packaging | **Not started** | Same |
| 6 - weathercocking, drag comparison | **Not started** | Needs Phase 4's Monte Carlo first |

Full detail, every approximation and its source: `PROGRESS.md`. Every commit tonight: `CHANGELOG.md`.

## Validation numbers (V1/V2 - the two that matter most)

| | Predicted | Flight (real) | Error | Inputs |
|---|---|---|---|---|
| **V1** (2026-07-04) | 1124.1 m | 1019.9 m | **+10.2%** | Mass 10.96 kg / motor 4.883 kg (as-flown, `verified_constants.json`); dry CG **approximated** from the Brasil config (no July4-specific CG exists anywhere in the files); OpenRocket-recorded wind/temp/pressure, not real weather |
| **V2** (LASC) | 1196.9 m | 1137.0 m | **+5.3%** (just outside ±5%) | Mass 10.370 kg (measured, your instruction); site/rail from the `.ork`'s own "brasil 2026" sim; motor mass reused from Brasil config (no LASC-specific figure exists); OpenRocket-recorded conditions, not real Iacanga weather |

Neither was tuned to pass. V2 is close - real weather + a real LASC motor-mass figure could plausibly close most of the gap.

## What you need to do (PowerShell)

```powershell
cd C:\path\to\rocketpy-2027
git pull origin main
.\start.bat
```
First run installs everything (~2-3 min); after that it just opens the app. Drag in `PrometeoLasc2026.ork` + `Icarus_I_K519.eng`, click Load, **enter 5.6622 in "dry mass override" and 0.6279 in "dry CG override"** (see below for why), click Simulate.

## What I need from you

1. **Set a whole-rocket `overridemass` + `overridecg` in OpenRocket** on `PrometeoLasc2026.ork`, from your LRR scale measurement - right now only the Fuselage shell is overridden, so the app's automatic mass estimate is 19% low and marginally unstable without the manual override above.
2. **Confirm the app's browser UI actually renders and works** - I could not test this myself (no display in this container), only the underlying logic.
3. **Real Iacanga flight-day weather** for V2 (I used OpenRocket-recorded conditions, not live data - your instructions said you'd pull this tomorrow via Open-Meteo/GFS).
4. **Exact LASC flight date/time** (you said pending, 2026-09-03 to 09-05 ~12:00 local).
5. **A LASC-specific motor mass**, if one exists separately from the 10.370 kg total - would help close V2's gap.
6. **Major Tom's `.ork`** + both `.eng` files (K503, M1739-P) - not touched tonight.
7. Decide priority: should I pick up Phase 4 (Monte Carlo) next, or something else first?
