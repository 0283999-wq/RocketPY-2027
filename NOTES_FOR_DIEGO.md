# Notes for Diego (plain language, no code)

## The +10% bug hunt: found part of it, not all of it

Good catch pushing on this. Here's what I found:

- **The July 4 gap is explained, not a bug**: OpenRocket used a different
  motor for that specific export than the one `.eng` file we actually
  have (shorter, hotter burn - 1732 Ns vs our 1871 Ns file). This was
  already written down in `config.py`'s own comments from before tonight.
  Not something to fix in code - we'd need a July4-specific `.eng`.
- **The Brasil-config gap is real, and I have NOT found the cause yet.**
  I checked, with actual numbers, every one of your suspects: reference
  area matches exactly, the Cd curves match OpenRocket's own values at
  Mach 0.3 to better than 0.1%, the motor's total impulse and burn time
  match exactly, air density and gravity match exactly. None of those are
  it. I did NOT tune anything to hide this - it's still open.
- One odd thing I found along the way: our rocket leaves the launch rail
  SLOWER than OpenRocket's own number (15.6 vs 16.8 m/s), which is the
  opposite of what you'd expect if we were under-predicting drag. That's
  a real lead for whoever picks this up next, not yet chased down.

Full diagnostic table and everything ruled out: `PROGRESS.md`, "Item 1
findings".

## Fixed: the upload bug you found

You were exactly right - the file upload was silently broken. The library
I'm using for the app updated how it hands off uploaded files between
when I wrote the first version and now, and my code was still using the
old way. Fixed, and this time I built a permanent test that actually
opens a real Chrome browser, uploads your real files, and clicks through
to the results - not just testing the code behind the scenes. That test
now passes and will run after every UI change from now on, so this exact
kind of bug gets caught immediately instead of shipping to you again.

## Phase 5 (partial): the actual LASC submission files now generate correctly

The app can now export `Mission44_Ballistic_RocketPy_v1.py` and
`Mission44_Nominal_RocketPy_v1.py` - these are the literal files you'd zip
up and submit. I proved they actually work standalone: built a brand new,
empty Python environment, installed only `rocketpy` into it (nothing else
from this repo), ran both files, and their answers matched the app's own
prediction to 0.003%. That's the real CRS requirement (someone else can
run it with nothing but `pip install rocketpy`), not just "it doesn't
crash."

Still missing for a real submission: the drogue-only/main-at-apogee
cases (only mandatory for >1500m vehicles, so less urgent for PROMETEO),
the PDF/DOCX report, and zipping everything together. Didn't get to those
tonight - see the priority order in PROGRESS.md.

## Phase 3: the app itself is up - please test it on your machine

`start.bat` is there. Double-click it: first time it sets up Python and
installs everything, then opens the app in your browser. Drag in your
`.ork` and `.eng`, click "Load files" to see what got imported, then
"Simulate" for the numbers and plots.

**One thing you'll need to do by hand for now:** since your `.ork`'s mass
override is incomplete (see Phase 1 notes below), the app will show an
"UNSTABLE" result if you just click through without entering a manual
mass/CG. There are two boxes for that above the Simulate button - use
5.6622 kg / 0.6279 m until you fix the override in OpenRocket itself.

**I could not test the actual browser window** - this cloud container has
no display, so I only proved the underlying logic works (loads your real
files, produces sane numbers, writes real plot images). Please confirm the
page itself looks right and the buttons work on your end - that's the one
part of tonight's work I genuinely could not verify myself.

## Phase 2: V1/V2 results, honestly - neither passes yet

- **V1 (July 4):** predicted 1124 m vs. your real 1020 m flight - **10.2%
  high.** Main reason: I don't have a CG measurement specific to that
  flight's exact mass, so I reused the LASC-config CG on a lighter rocket -
  that's a real approximation, not a bug.
- **V2 (LASC):** predicted 1197 m vs. your real 1137 m flight - **5.3%
  high, just barely outside the ±5% target.** This one's close - the two
  biggest things that could close the rest of the gap are (1) real
  Iacanga weather instead of the placeholder OpenRocket-recorded wind, and
  (2) an actual LASC-specific motor mass instead of reusing the Brasil
  design figure.
- I did **not** tune anything to force either number closer - both stay
  marked PROVISIONAL, per your own instructions. Full breakdown is in
  `PROGRESS.md`.
