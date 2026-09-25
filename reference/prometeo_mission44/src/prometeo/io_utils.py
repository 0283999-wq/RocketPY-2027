"""Parser for OpenRocket's comment-header CSV export format.

Column names live on the single line starting with "# Time (s)", not in a
normal header row - `pd.read_csv` can't see them without this split. Event
markers ("# Event BURNOUT occurred at t=3.57 seconds") are comments too and
get dropped by a naive read; we pull them out separately since Mission44
scripts need BURNOUT/APOGEE/LAUNCHROD timestamps for phase-gated drag
extraction and validation.
"""

import io
import re

import pandas as pd


def load_openrocket_csv(path):
    """Returns (df, events) where events is {EVENT_NAME: t_seconds}."""
    header = None
    events = {}
    with open(path, encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    for ln in lines:
        if ln.startswith("# Time (s)"):
            header = ln.lstrip("#").strip().split(",")
        elif ln.startswith("# Event"):
            m = re.search(r"Event ([\w_]+) occurred at t=([\d.eE+-]+)", ln)
            if m:
                events[m.group(1)] = float(m.group(2))
    if header is None:
        raise ValueError(f"no '# Time (s)' header line found in {path}")
    data_lines = [ln for ln in lines if not ln.startswith("#") and ln.strip()]
    df = pd.read_csv(io.StringIO("".join(data_lines)), header=None, names=header)
    return df, events
