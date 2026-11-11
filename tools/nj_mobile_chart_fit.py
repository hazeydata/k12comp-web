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
import math
import os
import re
import sys
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHARS = os.path.join(ROOT, "charts", "d")
EM = 0.62  # monospace advance as a share of the font size, slightly above JetBrains Mono / system monospace (0.60) to stay safe
VALUE_PX, TICK_PX = 14, 12  # font sizes from the SVG <style>: .v 14px bold, other text 12px
MARGIN, TICK_GAP, LIFT = 6, 6, 10
PLOT_BOTTOM = 256  # x-axis line at y=260; a label below its dot must stay above it
DISTRIBUTION = os.path.join(ROOT, "charts", "chart3-nj-salary-distribution-mobile.svg")  # the /nj/ histogram, also gated for text size
CONTENT_PX = (304, 358)  # rendered chart width at a 336 and a 390 px viewport (16 px page padding each side); spec D2
MIN_TEXT_PX = 12

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


def gated_files():
    """Every mobile SVG the effective-text gate measures: the district charts and the /nj/ distribution."""
    return files() + [DISTRIBUTION]


FONT_SIZE = re.compile(r"font-size\s*:\s*([\d.]+)px")
CSS_RULE = re.compile(r"([^{}]+)\{([^{}]*)\}")
TRANSFORM = re.compile(r"(\w+)\(([^)]*)\)")


def transform_scale(t):
    """Linear scale factor of an SVG transform list (translate and rotate keep it at 1)."""
    k = 1.0
    for op, args in TRANSFORM.findall(t or ""):
        a = [float(v) for v in re.split(r"[\s,]+", args.strip()) if v]
        if op == "scale":
            k *= math.sqrt(abs(a[0] * (a[1] if len(a) > 1 else a[0])))
        elif op == "matrix":
            k *= math.sqrt(abs(a[0] * a[3] - a[1] * a[2]))
        elif op not in ("translate", "rotate"):
            raise ValueError(f"unsupported transform {op}")
    return k


def text_sizes(svg):
    """(viewBox width, [(text, font size in viewBox units after ancestor transforms)]) for every non-empty text node.
    Font size cascade: inline style, then <style> rules (.class over element), then the font-size attribute, then the parent."""
    root = ET.fromstring(svg.encode())
    vb = root.get("viewBox")
    vb_w = float(vb.split()[2]) if vb else float(re.match(r"[\d.]+", root.get("width")).group(0))
    by_class, by_tag = {}, {}
    for st in root.iter("{http://www.w3.org/2000/svg}style"):
        for sels, decls in CSS_RULE.findall(st.text or ""):
            m = FONT_SIZE.search(decls)
            for sel in (x.strip() for x in sels.split(",")):
                if m and sel.startswith("."):
                    by_class[sel[1:]] = float(m.group(1))
                elif m and re.fullmatch(r"\w+", sel):
                    by_tag[sel] = float(m.group(1))
    out = []

    def walk(el, size, scale):
        tag = el.tag.split("}")[-1]
        m = FONT_SIZE.search(el.get("style", ""))
        cls = [by_class[c] for c in el.get("class", "").split() if c in by_class]
        attr = el.get("font-size")
        if m:
            size = float(m.group(1))
        elif cls:
            size = cls[-1]
        elif tag in by_tag:
            size = by_tag[tag]
        elif attr:
            size = float(attr.rstrip("px"))
        scale *= transform_scale(el.get("transform"))
        if tag in ("text", "tspan") and (el.text or "").strip():
            if size is None:
                raise ValueError(f"no font size for {el.text!r}")
            out.append((el.text, size * scale))
        for c in el:
            walk(c, size, scale)

    walk(root, None, 1.0)
    return vb_w, out


def small_text(svg):
    """[(content px, text, effective px)] for every text node under MIN_TEXT_PX at each CONTENT_PX width."""
    vb_w, sizes = text_sizes(svg)
    return [(w, t, u * w / vb_w) for w in CONTENT_PX for t, u in sizes if u * w / vb_w < MIN_TEXT_PX]


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
    small, nodes = [], {w: 0 for w in CONTENT_PX}
    for f in gated_files():
        with open(f, encoding="utf-8", newline="") as fh:
            s = small_text(fh.read())
        for w in CONTENT_PX:
            nodes[w] += sum(1 for x in s if x[0] == w)
        if s:
            small.append(f)
            lo = min(s, key=lambda x: x[2])
            counts = ", ".join(f"{sum(1 for x in s if x[0] == w)} at {w} px" for w in CONTENT_PX)
            print(f"{os.path.relpath(f, ROOT)}: text under {MIN_TEXT_PX} px: {counts} (smallest {lo[2]:.2f} px, {lo[1].strip()!r} at {lo[0]} px)")
    at = ", ".join(f"{nodes[w]} at {w} px" for w in CONTENT_PX)
    print(f"effective text: {len(gated_files())} mobile charts measured at {'/'.join(map(str, CONTENT_PX))} px content, "
          f"{len(small)} with text under {MIN_TEXT_PX} px; text nodes under {MIN_TEXT_PX} px: {at}")
    return 1 if bad or small else 0


if __name__ == "__main__":
    sys.exit(main())
