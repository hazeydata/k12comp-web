"""K12-INDEXING-001: tools/nj_indexing.py rewrote every district page, / and /nj/, regenerated sitemap.xml and added 21 county hubs after the
base commits other tests compare against. `undo(rel, text)` maps a current page back to its pre-ticket text (the tool's own strip functions:
breadcrumb, BreadcrumbList block, peer block, disambiguated title, "By county" list, /nj/ h1) so those comparisons stay exact.
`is_this_tickets_page_change(rel)` is true only when undoing gives web main 7e99b60e's bytes back. tests/test_k12_indexing.py checks the
markup itself."""
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import nj_indexing as I  # noqa: E402

BASE = "7e99b60ee83a606550ce9e353fef8fcb06047996"  # web main before K12-INDEXING-001
DISTRICT = re.compile(r"nj/[a-z0-9-]+-\d{7}/index\.html")
HUB = re.compile(r"nj/county/[a-z0-9-]+/index\.html")
SITEMAP = "sitemap.xml"  # regenerated; tests/test_k12_indexing.py pins it (base URLs + the 21 hubs, lastmod rule)
OWN_TESTS_AND_TOOLS = {"tools/nj_indexing.py", "tests/test_k12_indexing.py", "tests/k12_indexing_helpers.py", "docs/nj-indexing.md"}


def undo(rel, text):
    """The page without K12-INDEXING-001's markup (str or bytes in, same type out). Any other file comes back unchanged."""
    raw = isinstance(text, bytes)
    t = text.decode("utf-8") if raw else text
    if rel == "nj/index.html":
        t = I.strip_nj(t)
    elif rel == "index.html":
        t = I.strip_home(t)
    elif DISTRICT.fullmatch(rel):
        t = I.strip_district(t)
    return t.encode("utf-8") if raw else t


def at_base(rel):
    return subprocess.run(["git", "-C", ROOT, "show", f"{BASE}:{rel}"], capture_output=True, check=True).stdout


def is_this_tickets_page_change(rel):
    """True when the committed page differs from 7e99b60e by this ticket's markup only."""
    if not (rel in ("index.html", "nj/index.html") or DISTRICT.fullmatch(rel)):
        return False
    with open(os.path.join(ROOT, *rel.split("/")), "rb") as f:
        return undo(rel, f.read()) == at_base(rel)


# K12-INDEXING-001 (Ann's 304px fix): the one block added to history.css after the existing max-width:640px block
HIST_PANELS_BLOCK = "@media (max-width: 640px) {\n  .hist-panels { grid-template-columns: minmax(0, 1fr); }\n}\n"


def history_css_change_is_this_tickets_block_only():
    """True when the committed /history.css differs from 7e99b60e only by HIST_PANELS_BLOCK (undo gives the base bytes back)."""
    with open(os.path.join(ROOT, "history.css"), encoding="utf-8", newline="") as f:
        now = f.read()
    base = subprocess.run(["git", "-C", ROOT, "show", BASE + ":history.css"], capture_output=True, check=True).stdout.decode("utf-8")
    return now.count(HIST_PANELS_BLOCK) == 1 and now.replace(HIST_PANELS_BLOCK, "") == base
