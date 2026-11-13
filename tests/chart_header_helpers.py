"""K12-CHART-LABEL-EDGE-001: tests that compare charts with an earlier commit compare them in the old header, so only the header (added by
tools/nj_chart_label_edge.py to all 1146 charts) is tolerated, never any other byte."""
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import nj_chart_label_edge as E  # noqa: E402

DISTRICT_CHART = re.compile(r"charts/d/\d{7}-(?:mobile|desktop)\.svg")


def read(rel):
    with open(os.path.join(ROOT, *rel.split("/")), encoding="utf-8", newline="") as fh:
        return fh.read()


def show(commit, rel):
    return subprocess.run(["git", "-C", ROOT, "show", f"{commit}:{rel}"], capture_output=True, check=True).stdout.decode()


def content_changes(commit, names):
    """The names whose committed chart differs from `commit` by more than the headroom header."""
    return [n for n in names if not DISTRICT_CHART.fullmatch(n) or E.remove_headroom(read(n)) != show(commit, n)]
