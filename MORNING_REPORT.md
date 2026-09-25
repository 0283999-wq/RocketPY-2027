# Morning report - second overnight review, 2026-09-25 -> 2026-09-26

You tested the app yourself and it did not work for a real user - tests
passing was not the same as the app working. This is a direct,
in-progress response to that review, done in budget mode (worked through
sections in priority order, committed + pushed after each one, ran the
full test suite once per section rather than per edit). **This report is
being written partway through, per your own instruction, right after
Section 4 + the KPI/recovery part of Section 5 landed** - I'm continuing
past this point; treat this as a safe checkpoint, not a stopping point.

## Status by section

| # | Section | Status | One line |
|---|---|---|---|
| 0 | Rename (Stella Ignis -> Beyond UP) | **Done** | Team + package (`bup_rocketpy`) renamed everywhere; CLAUDE.md's "Definition of done" section added. |
| 1 | Crashes a-f | **Done** | All 6 fixed with real root causes, not workarounds - see below. |
| 2 | Physically impossible numbers a-c | **Done** | Found the actual bug behind the 394g spike and the 0.08 cal margin - both were the SAME root cause. |
| 3 | The +10% mystery | **Done (partially resolved)** | Found the real reason your app and the test harness disagreed: two different code paths. Fixed 3 real bugs while unifying them. Brasil-config code-to-code now passes at -1.45% (was +10.17%). July4/V2 still open - see below. |
| 4 | Tests that match reality | **Done** | New e2e tests using your actual default (no-override) path, a corrupt-history scenario, and a second-`.ork` swap test - found and fixed one more real bug this way. `start.bat` now prefers Python 3.12. |
| 5a | KPIs + recovery panel | **Done** | Time to apogee, Max-Q, ground-hit velocity, landing distance, and the full recovery panel (diameter/area/Cd/CdS/hand-calc vs. sim) you asked LASC officials wanted. |
| 5b | Remaining plots + rocket info | Not started yet | Continuing after this report. |
| 6 | The 4 "rocketpy bugs" repro scripts | Not started yet | Continuing after this report. |
| 7 | MC background/cancel, Leaflet map | **Background+cancel done** (landed inside Section 1's crash-b fix) | Leaflet map not started. |

## The most important fixes, in plain language

**Section 1 (crashes):**
- History page 500 error: a numpy `bool`/`float` type json.dump refuses, plus a truncated file from a killed process could poison the page forever. Fixed with a proper encoder and atomic writes; a corrupt file now shows a warning instead of taking the page down.
- "Connection lost" during Simulate: the simulation was blocking the app's single event loop. Now runs in a background thread with a progress bar. **Also found a second bug this exposed**: the app's own startup function was accidentally named the same as the background-worker module it imported, silently breaking every background simulation - fixed and explained in the code so it can't recur.
- Apogee -495m / margin -900 cal with no manual override: the "no override" path was silently passing 0/empty values instead of actually using no override. Fixed with an explicit "use manual override" checkbox (unchecked by default) - the app now correctly falls back to your `.ork`'s own component masses.
- Monte Carlo/RCSM/Analysis/Exports refusing to work without manually typed mass/CG: fixed - they now work off whatever Simulate actually used, override or not.
- Rocket page showing the wrong rocket's numbers: this was your browser caching an old picture under the same filename, not a data bug. Fixed by giving every regenerated plot a unique name. (Found a second, subtler version of this same bug in Section 4: after loading a NEW `.ork`, the page kept showing the PREVIOUS rocket's dry CG/margin numbers next to the new geometry until Simulate was re-run - fixed too.)
- rocketpy's "divide by zero" warning: some `.eng`/CSV files had duplicate time or Mach values, which is mathematically undefined for the interpolation rocketpy does. Now detected and fixed automatically, with a note in the import table.