- Also confirmed your drag curve extraction script is fully reproducible
  (reran it, byte-for-byte identical to what's committed) and inspected
  the telemetry file (72 packets, ~2.5 Hz, apogee packet matches your
  1019.9 m exactly).

## Autonomous overnight run - Phase 1 corrections

Thanks for the review, all 4 corrections are in. Short version:

- **Your real `.ork` is in and tested.** I moved it to
  `reference/prometeo_mission44/data/ork/PrometeoLasc2026.ork` (it landed at
  the repo root when you uploaded it). The geometry reading is solid: CP
  position matches OpenRocket's own number to 0.5%, diameter to 0.4%.
- **Mass doesn't match yet, and I know exactly why, and it's on you to
  fix, not me to guess around:** your `.ork`'s override only covers the
  Fuselage tube's own shell mass (1.475 kg). It does NOT cover the whole
  rocket. Several real parts (bulkheads/centering rings near the motor
  mount) don't have a resolvable size in the file, so the app can't
  compute their mass either. Result: my estimate comes out ~19% light,
  and a full flight built from it is borderline unstable - not because
  the physics is wrong, but because the mass input is incomplete. **Fix:**
  in OpenRocket, set a mass and CG override on the ROCKET itself (top
  level), typed in from your LRR scale measurement, with "override
  subcomponents" checked. That's the one thing I can't substitute for you.
- **Real drag curves are wired in now** - no more flat Cd=0.5 placeholder
  anywhere in the default path.
- **Coordinate convention (tail_to_nose vs nose_to_tail)**: I proved both
  give the identical answer (same CP, same static margin, to 9 decimal
  places) when used consistently, which is what the code now guarantees.
  Non-issue, just needed to show the proof.

See `CHANGELOG.md` for the exact numbers and every bug found along the way
(there were a few real ones - rail buttons, nose cone shape names, nested
payload-bay masses - all caught specifically because I finally had a real
file to test against instead of guessing from the format spec).

## Phase 1: the file readers work

**I built the file readers.** `stella_flight/` can now:
- Open a `.ork` file (zip or plain XML) and pull out the nose cone, body
  tubes, fins, parachutes, point masses, rail buttons, and any measured
  mass/CG you typed into OpenRocket's override fields.
- Open a `.eng` motor file and read the thrust curve + header.
- Turn both into an actual flyable RocketPy rocket.

**I tested it two ways**, since we still don't have PROMETEO's real `.ork`:
1. Against 3 real example rockets from OpenRocket's own GitHub, just to make
   sure the file-reading part doesn't choke on a real file. It didn't.
2. Against PROMETEO's own **already-checked** numbers (mass, CG) from
   `reference/prometeo_mission44/config.py` - not the real `.ork`, but the
   real, previously-verified values. Mass and CG came through exactly right.
   A full simulated flight with PROMETEO's real motor came out stable and
   in the right ballpark (apogee ~1165 m vs. the real ~1082 m sim) - the gap
   is expected, explained below.

### What's still missing / needs your input

1. **PROMETEO's real `.ork` file** (the one from your local `RocketPY/`
   folder, or wherever it lives, in the actual LASC configuration). Without
   it I can't run the formal accuracy check CLAUDE.md sets (mass/CG/CP
   within 1% of what OpenRocket itself shows).
2. **Major Tom's `.ork`** and both `.eng` files (K503, M1739-P), whenever
   they're ready.
3. A real drag curve is still missing from every test I ran - I used a flat,
   made-up number (Cd = 0.5) as a placeholder, the same shortcut the *old*
   repo used and that CLAUDE.md specifically says to fix. That's the biggest
   reason my test apogee (1165 m) came out higher than PROMETEO's real
   number (1082 m). Once we have a `.ork` with its stored drag data, or one
   of the OpenRocket CSV exports, this gets fixed - it's Phase 2 work.
4. **One thing to confirm with the team**: your own brief (CLAUDE.md) says
   RocketPy should use "nose_to_tail" coordinates, but PROMETEO's actual
   validated code uses "tail_to_nose". I went with what the validated code
   does, but flagging it so nobody assumes I just made a typo.

See `CHANGELOG.md` for the full technical detail.

## Phase 0: repo reorganized

The old `common/` folder (from before this CLAUDE.md brief existed) is gone.
What was useful from it moved into a new `stella_flight/` folder, which is
the real app code from now on. Nothing about your data or the PROMETEO
reference was touched.
