# Notes for Diego (plain language, no code)

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