**Section 2 (impossible numbers) - this was the big one:**
Your 394g spike and the 0.08 cal margin were **the same bug**. PROMETEO's real `.ork` has its parachute set to `deployevent="never"` - OpenRocket's way of saying "this isn't automatically triggered in my own model" (normal for a real altimeter system OpenRocket doesn't simulate). The old code read that as "deploy at 200m altitude" instead of recognizing it needs to fall back to apogee (which is how PROMETEO actually flies, confirmed by your own telemetry) - so the rocket free-fell from apogee to ~120 m/s before "deploying," and that shock swallowed every acceleration/margin number downstream. Fixed, verified against your real documented ~5.5 m/s descent rate (matches almost exactly now), and margin is now computed only for the ascent (rail exit to apogee), not the meaningless post-deployment phase. Also added a color-coded automatic sanity-check panel (thrust-to-weight, boost acceleration, delta-v, deployment speed, descent rate) that flags anything implausible instead of silently showing it.

**Section 3 (the +10% mystery) - solved the actual disagreement, found 3 real bugs:**
Your diagnosis was exactly right: the app and my test harness were two different code paths. The tests built their own rocket by hand from `config.py`; the app used `bup_rocketpy/translate.py`. Rewrote both tests to call the exact same functions the app uses. While doing that, found and fixed:
1. The motor's propellant mass was **18.8% too low** - a hardcoded density constant, not solved from your `.eng` file's own declared mass. This alone was worth about half the gap.
2. Wind was read from your `.ork` but never actually applied - and my first fix attempt silently did nothing, because of a real rocketpy quirk (it zeroes wind internally for the "standard atmosphere" model no matter what you pass it). Found the workaround.
3. **The LASC submission-script generator (`case_export.py`) had its own separate, stale copy of both bugs above** - meaning every exported competition script would have shipped with them even after they were fixed in the app. Fixed and now verified to match the app's own number to 0.003%.

Result: reproducing OpenRocket's own simulation with its exact inputs (no weather guessing at all) now matches to **-1.45%**, comfortably inside the 2% target. July4 and the LASC-vs-real-telemetry comparison (V2) are still open - full breakdown and next leads in `PROGRESS.md` "Item 3." Not tuned to force any of this - every number is what the code actually produces.

## Validation numbers (right now)

| | Predicted | Target | Error |
|---|---|---|---|
| Code-to-code vs. OpenRocket (Brasil config, no weather uncertainty) | 1066.0 m | 1081.7 m (OpenRocket) | **-1.45% (PASS)** |
| Code-to-code vs. OpenRocket (July4 config) | 1136.5 m | 1027.2 m (OpenRocket) | +10.64% (open) |
| V1 (2026-07-04, real flight) | 1136.5 m | 1019.9 m (telemetry) | +11.4% (open) |
| V2 (LASC, real flight) | 1071.1 m | 1137.0 m (telemetry) | -5.8% (open, was +5.3% before tonight's wind fix - see PROGRESS.md for why this is informative, not a regression) |

## What you need to do (PowerShell)

```powershell
cd C:\path\to\rocketpy-2027
git pull origin main
.\start.bat
```

`start.bat` now prefers Python 3.12 specifically (via `py -3.12`) even if
3.14 is your default - if it can't find 3.12, it prints install
instructions before falling back. First run installs everything fresh.

Drag in `PrometeoLasc2026.ork` + `Icarus_I_K519.eng` on the **Simulate**
page and click **Load files**, then **Simulate** - **you do not need to
type a manual mass/CG override anymore** for the app to produce a result
(though your `.ork`'s own incomplete override still means that
no-override result is unstable/approximate - see "what I need from you").
The sidebar (Rocket, Monte Carlo, RCSM Cases, Analysis, History, Exports,
Validation) all work off that same result now.

## What I need from you

1. **Still the same #1 ask as before**: a whole-rocket `overridemass` +
   `overridecg` in OpenRocket on `PrometeoLasc2026.ork`, from your LRR
   scale measurement, with "override subcomponents" checked. This is the
   one input nothing in this app can substitute for, and it's the reason
   the no-override default path is still unstable for your real rocket
   right now.
2. **Real Iacanga weather + exact LASC date/time** - more relevant now
   than ever: the Brasil-config check now matches OpenRocket almost
   exactly with no weather guessing, which means V2's remaining -5.8%
   gap increasingly looks like a real difference between the `.ork`'s
   recorded weather and Iacanga's actual flight-day conditions, not a
   code bug. This is the most likely way to close that gap further.
3. **Major Tom's `.ork` + `.eng` files** - still not in the repo, still
   nothing to test the app's second vehicle against.
4. **Logo files** (`logo_gold.png`/`logo_wine.png` in
   `bup_rocketpy/gui/assets/`) whenever the rebrand assets exist - text
   wordmark works fine as a placeholder.
5. **Look at the app yourself again** when you get a chance - I have new
   Playwright screenshots (`docs/screenshots/`) including the fixed
   Rocket page and the new recovery panel, but nothing replaces you
   clicking around with a real mouse, which is exactly what caught all
   of tonight's Section 1/2 bugs in the first place.

I'm continuing with the rest of Section 5 (remaining plots, rocket info
panel), Section 6 (writing up the 4 rocketpy bugs as minimal repro
scripts + draft GitHub issues), and Section 7 (the Leaflet landing map)
next, and will update this file again at the end.
