# Changelog

## Phase 0 - repo realignment

- Restructured `common/` (an earlier, since-abandoned "design tool" plan -
  see CLAUDE.md Sec 1, "no design search") into `stella_flight/`:
  - `common/rules.py` -> `stella_flight/rcsm.py` (unchanged)
  - `common/environment.py` -> `stella_flight/environment.py` (unchanged;
    Phase 2 will add Open-Meteo/GFS/sounding sources and caching)
  - `common/design_search.py` deleted (contradicted CLAUDE.md Sec 1)
  - Added `stella_flight/gui/` (empty, for Phase 3)
- Updated `README.md` to describe the app (not the old parametric-design
  scope).
