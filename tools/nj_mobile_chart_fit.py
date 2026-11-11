"""Leftover 7b (K12-SITE-NJ-HISTORY-001): fit the "Base salary by year" mobile charts (charts/d/<leaid>-mobile.svg) inside their 390 px box.

The redesign wrote these SVGs once (no generator in this repo), with the end-value label 8 px right of the last dot and an x-axis label
every other year plus the final year. At 336/390 px that clips an 8-character label ("$228,160" from x=326 runs past 390) and the
last two year labels overlap. This tool changes only those two things, and only where they misfit:
  - a value label whose estimated right edge passes the box (width - MARGIN) is right-aligned at width - MARGIN and lifted above its dot;
  - an x-axis year label that would overlap the final year's label is dropped (the final year stays; the alt text lists every year).
Lines, dots, gridlines, y-axis labels, alt text and the desktop SVGs are never touched. Re-running changes nothing (idempotent).

    python3 tools/nj_mobile_chart_fit.py --check   # exit 1 and list files that still misfit
    python3 tools/nj_mobile_chart_fit.py --write   # rewrite misfitting files in place
"""
import argparse
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHARS = os.path.join(ROOT, "charts", "d")
EM = 0.62  # monospace advance as a share of the font size, slightly above JetBrains Mono / system monospace (0.60) to stay safe
VALUE_PX, TICK_PX = 14, 12  # font sizes from the SVG <style>: .v 14px bold, other text 12px
MARGIN, TICK_GAP, LIFT = 6, 6, 10
PLOT_BOTTOM = 256  # x-axis line at y=260; a label below its dot must stay above it

SVG_W = re.compile(r'<svg[^>]*\bwidth="(\d+)"')
VALUE = re.compile(r'<text class="v" x="([\d.]+)" y="([\d.]+)"( text-anchor="end")?>([^<]*)</text>')
TICK = re.compile(r'<text x="([\d.]+)" y="284" text-anchor="middle">([^<]*)</text>')
DOT = re.compile(r'<circle cx="([\d.]+)" cy="([\d.]+)" r="4"')


def width_of(text, px):
    return len(text) * px * EM


def value_right_edge(x, anchor_end, text):
    return x if anchor_end else x + width_of(text, VALUE_PX)


def tick_overlaps(a, b):
    """True when two centred year labels (x, text) come closer than TICK_GAP."""
    return abs(b[0] - a[0]) < (width_of(a[1], TICK_PX) + width_of(b[1], TICK_PX)) / 2 + TICK_GAP


def problems(svg):
    """List of misfits in one mobile SVG (empty = fits)."""
    w = int(SVG_W.search(svg).group(1))
    out = []
    for m in VALUE.finditer(svg):
        if value_right_edge(float(m.group(1)), bool(m.group(3)), m.group(4)) > w - MARGIN + 0.01:
            out.append(f"value label {m.group(4)!r} runs past {w - MARGIN}")
    ticks = [(float(x), t) for x, t in TICK.findall(svg)]
    out += [f"year labels {a[1]} and {b[1]} overlap" for a, b in zip(ticks, ticks[1:]) if tick_overlaps(a, b)]
    return out


def fit(svg):
    """Return svg with misfitting value labels moved and colliding year labels dropped; everything else byte for byte."""
    w = int(SVG_W.search(svg).group(1))
    dots = [(float(x), float(y)) for x, y in DOT.findall(svg)]

    def move(m):
        x, y, end, text = float(m.group(1)), float(m.group(2)), bool(m.group(3)), m.group(4)
        if value_right_edge(x, end, text) <= w - MARGIN + 0.01:
            return m.group(0)
        # the dot this label belongs to: the one it was placed beside (label x = dot x + 8, baseline = dot y + 5)
        cx, cy = min(dots, key=lambda d: abs(d[0] + 8 - x) + abs(d[1] + 5 - y))
        prev = [d for d in dots if d[0] < cx]
        above, below = cy - LIFT, cy + LIFT + VALUE_PX
        # go to the side the incoming line is not on; above unless the line comes down into the dot (and there is room below the plot)
        from_above = bool(prev) and max(prev)[1] < cy
        ny = below if (from_above and below <= PLOT_BOTTOM) or above - VALUE_PX < 0 else above
        return f'<text class="v" x="{w - MARGIN:.1f}" y="{ny:.1f}" text-anchor="end">{text}</text>'

    svg = VALUE.sub(move, svg)
    ticks = [(m.group(0), float(m.group(1)), m.group(2)) for m in TICK.finditer(svg)]
    if len(ticks) >= 2:
        last = ticks[-1]
        keep, drop = [], set()
        for t in ticks[:-1]:
            if tick_overlaps((t[1], t[2]), (last[1], last[2])) or (keep and tick_overlaps((keep[-1][1], keep[-1][2]), (t[1], t[2]))):
                drop.add(t[0])
            else:
                keep.append(t)
        for d in drop:
            svg = svg.replace(d, "", 1)
    return svg


def files():
    return sorted(glob.glob(os.path.join(CHARS, "*-mobile.svg")))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true")
    g.add_argument("--write", action="store_true")
    a = ap.parse_args(argv)
    bad, changed = [], 0
    for f in files():
        with open(f, encoding="utf-8", newline="") as fh:
            svg = fh.read()
        if a.write:
            new = fit(svg)
            if new != svg:
                with open(f, "w", encoding="utf-8", newline="") as fh:
                    fh.write(new)
                changed += 1
            svg = new
        p = problems(svg)
        if p:
            bad.append((os.path.relpath(f, ROOT), p))
    for f, p in bad:
        print(f"{f}: {'; '.join(p)}")
    print(f"{len(files())} mobile charts, {changed} rewritten, {len(bad)} still misfit")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
