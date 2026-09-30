"""2026-09-30 review, Windows bug 2: "OpenRocket-style CSV export failed:
'charmap' codec can't encode character '\\u200b'". Root cause: open()
with no `encoding=` defaults to the OS's "locale preferred" encoding -
UTF-8 on this project's own (Linux, UTF-8-locale) dev/test environment,
but Windows' ANSI codepage (cp1252 for most US/Western installs) unless
the user has separately opted into "Use Unicode UTF-8 for worldwide
language support" - so a bug class like this is INVISIBLE in this
project's own test runs no matter how thoroughly they're run, and only
shows up on Diego's own machine.

Two complements, matching the review's own two asks:
1. A concrete regression test reproducing the EXACT reported failure
   (export_openrocket_style_csv, whose 58 real OpenRocket column names
   include a literal zero-width space) inside a subprocess with Python's
   UTF-8 mode disabled and a non-UTF-8 locale - the closest available
   proxy for "Windows, no explicit encoding" this Linux sandbox has (no
   cp1252 locale is actually installed here - `locale -a` only lists
   C/C.utf8/POSIX - so this uses the C/POSIX locale instead; it fails
   with a different codec NAME ('ascii', not 'charmap') but the exact
   same class of bug: a default encoding that can't represent U+200B).
2. A static AST scan added as a standing test (item 3's "Windows
   emulation CI step" spirit, made to run every time, not just once) so
   a FUTURE bare open(path, "w")/open(path) added anywhere in
   bup_rocketpy/ fails CI immediately, in any locale, without needing to
   actually reproduce Windows' locale to catch it.
"""
import ast
import glob
import os
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNNER = os.path.join(REPO_ROOT, "tests", "_windows_encoding_runner.py")


def test_openrocket_csv_export_survives_non_utf8_default_encoding():
    env = dict(os.environ)
    env.update(LC_ALL="C", LANG="C", PYTHONUTF8="0", PYTHONCOERCECLOCALE="0")
    proc = subprocess.run([sys.executable, RUNNER], cwd=REPO_ROOT, env=env,
                           capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, (
        f"export crashed under a non-UTF-8 default encoding (Windows' own failure mode) - "
        f"the exact bug Diego reported:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
    )
    assert "OK" in proc.stdout, f"unexpected runner output:\n{proc.stdout}"


def _bare_open_calls_missing_encoding(py_path):
    with open(py_path, encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=py_path)
    findings = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "open"):
            continue
        mode = None
        if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
            mode = node.args[1].value
        for kw in node.keywords:
            if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                mode = kw.value.value
        if mode and "b" in mode:
            continue  # binary mode - an encoding= kwarg would itself be an error here
        has_encoding = any(kw.arg == "encoding" for kw in node.keywords)
        if not has_encoding:
            findings.append(node.lineno)
    return findings


def test_no_bare_open_without_explicit_encoding_in_bup_rocketpy():
    """2026-09-30 review item 2: "grep the whole codebase for open(...
    without an encoding" - kept as a standing test so this can't silently
    regress the next time someone adds a new open() call."""
    offenders = {}
    for py_path in glob.glob(os.path.join(REPO_ROOT, "bup_rocketpy", "**", "*.py"), recursive=True):
        lines = _bare_open_calls_missing_encoding(py_path)
        if lines:
            offenders[os.path.relpath(py_path, REPO_ROOT)] = lines
    assert not offenders, (
        "found open(...) call(s) with no explicit encoding= (text mode defaults to the OS "
        f"locale - cp1252 on most Windows installs, not UTF-8): {offenders}"
    )


if __name__ == "__main__":
    test_openrocket_csv_export_survives_non_utf8_default_encoding()
    test_no_bare_open_without_explicit_encoding_in_bup_rocketpy()
    print("\nENCODING DEFAULTS: OK")
