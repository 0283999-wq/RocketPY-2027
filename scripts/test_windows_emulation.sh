#!/usr/bin/env bash
# 2026-09-30 review item 3: "Add a 'Windows emulation' CI step for the
# future: the full test suite with multiprocessing 'spawn' + cp1252
# default encoding." There's no CI config in this repo yet (add this as
# a job's `run:` step whenever one is set up) - until then, run this
# manually before pushing anything that touches file I/O or
# multiprocessing (Monte Carlo, drag comparison, the LASC package, any
# CSV/JSON export).
#
# What this actually emulates, and why (see the two real Windows-only
# bugs this was written after - "git log --grep 'Windows [Bb]ug'"):
#   - PYTHONUTF8=0 + a non-UTF-8 locale: on Windows, open() with no
#     explicit encoding= defaults to the OS's ANSI codepage (cp1252 for
#     most US/Western installs), not UTF-8 - invisible on this
#     project's own Linux dev boxes, which default to a UTF-8 locale
#     (or Python's automatic UTF-8 mode). No cp1252 locale is actually
#     installed in this sandbox (`locale -a` only lists C/C.utf8/POSIX),
#     so this uses C/POSIX instead - same failure class (a non-UTF-8
#     default encoding that can't represent characters like OpenRocket's
#     own zero-width-space column name), a different codec NAME.
#   - BUP_WINDOWS_EMULATION=1: read by tests/conftest.py, forces
#     multiprocessing's start method to "spawn" - Windows' ONLY option,
#     vs. Linux's default "fork" - for every ProcessPoolExecutor this
#     suite creates (Monte Carlo, drag comparison), not just the two
#     tests that already force it locally in their own subprocess.
set -euo pipefail
cd "$(dirname "$0")/.."

export PYTHONUTF8=0
export LC_ALL=C
export LANG=C
export PYTHONCOERCECLOCALE=0
export BUP_WINDOWS_EMULATION=1

echo "Running the full suite under Windows emulation (spawn + non-UTF-8 default encoding)..."
.venv/bin/python -m pytest tests/ -q "$@"
