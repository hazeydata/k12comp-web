"""Shared helpers for the NJ history tests: one cached real build, fresh pinned reads, small HTML extractors."""
import atexit
import csv
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from nj_history import build as B, data as D, render as R  # noqa: E402

BASE_COMMIT = "3b50ce10b88e80188e6c8265634b68b482c1a81f"  # live k12comp-web main the spec was written against
DATA_REPO = os.environ.get("K12_DATA_REPO", "")
LOCK = D.load_lock()
COMMIT = LOCK["data_commit"]
WINDOW = D.WINDOW
_tmp = []


def tmpdir(prefix="k12nj-test-"):
    d = tempfile.mkdtemp(prefix=prefix)
    _tmp.append(d)
    return d


@atexit.register
def _cleanup():
    for d in _tmp:
        shutil.rmtree(d, ignore_errors=True)


def pinned(path):
    """Fresh read of a pinned input, independent of tools/nj_history."""
    return subprocess.run(["git", "-C", DATA_REPO, "show", f"{COMMIT}:{path}"], capture_output=True, check=True).stdout.decode()


def pinned_staff_rows():
    rows = []
    for y in WINDOW:
        rows += list(csv.DictReader(io.StringIO(pinned(f"data/nj_district_staff_{y}.csv"), newline="")))
    return rows


def git_base(path):
    return subprocess.run(["git", "-C", ROOT, "show", f"{BASE_COMMIT}:{path}"], capture_output=True, check=True).stdout


def base_paths():
    out = subprocess.run(["git", "-C", ROOT, "ls-tree", "-r", "--name-only", BASE_COMMIT], capture_output=True, check=True).stdout
    return out.decode().splitlines()


_built = {}


def built():
    """The real build from the pinned data, once per test process. Returns (out_dir, report)."""
    if "b" not in _built:
        out = os.path.join(tmpdir(), "site")
        _built["b"] = (out, B.run(site_root=_site_tree(), out_dir=out, data_repo=DATA_REPO))
    return _built["b"]


def _site_tree():
    """A pristine copy of the base commit tree (the working tree may carry untracked build output)."""
    if "tree" not in _built:
        d = os.path.join(tmpdir(), "base")
        os.makedirs(d)
        tar = subprocess.run(["git", "-C", ROOT, "archive", BASE_COMMIT], capture_output=True, check=True).stdout
        subprocess.run(["tar", "-x", "-C", d], input=tar, check=True)
        _built["tree"] = d
    return _built["tree"]


def site_tree():
    return _site_tree()


def read(out, rel):
    with open(os.path.join(out, *rel.split("/")), "rb") as f:
        return f.read().decode("utf-8")


def history_section(page):
    m = re.search(r'<section class="nj-hist".*?</section>', page, re.S)
    return m.group(0) if m else None


def strip_history(page):
    """Remove everything the history adds to an existing page (the declared normalisation list)."""
    page = re.sub(r'<section class="nj-hist".*?</section>', "", page, flags=re.S)
    page = re.sub(r'<script type="application/ld\+json" id="ld-nj-history">.*?</script>', "", page, flags=re.S)
    page = re.sub(r' id="guide-teacher-\d{4}-\d\d"', "", page)
    return page


def table_rows(section):
    """{(year, group): (published_text, status_text)} from the data table."""
    out = {}
    for m in re.finditer(r'<tr data-year="([^"]+)" data-group="([^"]+)" data-status="([^"]+)">(.*?)</tr>', section, re.S):
        cells = [re.sub(r"<[^>]+>", "", c) for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", m.group(4), re.S)]
        out[(m.group(1), m.group(2))] = (m.group(3), cells)
    return out


def chart_data(section):
    """{(year, group): ('published', fte) | (status, None)} from the SVG panels and row lists."""
    out = {}
    for m in re.finditer(r'<circle class="dot"[^>]*data-year="([^"]+)" data-group="([^"]+)" data-fte="([^"]+)"', section):
        out[(m.group(1), m.group(2))] = ("published", m.group(3))
    for m in re.finditer(r'<text class="st \w+" data-year="([^"]+)" data-group="([^"]+)" data-status="([^"]+)"', section):
        out[(m.group(1), m.group(2))] = (m.group(3), None)
    for m in re.finditer(r'<li data-year="([^"]+)" data-group="([^"]+)" data-status="([^"]+)">(.*?)</li>', section, re.S):
        y, g, st, inner = m.groups()
        if st == "published":
            nums = re.findall(r'<span class="num">([^<]+)</span>', inner)
            out[(y, g)] = ("published", nums[-1].replace(",", ""))
        else:
            out[(y, g)] = (st, None)
    return out


def text_of(html_s):
    import html as _h
    return re.sub(r"\s+", " ", _h.unescape(re.sub(r"<[^>]+>", " ", html_s))).strip()
