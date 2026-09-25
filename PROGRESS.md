# PROGRESS - autonomous overnight run

Started 2026-09-25. This file is the resume point if context gets compacted -
check here first, then CHANGELOG.md for detail.

## Checklist

- [x] Phase 0: repo restructure (common/ -> stella_flight/) - commit 59c4c19
- [x] Phase 1a: ork_reader.py, motor_reader.py, translate.py built - commit 0dc168c
- [x] Phase 1b: real acceptance test vs PROMETEO's real .ork (moved to
      `reference/prometeo_mission44/data/ork/PrometeoLasc2026.ork`) -
      tests/test_phase1_acceptance.py, 5/5 pass (with 2 honestly-documented
      known limitations, not hidden - see "Phase 1 findings" below)
- [x] Phase 1c: fix Cd=0.5 placeholder -> real power_on/off_drag.csv curves
      (translate.build_rocket/ork_to_flight now REQUIRE a drag curve path,
      no silent default)
- [ ] Phase 1d: coordinate-convention test (tail_to_nose vs nose_to_tail, same CP/margin) - NOT DONE YET, next
- [x] Phase 1e: fix "validated" language - ork_reader.SimulationReference
      docstring + all Phase 1 tests explicitly say "OpenRocket reference,
      NOT validated" (validated = compared to flight data, Phase 2 only)
- [ ] Phase 2: V1 (2026-07-04, 1019.9 m) + V2 (LASC, 1137 m) validation tests,
      OpenRocket-recorded conditions (no live weather - cloud can't reach it)
- [ ] Phase 2: Cd-extraction-from-CSV vs committed drag curves, logged
- [ ] Phase 2: telemetry_2026_07_04.xlsx inspected (columns, sample rate)
- [ ] Phase 3: NiceGUI app, start.bat, headless smoke test
- [ ] Phase 4: Monte Carlo + landing ellipse
- [ ] Phase 5: Ballistic + Nominal cases, per-case .py export (CRS 10.1.6),
      tested in a clean venv
- [ ] Phase 5 (rest): drogue-only / main-at-apogee, PDF/DOCX report
- [ ] Phase 6: weathercocking sweep, drag comparison
- [ ] MORNING_REPORT.md written and pushed last

## BLOCKED / NEEDS DIEGO

(nothing yet - filled in as found, never stops the run)

## Log

- 06:30 Pulled Diego's `rocket.ork` upload (landed at repo root), moved to
  `reference/prometeo_mission44/data/ork/PrometeoLasc2026.ork` to match the
  existing data/ layout. Confirmed plain-XML (not zipped), OpenRocket 24.12,
  2 stored simulations (both Brasil-config variants, rail 4.0m/10deg from
  vertical, elevation 495.0m and 490.0m respectively - investigating which
  is the LASC-as-flown one next.
