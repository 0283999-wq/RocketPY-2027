# Morning report - autonomous run 4: validation chip, OpenRocket comparison, reefing fix, report rewrite

`main` builds and passes its full test suite after every commit tonight
(4 sections, 8 commits, each pushed only after the full suite was
green). Nothing below left the app in a broken state at any point.

Major Tom's `.ork`/`.eng` (attached with tonight's instructions) were
used for local checks only in Section 2 and are **not** committed, per
your explicit instruction.

## Status table

| Section | Status |
|---|---|
| 1 - Replace the stale PROVISIONAL banner with a real validation chip | **Done** |
| 2 - Rocket page OpenRocket comparison card + fix dimension/drawing gaps | **Done** |
| 3 - Fix reefing never reaching Monte Carlo | **Done** |
| 4 - Rewrite report generation as HTML/CSS -> PDF/DOCX | **Done** |

## Section 1: the PROVISIONAL banner

Replaced the big "PROVISIONAL" banner that appeared on every single
simulation with a small status chip on the results page ("Model
validated on 1 flight (LASC 2026, -3.4%) - 1 pending"), linking to the
Validation page. V1 (the 2026-07-04 profile check) now reports
`status="inconclusive"` instead of FAIL - it uses a CG approximated
from a different vehicle configuration (the July-4-specific design
file still hasn't arrived), so scoring its miss as a plain FAIL would
blame the flight model for an input-data gap, not a real disagreement.

Also scrubbed every `"see PROGRESS.md"` reference a real person could
see: the Validation page's own captions, the generated per-case `.py`
files and the LASC `.zip`'s `README.txt` (both read by LASC judges),
and a `translate.estimate_best_dry_mass_cg_inertia` code-name leak in
the mass-source string shown throughout the app.

## Section 2: OpenRocket comparison card

New `bup_rocketpy/openrocket_comparison.py`: a 9-row table (length, max
diameter, mass with/without motor, CG with motor at t=0, CP at Mach
0.3, stability at Mach 0.3 (t=0), apogee, max Mach) comparing this
app's own computed numbers against the `.ork`'s OWN stored simulation -
works for any `.ork` with a stored sim, not hand-typed per rocket.
CP/stability get a 2% tolerance (documented RocketPy/OpenRocket body-
lift model difference), everything else 1%.

Investigated Major Tom's real files and found/fixed 3 real bugs:
1. `<tubecoupler>` mass overrides were silently dropped into the
   generic "unhandled nested tag" IGNORED branch.
2. The vehicle drawing's motor rectangle was real, working code that
   had simply never been wired up at any of its 4 call sites - no
   rocket drawing anywhere in the app had ever shown a motor.
3. The transition/boat-tail was drawn at the same low opacity as the
   body tube, so a shallow taper visually disappeared into it.

On the specific mass mismatch you reported: Major Tom's `.ork`'s OWN
stored simulation computes dry mass 15.021 kg / with-motor 30.981 kg,
and this app's comparison card matches all three of those numbers to
within 0.00-0.22%. That's different from the 13,758 g you read off
OpenRocket's live panel - since the numbers embedded in the file you
sent and the numbers you read live don't agree with each other either,
this looks like the file being a slightly earlier/later save than what
you were looking at, not a bug in how the app reads it. Re-export and
re-upload a fresher `.ork` and the comparison card will show it
immediately.

## Section 3: reefing missing from Monte Carlo

Root cause: RocketPy 1.13.0's `StochasticRocket.create_object()`
doesn't carry over anything added to the nominal rocket via
`rocket.add_X()` - a documented bug class for nose/fins, never
re-checked for parachutes. Every Monte Carlo sample had **zero**
parachutes, reefed or not (confirmed: with a fixed seed, reefed and
non-reefed impact samples were bit-for-bit identical, exactly what you
reported).

Fixed by re-registering every parachute on the `StochasticRocket`, plus
wiring in the `parachute_cd_s_factor`/`parachute_lag_s` uncertainties
that had been listed with sources since Phase 4 but never actually
applied to anything. Found and fixed a second bug while verifying:
randomizing lag around a real 0s nominal samples negative ~50% of the
time, which corrupts the trajectory (RocketPy's own docstring warns
about this) - now only randomizes lag when the nominal is comfortably
positive.

Confirmed with a fresh run: reefed Nominal case flight time 130.2s vs.
206.8s not reefed, for PROMETEO. The 4 RCSM cases, report and CSV all
already went through the same shared `build_rocket()` path, so they
needed no separate fix - just confirmation.

## Section 4: report rewritten as HTML/CSS -> PDF/DOCX

Replaced the entire reportlab PDF pipeline and the old python-docx
generator (per your instruction to stop fighting reportlab). New
architecture: `report_html.py` + `report_templates/report.html`
renders via Jinja2, printed by real Playwright Chromium, with a
two-pass render for a genuine table of contents with real page
numbers. New `report_docx.py` builds a real Word document with a
genuine TOC field, styled tables, and a real header/footer with
PAGE/NUMPAGES fields. Both consume the same `build_report_data()`
dict, so the two formats can never silently disagree.

Added the requested structure: General information and set-up (with a
Simulation Parameters sub-section reading RocketPy's own integrator
settings directly, modeled on the SOLIDWORKS template you sent), a
Global min-max table section, and an Appendix A with the actual motor/
drag/parachute/launch input data.

**Visual QA** (rendering every PDF page to PNG and inspecting it, per
your explicit instruction) found and fixed 6 real bugs unit tests alone
would never have caught:

1. A table's last row split across a page boundary, leaving the next
   page 95% blank with one stranded row.
2. **The table of contents' page numbers were completely broken** -
   every row showed "..." instead of a real number, in every report
   this new architecture had ever produced. Root cause: Chromium's
   print pipeline does not paint `color:transparent` (or `opacity:0`)
   text at all - it never reaches the PDF's text layer, so the
   invisible page markers the TOC mechanism searches for were never
   actually in the rendered PDF. Fixed by switching the markers to
   `color:#ffffff` (invisible on the white page, but painted and
   extractable).
3. The old internal codename "StellaIgnis" was leaking into the
   Propulsion section and Appendix A - traced to PROMETEO's own `.eng`
   file (pre-dating the Section 0 rename), not to any report code.
   Fixed at the source file; cosmetic metadata only, no physics
   affected.
4. A plot legend overlapped its own annotation text on the static
   margin figure.
5. The Monte Carlo landing-ellipse figure baked huge blank margins into
   its own PNG (equal-aspect axes on a square canvas, needed for
   correct 1m-in-X-equals-1m-in-Y scaling, almost never actually fill a
   square) - fixed with a tight crop on save, in both the report and
   the live Monte Carlo page.
6. Appendix A's parachute row read "Deploy: never @ 200 m" for
   PROMETEO - technically what's in the `.ork` (OpenRocket keeps a
   stale altitude value even when deployment is set to "never"), but
   actively misleading. Now shown as "Deploy: simulated at apogee (.ork
   says \"never\")" with the existing explanatory warning.

**A 7th bug came from the full test suite, not visual QA**: the actual
"Generate PDF report" button in the running app started silently timing
out. Playwright's sync API refuses to run inside a thread with a
running asyncio event loop, and the button's `on_click` handler called
the Chromium-driving report generator directly on NiceGUI's own event
loop thread. Fixed by running report generation through `run.io_bound`,
the same pattern Monte Carlo already uses for background work -
confirmed with a minimal repro before and after the fix, then verified
against the real end-to-end Playwright test that clicks the actual
button.

DOCX was checked structurally (soffice cannot render ANY `.docx` in
this sandbox, confirmed with a trivial test file too - an environment
limitation, not a bug here): real TOC field present, PAGE/NUMPAGES
fields present in the footer, no leftover codenames, no unresolved
`{fig}` placeholders, exactly one appropriately-scoped yellow
`[EDIT: ...]` mark (team member names).

Sample reports (PDF + DOCX + per-page PNGs) committed to
`docs/sample_reports/`: `prometeo_mission44/` (real motor + real drag
data, Monte Carlo N=30, full appendix) and `openrocket_example/` (the
repo's own `Dual_parachute_deployment.ork` fixture, clearly labeled as
a demo pairing - it correctly shows a static margin OUTSIDE the RCSM
band and a red "NO" stability chip rather than hiding or fabricating a
pass).

## Exact PowerShell commands

```powershell
git pull
.\start.bat
```

`start.bat` re-syncs `requirements.txt` on every run. Tonight added
`jinja2` and removed `reportlab` - no separate install step needed
after `git pull`.

To see tonight's report changes without running the app: open
`docs/sample_reports/prometeo_mission44/prometeo_mission44_report.pdf`
(or `.docx`), or just look at the page PNGs in that folder.

## What I need from you (one line each)

- **The July 4 `.ork`** - still pending; V1 still uses a CG
  approximated from the Brasil-config file, which is why it now reports
  "inconclusive" rather than a scored PASS/FAIL.
- **A fresher Major Tom `.ork`** - the one you sent tonight's stored
  simulation doesn't match the numbers you read live off OpenRocket's
  panel (see Section 2 above); re-export and re-upload to get an
  accurate comparison card.
- **Exact LASC 2026 flight date/time at Iacanga** - still pending, for
  a real weather-based V2 re-run.

## Full test count

112 passed, 1 skipped - a single clean full-suite run at the end of
tonight's work (an earlier run showed spurious failures from two
pytest processes accidentally racing on the same shared `outputs/`
directory; re-ran clean to confirm before committing). Same count as
before tonight's run - Section 4's two rewritten report tests replaced
their old reportlab-specific assertions 1:1, no tests added or removed
elsewhere.
