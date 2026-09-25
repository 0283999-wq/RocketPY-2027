# OpenRocket example rockets

Two `.ork` files pulled from the [OpenRocket project's own example
rockets](https://github.com/openrocket/openrocket/tree/master/core/src/main/resources/datafiles/examples)
(GPL v3, bundled with every OpenRocket install for exactly this kind of
use - testing a reader/importer against real files that aren't
PROMETEO's). Used only as **test fixtures**, not simulated for any
validation claim:

- `A_simple_model_rocket.ork` - a single-fin, single-parachute Estes
  A8/B4/C6-class model rocket. Used by
  `tests/test_phase0_e2e_full.py` to prove the app's Rocket page
  updates to a genuinely different rocket's geometry after loading a
  second `.ork` (2026-09-25 review Section 4), not stale data from the
  first one loaded (2026-09-25 review crash (e)).
- `Dual_parachute_deployment.ork` - has both a drogue (apogee-triggered)
  and a main (altitude-triggered) parachute, unlike PROMETEO's single-
  chute design. Used for testing the RCSM Drogue-only/Main-at-apogee
  cases against a real dual-deployment vehicle (2026-09-25 review
  Section 7).

Both reference an Estes A8/B4/C6 motor mount in their own `.ork`, which
this repo has no `.eng` for. Where a test needs to click "Simulate" on
one of these (not just "Load"), it pairs the `.ork` with PROMETEO's real
`Icarus_I_K519.eng` - physically nonsensical as a real motor choice, but
these tests are checking UI/pipeline behavior (does the page update, does
a dual-deploy case run without crashing), not vehicle performance, so a
real `.eng` file paired with a different real `.ork` is an honest test
fixture, not fabricated data.
