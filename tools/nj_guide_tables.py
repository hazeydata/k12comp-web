"""PR #5 fix list, fix 1 (K12-SITE-NJ-HISTORY-001): mobile salary-guide tables keep their caption and say they scroll sideways.

At 336/390 px a guide table with several lanes scrolls sideways inside its `.table-wrap` region (leftover 7a). The table's
<caption> sat inside that scroller, so it was cut off ("Teacher salary guide, 2026-2...") and nothing said more columns exist.
This rewrites each guide table on the committed district pages (the 8 pages with `<section class="grid ...">`):

- The caption text moves, unchanged, into `<p class="guide-caption" id="guide-cap-N">` just above the scroller. The table
  keeps its accessible name through `aria-labelledby="guide-cap-N"` (N counts the guide tables on that page from 1).
  The region's `aria-label`, the heading, the source line, the note and every table cell are untouched.
- Tables with more than one lane column (3+ header cells) get `<p class="guide-cue" aria-hidden="true">SCROLL_CUE</p>` between
  the caption and the scroller. style.css shows it at <=640 px only. Step + one lane tables fit at 336 px and get no cue.

The history build still writes the old markup (from base 3b50ce10), so re-run --write after copying a fresh build in place;
tests/test_nj_history_committed.py allows exactly this rewrite on these pages and nothing more.
Idempotent: the tool first undoes its own markup, then applies it, so a second --write changes nothing and a new SCROLL_CUE
replaces the old one. To change the cue wording, edit SCROLL_CUE (one line), update its pin in tests/test_nj_guide_tables.py
and run --write.

    python3 tools/nj_guide_tables.py --check   # exit 1 if any guide page is not in the final form
    python3 tools/nj_guide_tables.py --write
"""
import argparse
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCROLL_CUE = "Swipe to see more columns →"  # approved copy (Lindsay); the only cue wording
CUE_MIN_HEADER_CELLS = 3  # Step + 2 lanes or more: these overflow at 336 and 390 px (checked in a real browser)

SECTION = re.compile(r'(<section class="grid [a-z]+">)(.*?)(</section>)', re.S)
# the build's markup: the region label and the caption carry the same text
OLD = re.compile(r'<div class="table-wrap" tabindex="0" role="region" aria-label="([^"<>]*)"><table><caption>([^<>]*)</caption>')
NEW = re.compile(r'<p class="guide-caption" id="guide-cap-(\d+)">([^<>]*)</p>(?:<p class="guide-cue" aria-hidden="true">[^<>]*</p>)?'
                 r'<div class="table-wrap" tabindex="0" role="region" aria-label="([^"<>]*)"><table aria-labelledby="guide-cap-\1">')


def undo(body):
    """One guide section's body back in the build's markup. Raises on anything else."""
    n_old, n_new = len(OLD.findall(body)), len(NEW.findall(body))
    if (n_old, n_new) == (1, 0):
        return body
    if (n_old, n_new) != (0, 1):
        raise ValueError(f"guide section has {n_old} build tables and {n_new} rewritten tables; expected exactly one table")
    m = NEW.search(body)
    if m.group(2) != m.group(3):
        raise ValueError(f"caption {m.group(2)!r} differs from the region label {m.group(3)!r}")
    return body[:m.start()] + f'<div class="table-wrap" tabindex="0" role="region" aria-label="{m.group(3)}"><table><caption>{m.group(2)}</caption>' + body[m.end():]


def rewrite(page):
    """The page with every guide table in the final form. Pages without guide tables come back unchanged."""
    count = 0

    def one(sec):
        nonlocal count
        body = undo(sec.group(2))
        m = OLD.search(body)
        label, caption = m.group(1), m.group(2)
        if label != caption:
            raise ValueError(f"caption {caption!r} differs from the region label {label!r}")
        count += 1
        cells = len(re.findall(r"<th scope=\"col\"", body[m.end():body.index("</thead>", m.end())]))
        cue = f'<p class="guide-cue" aria-hidden="true">{SCROLL_CUE}</p>' if cells >= CUE_MIN_HEADER_CELLS else ""
        new = (f'<p class="guide-caption" id="guide-cap-{count}">{caption}</p>{cue}'
               f'<div class="table-wrap" tabindex="0" role="region" aria-label="{label}"><table aria-labelledby="guide-cap-{count}">')
        return sec.group(1) + body[:m.start()] + new + body[m.end():] + sec.group(3)

    out = SECTION.sub(one, page)
    if 'id="guide-cap-' in SECTION.sub("", out):
        raise ValueError("guide caption markup outside a guide section")
    return out


def guide_pages(root=ROOT):
    pages = []
    for p in sorted(glob.glob(os.path.join(root, "nj", "*", "index.html"))):
        with open(p, encoding="utf-8", newline="") as f:
            if '<section class="grid ' in f.read():
                pages.append(p)
    return pages


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true")
    g.add_argument("--write", action="store_true")
    a = ap.parse_args(argv)
    stale, tables = [], 0
    pages = guide_pages()
    for p in pages:
        with open(p, encoding="utf-8", newline="") as f:
            cur = f.read()
        want = rewrite(cur)
        tables += len(NEW.findall(want))
        if want != cur:
            stale.append(os.path.relpath(p, ROOT))
            if a.write:
                with open(p, "w", encoding="utf-8", newline="") as f:
                    f.write(want)
    verb = "rewritten" if a.write else "stale"
    print(f"{len(pages)} guide pages, {tables} guide tables, {len(stale)} {verb}" + "".join(f"\n  {s}" for s in stale))
    return 1 if (a.check and stale) else 0


if __name__ == "__main__":
    sys.exit(main())
