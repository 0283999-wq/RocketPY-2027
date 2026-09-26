# Morning report - autonomous run 2 (MEGA_PROMPT_2), Sections 1-5 done

Status as of Section 5. This file is updated again at the end of the run
with whatever else got done in Sections 6-7. `main` builds and passes
its full test suite + Playwright e2e after every commit below - nothing
here left the app in a broken state.

## Status table

| Section | Status |
|---|---|
| 1 - mass/CG/inertia matching OpenRocket | **Done** (mechanism proven on PROMETEO + both OpenRocket examples; Major Tom itself still blocked, see below) |
| 2 - reefing/settings persistence ("mission" save+reopen) | **Done** |
| 3 - launch-day weather correctness (timezone bug) | **Done** |
| 4 - History page (detail view, real delete fix, reopen) | **Done** |
| 5 - validation consistency (V2 now passes) | **Done** |
| 6 - real technical report (prose, not a data dump) | Not started |
| 7 - Mission Control redesign (3D playback, live MC) | Not started - now IN SCOPE per this prompt, unlike last night |

Continuing now with Section 6 (reading the two reference PDFs first, as
instructed), then Section 7.

## Numbers before/after this run

- **Section 1 (mass/CG)**: PROMETEO's own default-path apogee moved from
  1088.0 m (old geometric thin-shell estimate) to **1072.1 m** (new:
  OpenRocket's own stored-simulation mass/CG, minus motor) - closer to
  the ~1080 m ballpark, and now grounded in OpenRocket's own computed
  total instead of a from-scratch approximation that was off by **-35%
  to -50%** on both shipped OpenRocket example rockets (checked directly
  against their own stored-sim ground truth). Margin: 1.94 -> 2.04 cal.
  Descent: 5.49 -> 5.51 m/s.
- **Section 1 (a real bug caught along the way)**: last night's new
  OpenRocket-style CSV export had its "Longitudinal"/"Rotational" moment
  of inertia columns backwards - fixed, with a regression test.
- **Section 5 (validation)**: **V2 now predicts 1098.3 m vs. the 1137 m
  target - error -3.4%, PASSES within +-5%** (was -6.1%, FAIL). This is
  the single biggest number change tonight, and it's earned: it came
  from fixing a real data-consistency bug (V2's with-motor CG and rocket
  length were pulled from a DIFFERENT source than the .ork's own stored
  simulation - see Section 5 in PROGRESS.md for the full diagnosis),
  which is also exactly why the OLD numbers had V2 (150 g lighter)
  predicting a LOWER apogee than the unconstrained default run -
  physically backwards. Not tuned - the fix is a code path unification,
  and V1 (+11.0%, unchanged, still fails) proves nothing was tweaked to
  force a pass. The app-wide PROVISIONAL badge correctly stays up
  (CLAUDE.md Rule 3 needs BOTH to pass).
- **Section 3 (weather)**: root-caused Diego's reported "0.3 m/s from
  121 deg vs. a 4-9 m/s NE forecast" to a missing `timezone=` parameter
  in every Open-Meteo request - Open-Meteo defaulted to GMT, so "12:00
  local" was silently read as 06:00 local (early morning, much calmer).
  Fixed; every request now gets local-time-correct results.

## Exact PowerShell commands (unchanged)

```powershell
git pull
.\start.bat
```

`start.bat` re-syncs `requirements.txt` on every run, so no separate
reinstall step is ever needed after a `git pull`.

## What I need from you (one line each)

- **Major Tom's `.ork`/`.eng`** - still not in this repo (flagged since
  Phase 1). Section 1's mass/CG fix is proven on PROMETEO and both
  OpenRocket example rockets, but can't be demonstrated on Major Tom
  itself without these files.
- **The July 4 .ork** - checked `reference/prometeo_mission44/data/rockets/`
  per your instruction; only the two drag CSVs are there. V1 still uses
  the Brasil-config CG approximation, not a July-4-specific measurement.
- **Exact LASC 2026 flight date/time at Iacanga** - already logged as
  pending from an earlier session; needed for the Validation page's "V2
  re-run with real weather" to produce a real number instead of the
  honest "date not yet known" message (the mechanism itself works).
- **The reference PDFs** (`docs/report_references/`) - received and will
  be read before Section 6's report rewrite starts, per your instruction.

None of these block Sections 1-5 above or (expected) Sections 6-7 -
each is an isolated, clearly labeled gap.
