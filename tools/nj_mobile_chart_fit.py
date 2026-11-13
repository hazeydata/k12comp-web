"""Mobile chart generator and gate (K12-CHART-MOBILE-TEXT-001, after leftover 7b of K12-SITE-NJ-HISTORY-001).

The mobile charts render at the page's content width (`figure.chart img{width:100%}`): 304 px at a 336 px viewport and 358 px at 390.
Text is legible only if every node is at least 12 CSS px there, where effective px = font units x ancestor transform scale x content width
/ viewBox width. Both in-scope mobile charts are therefore drawn in a 304-unit-wide viewBox (1 unit = 1 CSS px at 336) with text of 12 units
or more.

District "Base salary by year" charts (charts/d/<leaid>-mobile.svg). The redesign wrote them once with no generator; `--write` rebuilds
each from itself and its desktop twin (<leaid>-desktop.svg, read only):
  - every y coordinate (dots, lines, gridlines, y labels), every label text, the colours and the <style> block are kept byte for byte;
  - x is redrawn on a plot from x=PLOT_L to PLOT_R, with each dot at its true school-year position: linear in the start year over the axis
    range, which runs from the desktop's first to its last year slot. The desktop has one slot per source year, so where the source skips a
    year the desktop (unchanged) spaces the years unevenly; the mobile chart does not. Desktop dots map in order to mobile dots;
  - year labels follow one rule: the latest axis year, then every k-th year counting back from it, k the smallest whole step whose label
    pitch is at least one label width plus TICK_GAP. The labels are evenly spaced because the years are; the first year is labelled only
    when it falls on the step. The visible figcaption and the alt text list every year and value;
  - a value label takes the first spot, in a fixed order (`place_value`), that stays inside the plot, clears every dot, line and other
    value label, and is no nearer another dot than its own: 8 units right of its dot; else right-aligned at MOBILE_W - MARGIN, LIFT above
    or below the dot (the side the incoming line is not on first); then beside or left of the dot; then right-aligned further out.
    A dot before the last year slot has empty years to its right, so its label is never right-aligned at the edge: those spots become
    start-aligned NEAR (6) units right of the dot, above or below it;
  - a value label more than LEADER_OVER (20) units from its dot (nearest point of its box to the dot's centre) gets a leader: a #999,
    0.75-wide line, no arrowhead, from that nearest point to the dot's centre, drawn under the dots. Nearer labels get none.
    `--check` fails on any label that covers a mark or sits nearer another dot, on a missing, extra or misplaced leader, and on a label
    right-aligned past a dot that is not at the last year slot.
NJ distribution (charts/chart3-nj-salary-distribution-mobile.svg, matplotlib output, no generator in this repo): `--write` reflows the
original once (a file already in the 304-unit viewBox is left alone). Title, subtitle and source note keep their words verbatim and are
rewrapped at 13 (title, bold) and 12 units; tick, axis and note labels become 12 units; the two outlier notes move clear of the stems
(OUTLIERS). "Hampton Twp / $56,225" goes one word per line over the low tail it names, below the "20" tick row and clear of it.
The plot (stems, dots, median line, spines, ticks) is only translated, by DIST_DX/dy, never scaled or moved relative to itself.
Header: the 4-unit top headroom header of tools/nj_chart_label_edge.py is read and written back as found (old header in, old header out), so
running this tool after that one changes nothing.
Desktop SVGs are never touched by this tool (tools/nj_fte_marks.py writes their marker). Re-running `--write` changes nothing (idempotent).

Part-time marker, key and line rule (K12-FTE-PRESENTATION-001; the 44 districts with a dot whose `ufb_fte` is below 1 and whose salary is
reported; the other 529 charts are byte-unchanged). tools/nj_fte_marks.py writes the marker into each desktop chart from the committed
api/v1/nj/<leaid>.json; `--write` here carries it to the mobile twin, and the helpers below (`cut_lines`, `place_key`) are the one rule both
tools use:
  - a part-time dot is hollow: `<circle cx cy r="4" fill="#fff" stroke="#458699" stroke-width="1.5" class="pt" data-fte="0.2"/>`, data-fte
    the published `ufb_fte` string; it keeps the dot's coordinates. Desktop dot i is mobile dot i, so `--write` copies its class and data-fte;
  - a line segment survives only between two full-time dots or two part-time dots with the same numeric FTE ("0" equals "0.0"), so a slope
    never reads as a pay cut. Point strings are kept byte for byte and only split; a run of one point draws no polyline. Value labels are then
    re-placed by `place_value` against the re-cut lines (the same rule as above);
  - one key, the last two elements: a hollow dot and the text `Part-time` (`Under 1.0 FTE` when any marked dot is FTE 0 or 0.0), 12 px from
    the chart's text rule. `place_key` takes the first of KEY_SPOTS (above the plot left, right, centre, then inside the plot) whose box,
    grown by the spot's pad, clears every dot, line, leader and value label and stays between PLOT_L and PLOT_R. It is placed in this chart's
    own coordinates after the value labels. A chart with no part-time dot has no key.
`--check` also fails on: a part-time dot whose data-fte is not that year's FTE<1 reported row in the committed JSON, a missing or extra mark,
a segment joining dots the line rule separates, a key that is missing, extra, mislabelled, within its pads or outside the plot, and a key on a
chart with no part-time dot.

    python3 tools/nj_mobile_chart_fit.py --check   # exit 1 on any misfit or any text node under 12 px at 304 or 358 px content
    python3 tools/nj_mobile_chart_fit.py --write   # regenerate the mobile charts in place, then check
"""
import argparse
import glob
import json
import math
import os
import re
import sys
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHARS = os.path.join(ROOT, "charts", "d")
EM = 0.62  # monospace advance as a share of the font size, slightly above JetBrains Mono / system monospace (0.60) to stay safe
VALUE_PX, TICK_PX = 14, 12  # font sizes from the SVG <style>: .v 14px bold, other text 12px
MOBILE_W = 304  # viewBox width of the mobile charts: the content width at a 336 px viewport
PLOT_L, PLOT_R = 48, 272  # first and last year of the axis; PLOT_R + half a year label + MARGIN stays inside MOBILE_W
YLABEL_X = PLOT_L - 8
MARGIN, TICK_GAP, LIFT = 6, 6, 10
NEAR = 6  # a label beside a dot that is not at the last year slot starts this far right of it (above or below; level is x + 8)
LEADER_OVER = 20  # a value label farther than this from its dot gets a leader line
LEADER = 'stroke="#999" stroke-width="0.75"'
PLOT_BOTTOM = 256  # x-axis line at y=260; a label below its dot must stay above it
DISTRIBUTION = os.path.join(ROOT, "charts", "chart3-nj-salary-distribution-mobile.svg")  # the /nj/ histogram, also gated for text size
CONTENT_PX = (304, 358)  # rendered chart width at a 336 and a 390 px viewport (16 px page padding each side); spec D2
MIN_TEXT_PX = 12

SVG_W = re.compile(r'<svg[^>]*\bwidth="(\d+)"')
VALUE = re.compile(r'<text class="v" x="([\d.]+)" y="([\d.]+)"( text-anchor="end")?>([^<]*)</text>')
TICK = re.compile(r'<text x="([\d.]+)" y="284" text-anchor="middle">([^<]*)</text>')
DOT = re.compile(r'<circle cx="([\d.]+)" cy="([\d.]+)" r="4"')  # both dot forms: full-time and part-time (hollow)
YLABEL = re.compile(r'<text x="([\d.]+)" y="[\d.]+" text-anchor="end">([^<]*)</text>')
FT_ATTRS = r'fill="#458699"'
PT_ATTRS = r'fill="#fff" stroke="#458699" stroke-width="1\.5" class="pt" data-fte="0(?:\.\d+)?"'
KEY_RE = (r'<circle class="key" cx="[\d.]+" cy="[\d.]+" r="4" fill="#fff" stroke="#458699" stroke-width="1\.5"/>'
          r'<text class="key" x="[\d.]+" y="[\d.]+">(?:Part-time|Under 1\.0 FTE)</text>')
# One district mobile SVG, start to end; every part is captured so nothing can be lost on a rewrite.
OLD_HEADER = ('<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="300" viewBox="0 0 {w} 300" role="img">'
              '<rect width="{w}" height="300" fill="#ffffff"/>')
# K12-CHART-LABEL-EDGE-001: tools/nj_chart_label_edge.py adds 4 units of top headroom to the header. This tool reads either header and
# writes back the one it found, so it is a no-op after that tool and still works on a fresh (old header) history build.
HEADROOM_HEADER = ('<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="304" viewBox="0 -4 {w} 304" role="img">'
                   '<rect y="-4" width="{w}" height="304" fill="#ffffff"/>')
DISTRICT = re.compile(
    r'(?P<head><svg xmlns="http://www.w3.org/2000/svg" width="\d+" height="300" viewBox="0 0 \d+ 300" role="img"><rect width="\d+" height="300" fill="#ffffff"/>'
    r'|<svg xmlns="http://www.w3.org/2000/svg" width="\d+" height="304" viewBox="0 -4 \d+ 304" role="img"><rect y="-4" width="\d+" height="304" fill="#ffffff"/>)'
    r'(?P<style><style>[^<]*</style>)'
    r'(?P<grid>(?:<line x1="[\d.]+" x2="[\d.]+" y1="[\d.]+" y2="[\d.]+" stroke="#e3e6ea"/><text x="[\d.]+" y="[\d.]+" text-anchor="end">[^<]*</text>)*)'
    r'<line x1="[\d.]+" x2="[\d.]+" y1="260" y2="260" stroke="#999999"/>'
    r'(?P<ticks>(?:<text x="[\d.]+" y="284" text-anchor="middle">[^<]*</text>)*)'
    r'(?P<lines>(?:<polyline fill="none" stroke="#458699" stroke-width="3" points="[^"]*"/>)*)'
    r'(?P<leaders>(?:<line x1="[\d.]+" y1="[\d.]+" x2="[\d.]+" y2="[\d.]+" ' + LEADER + r'/>)*)'
    r'(?P<dots>(?:<circle cx="[\d.]+" cy="[\d.]+" r="4" (?:' + FT_ATTRS + '|' + PT_ATTRS + r')/>)*)'
    r'(?P<values>(?:<text class="v" x="[\d.]+" y="[\d.]+"(?: text-anchor="end")?>[^<]*</text>)*)'
    r'(?P<key>(?:' + KEY_RE + r')?)</svg>\Z')
GRID = re.compile(r'<line x1="[\d.]+" x2="[\d.]+" y1="([\d.]+)" y2="([\d.]+)" stroke="#e3e6ea"/><text x="[\d.]+" y="([\d.]+)" text-anchor="end">([^<]*)</text>')
POLYLINE = re.compile(r'points="([^"]*)"')
DESKTOP_TICK = re.compile(r'<text x="([\d.]+)" y="304" text-anchor="middle">(\d{4})-\d\d</text>')
DESKTOP_DOT = re.compile(r'<circle cx="([\d.]+)" cy="([\d.]+)" r="4"')
DOT_FTE = re.compile(r'<circle cx="([\d.]+)" cy="([\d.]+)" r="4" (?:' + FT_ATTRS + r'|fill="#fff" stroke="#458699" stroke-width="1\.5" class="pt" data-fte="([^"]*)")/>')
KEY_PARTS = re.compile(r'<circle class="key" cx="([\d.]+)" cy="([\d.]+)" r="4" fill="#fff" stroke="#458699" stroke-width="1\.5"/>'
                       r'<text class="key" x="([\d.]+)" y="([\d.]+)">(Part-time|Under 1\.0 FTE)</text>')
LEADER_LINE = re.compile(r'<line x1="([\d.]+)" y1="([\d.]+)" x2="([\d.]+)" y2="([\d.]+)" ' + LEADER + r'/>')
DESKTOP_VALUE = re.compile(r'<text class="v" x="([\d.]+)" y="([\d.]+)"(?: text-anchor="end")?>([^<]*)</text>')


def width_of(text, px):
    return len(text) * px * EM


def value_right_edge(x, anchor_end, text):
    return x if anchor_end else x + width_of(text, VALUE_PX)


def tick_overlaps(a, b):
    """True when two centred year labels (x, text) come closer than TICK_GAP."""
    return abs(b[0] - a[0]) < (width_of(a[1], TICK_PX) + width_of(b[1], TICK_PX)) / 2 + TICK_GAP


def school_year(y):
    return f"{y}-{(y + 1) % 100:02d}"


def year_labels(first, last):
    """The year-label rule: the latest year, then every k-th year back from it (k the smallest step that keeps labels TICK_GAP apart)."""
    if last == first:
        return [first]
    pitch = (PLOT_R - PLOT_L) / (last - first)
    k = math.ceil((width_of(school_year(last), TICK_PX) + TICK_GAP) / pitch - 1e-9)
    return list(range(last, first - 1, -k))[::-1]


def problems(svg, desktop=None, ftes=None):
    """List of misfits in one district mobile SVG (empty = fits). With its desktop twin, also checks each value label is nearest its own dot.
    With `ftes` (the expected mark per dot from the committed JSON, see expected_ftes), also checks every dot's part-time mark. The marker,
    line rule and key (marker_problems) are always checked."""
    w = int(SVG_W.search(svg).group(1))
    out = [] if w == MOBILE_W else [f"width {w}, not {MOBILE_W}"]
    values = []
    for m in VALUE.finditer(svg):
        x, end, text = float(m.group(1)), bool(m.group(3)), m.group(4)
        right = value_right_edge(x, end, text)
        if right > w - MARGIN + 0.01:
            out.append(f"value label {text!r} runs past {w - MARGIN}")
        values.append((right - width_of(text, VALUE_PX), float(m.group(2)), right, text))
    out += [f"value labels {a[3]} and {b[3]} overlap" for i, a in enumerate(values) for b in values[i + 1:]
            if a[0] < b[2] and b[0] < a[2] and abs(a[1] - b[1]) < VALUE_PX]
    dots = [(float(x), float(y)) for x, y in DOT.findall(svg)]
    segments = polyline_segments(svg)
    for m in VALUE.finditer(svg):
        if covers_marks(value_box(float(m.group(1)), bool(m.group(3)), float(m.group(2)), m.group(4)), dots, segments, [], 1):
            out.append(f"value label {m.group(4)!r} covers a dot or line")
        if float(m.group(2)) > PLOT_BOTTOM or float(m.group(2)) < VALUE_PX:
            out.append(f"value label {m.group(4)!r} leaves the plot")
    if desktop is not None:
        leaders = []
        for (_, owner), m in zip(value_owners(desktop), VALUE.finditer(svg)):
            box = value_box(float(m.group(1)), bool(m.group(3)), float(m.group(2)), m.group(4))
            if nearer_dot(box, dots[owner], dots):
                out.append(f"value label {m.group(4)!r} sits nearer another dot than its own")
            if box_distance(box, dots[owner]) > LEADER_OVER:
                leaders.append(leader(box, dots[owner]))
            if dots[owner][0] < PLOT_R - 0.5 and m.group(3) and float(m.group(1)) > dots[owner][0]:
                out.append(f"value label {m.group(4)!r} is right-aligned over the empty years after its dot")
        if LEADER_LINE.findall(svg) != [LEADER_LINE.match(ln).groups() for ln in leaders]:
            out.append(f"leader lines do not match the value labels more than {LEADER_OVER} units from their dot")
    ticks = [(float(x), t) for x, t in TICK.findall(svg)]
    out += [f"year labels {a[1]} and {b[1]} overlap" for a, b in zip(ticks, ticks[1:]) if tick_overlaps(a, b)]
    out += [f"year label {t} runs past the edge" for x, t in ticks if x - width_of(t, TICK_PX) / 2 < 0 or x + width_of(t, TICK_PX) / 2 > w]
    out += [f"y label {t} runs past the left edge" for x, t in YLABEL.findall(svg) if float(x) - width_of(t, TICK_PX) < 0]
    return out + marker_problems(svg, "mobile", ftes)


def value_box(x, anchor_end, y, text):
    """Estimated ink box (left, top, right, bottom) of a value label."""
    left = x - width_of(text, VALUE_PX) if anchor_end else x
    return left, y - 0.75 * VALUE_PX, left + width_of(text, VALUE_PX), y + 0.25 * VALUE_PX


def segment_hits(p, q, box):
    """True when the segment p-q touches the box (Liang-Barsky clip)."""
    t0, t1 = 0.0, 1.0
    dx, dy = q[0] - p[0], q[1] - p[1]
    for d, lo, hi in ((dx, box[0] - p[0], box[2] - p[0]), (dy, box[1] - p[1], box[3] - p[1])):
        if d == 0:
            if lo > 0 or hi < 0:
                return False
            continue
        a, b = sorted((lo / d, hi / d))
        t0, t1 = max(t0, a), min(t1, b)
        if t0 > t1:
            return False
    return True


def covers_marks(box, dots, segments, labels, pad):
    """True when a label box, grown by pad, touches a dot (r=4), a line segment or another label box."""
    b = (box[0] - pad, box[1] - pad, box[2] + pad, box[3] + pad)
    return (any(b[0] - 4 <= x <= b[2] + 4 and b[1] - 4 <= y <= b[3] + 4 for x, y in dots)
            or any(segment_hits(p, q, b) for p, q in segments)
            or any(b[0] < o[2] and o[0] < b[2] and b[1] < o[3] and o[1] < b[3] for o in labels))


def polyline_segments(svg):
    out = []
    for pts in POLYLINE.findall(svg):
        p = [tuple(map(float, q.split(","))) for q in pts.split()]
        out += list(zip(p, p[1:]))
    return out


def place_value(text, dot, dots, segments, placed):
    """(x, anchor_end, baseline) of a value label: the first candidate inside the plot that clears every dot, line and earlier label.
    Order: beside the dot (x + 8); right-aligned at MOBILE_W - MARGIN, LIFT above the dot, then below it (below first when the line comes
    down into the dot); beside, above then below; left of the dot (x - 8), level, above, below; then right-aligned, 4 units further out each
    try, above and below in turn. A dot before the last year slot (PLOT_R) has empty years to its right, so its label is never right-aligned
    at the edge: every right-aligned try becomes start-aligned NEAR units right of the dot. A candidate also has to be nearer its own dot
    than any other dot. If nothing qualifies, the first candidate inside the plot (the gate then reports the collision)."""
    cx, cy = dot
    prev = [d for d in dots if d[0] < cx]
    above, below = cy - LIFT, cy + LIFT + VALUE_PX
    side = (MOBILE_W - MARGIN, True) if cx >= PLOT_R - 0.5 else (cx + NEAR, False)
    right = [(*side, above), (*side, below)]
    if bool(prev) and max(prev)[1] < cy:
        right.reverse()
    tries = ([(cx + 8, False, cy + 5)] + right + [(cx + 8, False, above), (cx + 8, False, below)]
             + [(cx - 8, True, y) for y in (cy + 5, above, below)])
    for k in range(1, 40):
        tries += [(*side, above - 4 * k), (*side, below + 4 * k)]
    inside = [t for t in tries if t[2] >= VALUE_PX and t[2] <= PLOT_BOTTOM and value_box(*t, text)[0] >= 0
              and value_box(*t, text)[2] <= MOBILE_W - MARGIN + 0.01]
    for t in inside:
        box = value_box(*t, text)
        if not covers_marks(box, dots, segments, placed, 2) and not nearer_dot(box, dot, dots):
            return t
    return inside[0]


def box_distance(box, dot):
    """Distance from a dot's centre to the nearest point of a label box (0 inside it)."""
    return math.hypot(max(box[0] - dot[0], 0, dot[0] - box[2]), max(box[1] - dot[1], 0, dot[1] - box[3]))


def nearer_dot(box, own, dots):
    """True when another dot is nearer the label box than its own dot (by more than half a unit; equal values tie), so a label never
    reads as another point's."""
    return any(box_distance(box, d) < box_distance(box, own) - 0.5 for d in dots)


def leader(box, dot):
    """Leader line from the point of the label box nearest the dot to the dot's centre; drawn under the dots, so it shows from the label
    edge to the dot's rim."""
    x, y = min(max(dot[0], box[0]), box[2]), min(max(dot[1], box[1]), box[3])
    return f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{dot[0]:.1f}" y2="{dot[1]:.1f}" {LEADER}/>'


def value_owners(desktop):
    """[(label text, index of its dot)] in order: each desktop value label sits beside its dot (x = dot x + 8, baseline = dot y + 5), or,
    when the axis rule of tools/nj_chart_label_edge.py lifted it, LIFT above it (baseline = dot y - LIFT)."""
    dots = [(float(x), float(y)) for x, y in DESKTOP_DOT.findall(desktop)]
    return [(text, min(range(len(dots)), key=lambda j: abs(dots[j][0] + 8 - float(vx)) + min(abs(dots[j][1] + 5 - float(vy)), abs(dots[j][1] - LIFT - float(vy)))))
            for vx, vy, text in DESKTOP_VALUE.findall(desktop)]


def years_of_dots(desktop):
    """Start year of each dot, in order, from the desktop twin: each desktop dot sits on one labelled year slot."""
    slots = {x: int(y) for x, y in DESKTOP_TICK.findall(desktop)}
    return [slots[x] for x, _ in DESKTOP_DOT.findall(desktop)], min(slots.values()), max(slots.values())


# --- part-time marker, line rule and key (K12-FTE-PRESENTATION-001; shared with tools/nj_fte_marks.py) -----------------------------------
PT_DOT = '<circle cx="{x}" cy="{y}" r="4" fill="#fff" stroke="#458699" stroke-width="1.5" class="pt" data-fte="{f}"/>'
FT_DOT = '<circle cx="{x}" cy="{y}" r="4" fill="#458699"/>'
# `class` comes first on both key elements, so DOT, DESKTOP_DOT, TICK and YLABEL (which start `<circle cx=` / `<text x=`) never read the
# key as a data dot or an axis label
KEY = ('<circle class="key" cx="{dx:.1f}" cy="{dy:.1f}" r="4" fill="#fff" stroke="#458699" stroke-width="1.5"/>'
       '<text class="key" x="{tx:.1f}" y="{ty:.1f}">{label}</text>')
KEY_LABEL, KEY_LABEL_ZERO = "Part-time", "Under 1.0 FTE"  # the second when any marked dot is FTE 0 or 0.0
KEY_PX, KEY_GAP = 12, 8  # key text size (the 12 px text rule); key dot centre to text start
INK_R = 4.75  # ink radius of either dot form (hollow: r 4 plus half of the 1.5 stroke)
GEOM = {"desktop": dict(l=64, r=1024, top=24, axis=280), "mobile": dict(l=PLOT_L, r=PLOT_R, top=24, axis=260)}  # plot edges and gridline/axis y
# Key spots in order: key dot centre x as an offset from the plot edge, y from the top gridline or the x-axis, and the pad. The band above the
# top gridline comes first (clear of the data); inside the plot a key needs a wider pad, so it never sits under a line and reads as its label.
KEY_SPOTS = (("above plot, left", "l", 4.75, "top", -16, 6), ("above plot, right", "r", 0, "top", -16, 6),
             ("above plot, centre", "c", 0, "top", -16, 6), ("top-left", "l", 10, "top", 16, 10), ("top-right", "r", -10, "top", 16, 10),
             ("bottom-right", "r", -10, "axis", -16, 10), ("bottom-left", "l", 10, "axis", -16, 10))


def joined(a, b):
    """True when a line may join two dots. Each is None (full-time) or its published FTE string: two full-time dots join, two part-time
    dots join when the FTE is the same number ("0" equals "0.0"), a part-time and a full-time dot never do."""
    if a is None or b is None:
        return a is None and b is None
    return float(a) == float(b)


def cut_lines(polylines, index, ftes):
    """Polyline point strings re-cut by `joined`. `polylines` are the points="..." values, `index` maps a point string "x,y" to its dot's
    index in `ftes`. Point strings are only split, never changed; a run of one point is dropped. Returns (new strings, segments removed)."""
    out, removed = [], 0
    for pts in polylines:
        ps = pts.split()
        run = [ps[0]]
        for p, q in zip(ps, ps[1:]):
            if joined(ftes[index[p]], ftes[index[q]]):
                run.append(q)
            else:
                removed += 1
                if len(run) > 1:
                    out.append(" ".join(run))
                run = [q]
        if len(run) > 1:
            out.append(" ".join(run))
    return out, removed


def key_label(ftes):
    """`Under 1.0 FTE` when any marked dot is FTE 0 or 0.0, else `Part-time`."""
    return KEY_LABEL_ZERO if any(f is not None and float(f) == 0 for f in ftes) else KEY_LABEL


def key_box(dx, dy, label):
    """Ink box of a key: its dot and its text box (EM advance)."""
    return (dx - INK_R, min(dy - INK_R, dy + 4 - 0.75 * KEY_PX), dx + KEY_GAP + width_of(label, KEY_PX), max(dy + INK_R, dy + 4 + 0.25 * KEY_PX))


def key_clear(kind, label, dx, dy, pad, dots, segments, boxes, leaders):
    """True when the key at (dx, dy), its box grown by pad, clears every dot (ink), line (plus its half width), leader and value-label box
    and stays between the plot edges."""
    g = GEOM[kind]
    b = key_box(dx, dy, label)
    bb = (b[0] - pad, b[1] - pad, b[2] + pad, b[3] + pad)
    bl = (bb[0] - 1.5, bb[1] - 1.5, bb[2] + 1.5, bb[3] + 1.5)
    return not (any(bb[0] - INK_R <= x <= bb[2] + INK_R and bb[1] - INK_R <= y <= bb[3] + INK_R for x, y in dots)
                or any(segment_hits(a, c, bl) for a, c in segments)
                or any(segment_hits(a, c, bb) for a, c in leaders)
                or any(bb[0] < o[2] and o[0] < bb[2] and bb[1] < o[3] and o[1] < bb[3] for o in boxes)
                or b[0] < g["l"] or b[2] > g["r"])


def place_key(kind, label, dots, segments, boxes, leaders):
    """(spot name, dot centre x, dot centre y) of the first KEY_SPOTS spot where the key is clear (`key_clear`)."""
    g = GEOM[kind]
    kw = KEY_GAP + width_of(label, KEY_PX)
    for name, edge, off, base, dyo, pad in KEY_SPOTS:
        dx = {"l": g["l"] + off, "r": g["r"] + off - kw, "c": (g["l"] + g["r"]) / 2 - kw / 2}[edge]
        dy = g[base] + dyo
        if key_clear(kind, label, dx, dy, pad, dots, segments, boxes, leaders):
            return name, dx, dy
    raise ValueError(f"no key spot for {label!r}")


def key_svg(dx, dy, label):
    return KEY.format(dx=dx, dy=dy, tx=dx + KEY_GAP, ty=dy + 4, label=label)


def segment_list(polylines):
    out = []
    for pts in polylines:
        p = [tuple(map(float, q.split(","))) for q in pts.split()]
        out += list(zip(p, p[1:]))
    return out


def dot_ftes(svg):
    """[None (full-time) or the data-fte string] per dot, in order, from a chart carrying either dot form."""
    return [f or None for _, _, f in DOT_FTE.findall(svg)]


def load_rows(leaid):
    """The superintendent rows of the committed api/v1/nj/<leaid>.json, in file order."""
    with open(os.path.join(ROOT, "api", "v1", "nj", f"{leaid}.json"), encoding="utf-8") as fh:
        return json.load(fh)["superintendent_contracts"]


def marked_fte(row):
    """The row's `ufb_fte` string when it is part-time and plotted (float(ufb_fte) < 1 and a reported salary), else None."""
    return row["ufb_fte"] if float(row["ufb_fte"]) < 1 and not row["salary_not_reported"] else None


def expected_ftes(desktop, rows):
    """[None or FTE string] per desktop dot, from the committed JSON rows: the dot on year slot Y that is the k-th on that slot is the k-th
    reported row of Y in file order. Raises ValueError when the chart and the rows disagree."""
    slots = {x: y for x, y in re.findall(r'<text x="([\d.]+)" y="304" text-anchor="middle">(\d{4}-\d\d)</text>', desktop)}
    by = {}
    for r in rows:
        if not r["salary_not_reported"]:
            by.setdefault(r["school_year"], []).append(marked_fte(r))
    out, seen = [], {}
    for x, _ in DESKTOP_DOT.findall(desktop):
        year = slots.get(x)
        k = seen.get(year, 0)
        seen[year] = k + 1
        if year not in by or k >= len(by[year]):
            raise ValueError(f"dot at x={x} (year {year}) has no reported row in the JSON")
        out.append(by[year][k])
    if seen != {y: len(v) for y, v in by.items()}:
        raise ValueError("the chart's dots and the JSON's reported rows differ")
    return out


def marker_problems(svg, kind, ftes=None):
    """Misfits of the part-time marker, line rule and key in one chart (desktop or mobile). With `ftes` (expected, per dot, from the
    JSON) also checks every dot's mark and data-fte against its row."""
    dots_full = DOT_FTE.findall(svg)
    flags = [f or None for _, _, f in dots_full]
    out = []
    if ftes is not None:
        if len(ftes) != len(flags):
            out.append(f"{len(flags)} dots but {len(ftes)} reported rows")
        else:
            for i, (have, want) in enumerate(zip(flags, ftes)):
                if have != want:
                    out.append(f"dot {i + 1} is {'marked part-time, data-fte ' + have if have else 'not marked'} but its row is "
                               f"{'part-time, ' + want + ' FTE' if want else 'full-time or not plotted'}")
    index = {}
    for i, (x, y, _) in reversed(list(enumerate(dots_full))):
        index[f"{x},{y}"] = i
    for pts in POLYLINE.findall(svg):
        ps = pts.split()
        out += [f"a line segment joins dots {index[p] + 1} and {index[q] + 1} that the FTE rule separates" for p, q in zip(ps, ps[1:])
                if p in index and q in index and not joined(flags[index[p]], flags[index[q]])]
    keys = KEY_PARTS.findall(svg)
    if svg.count('class="key"') != 2 * len(keys):
        out.append("key markup is not the approved key")
    if len(keys) > 1:
        out.append(f"{len(keys)} keys, expected one")
    if not any(flags):
        if keys:
            out.append("a key on a chart with no part-time dot")
        return out
    if not keys:
        return out + ["a part-time dot but no key"]
    cx, cy, tx, ty, label = keys[0]
    dx, dy = float(cx), float(cy)
    if label != key_label(flags):
        out.append(f"key reads {label!r}, expected {key_label(flags)!r}")
    if abs(float(tx) - (dx + KEY_GAP)) > 0.11 or abs(float(ty) - (dy + 4)) > 0.11:
        out.append("key text is not beside its dot")
    dots = [(float(x), float(y)) for x, y, _ in dots_full]
    boxes = [value_box(float(m.group(1)), bool(m.group(3)), float(m.group(2)), m.group(4)) for m in VALUE.finditer(svg)]
    leaders = [tuple(map(float, m)) for m in LEADER_LINE.findall(svg)]
    g = GEOM[kind]
    pad = 6 if dy < g["top"] else 10
    if not key_clear(kind, label, dx, dy, pad, dots, segment_list(POLYLINE.findall(svg)), boxes, [((a, b), (c, d)) for a, b, c, d in leaders]):
        out.append(f"key is within {pad} units of a dot, line, leader or value label, or outside the plot")
    return out


def fit(svg, desktop):
    """The district mobile SVG redrawn in the MOBILE_W viewBox (see the module docstring). Pure: same input, same output."""
    m = DISTRICT.match(svg)
    if not m:
        raise ValueError("unexpected district mobile SVG structure")
    years, first, last = years_of_dots(desktop)
    old_dots = DOT.findall(m.group("dots"))
    if len(old_dots) != len(years):
        raise ValueError("mobile and desktop dot counts differ")
    ftes = dot_ftes(desktop)  # the desktop dot's mark (None or its FTE) goes to mobile dot i
    if len(ftes) != len(old_dots):
        raise ValueError("mobile and desktop dot counts differ")

    def x_of(year):
        return PLOT_L + (year - first) * (PLOT_R - PLOT_L) / (last - first) if last > first else (PLOT_L + PLOT_R) / 2

    new_x = [f"{x_of(y):.1f}" for y in years]
    where = {d: i for i, d in reversed(list(enumerate(old_dots)))}  # (cx, cy) as written -> first dot index
    dots = [(float(new_x[i]), float(cy)) for i, (_, cy) in enumerate(old_dots)]

    header = HEADROOM_HEADER if m.group("head").startswith('<svg xmlns="http://www.w3.org/2000/svg" width="304" height="304"') else OLD_HEADER
    out = [header.format(w=MOBILE_W), m.group("style")]
    for y1, y2, ty, label in GRID.findall(m.group("grid")):
        out.append(f'<line x1="{PLOT_L}" x2="{PLOT_R}" y1="{y1}" y2="{y2}" stroke="#e3e6ea"/><text x="{YLABEL_X}" y="{ty}" text-anchor="end">{label}</text>')
    out.append(f'<line x1="{PLOT_L}" x2="{PLOT_R}" y1="260" y2="260" stroke="#999999"/>')
    out += [f'<text x="{x_of(y):.1f}" y="284" text-anchor="middle">{school_year(y)}</text>' for y in year_labels(first, last)]
    moved_lines, index = [], {}
    for pts in POLYLINE.findall(m.group("lines")):
        moved = []
        for p in pts.split():
            cx, cy = p.split(",")
            moved.append(f"{new_x[where[(cx, cy)]]},{cy}")
            index[moved[-1]] = where[(cx, cy)]
        moved_lines.append(" ".join(moved))
    for pts in cut_lines(moved_lines, index, ftes)[0]:
        out.append(f'<polyline fill="none" stroke="#458699" stroke-width="3" points="{pts}"/>')

    values = value_owners(desktop)
    if [v[0] for v in values] != [v[3] for v in VALUE.findall(m.group("values"))]:
        raise ValueError("mobile and desktop value labels differ")
    segments = [seg for pl in out if pl.startswith("<polyline") for seg in polyline_segments(pl)]
    placed, labels, leaders = [], [], []
    for text, i in values:
        x, end, y = place_value(text, dots[i], dots, segments, placed)
        x, y = round(x, 1), round(y, 1)  # as written, so the leader meets the label the gate reads back
        placed.append(value_box(x, end, y, text))
        if box_distance(placed[-1], dots[i]) > LEADER_OVER:
            leaders.append(leader(placed[-1], dots[i]))
        labels.append(f'<text class="v" x="{x:.1f}" y="{y:.1f}" text-anchor="end">{text}</text>' if end else f'<text class="v" x="{x:.1f}" y="{y:.1f}">{text}</text>')
    out += leaders  # under the dots, over the line
    out += [(PT_DOT if ftes[i] is not None else FT_DOT).format(x=new_x[i], y=cy, f=ftes[i]) for i, (_, cy) in enumerate(old_dots)]
    out += labels
    if any(f is not None for f in ftes):  # the key goes last, placed in this chart's own coordinates around the value labels and leaders
        label = key_label(ftes)
        leader_segments = [((a[0], a[1]), (a[2], a[3])) for a in (tuple(map(float, LEADER_LINE.match(ln).groups())) for ln in leaders)]
        _, dx, dy = place_key("mobile", label, dots, segments, placed, leader_segments)
        out.append(key_svg(dx, dy, label))
    return "".join(out) + "</svg>"


# --- NJ distribution (matplotlib) -------------------------------------------------------------------------------------------------
DIST_DX = 8  # plot shift right, so the y-axis title clears the tick labels and "$350k" clears the right edge
DIST_X = 12  # left edge of the title, subtitle and source note
DIST_WRAP = MOBILE_W - 2 * DIST_X
DIST_EM = 0.6  # Space Grotesk / fallback sans advance, rounded up
TITLE_PX, NOTE_PX = 13, 12  # title (bold); every other text node
TITLE_STEP, NOTE_STEP = 17, 15.5  # baseline to baseline
ORIGINAL_VIEWBOX = 'width="280.8pt" height="374.4pt" viewBox="0 0 280.8 374.4"'
PLOT_TOP, AXIS_Y = 128.0512, 299.52  # matplotlib's axes box, in the plot's own coordinates (kept)
GROUP_TEXT = re.compile(r'(<g id="(text_1[1-5])">\n)(.*?)(\n {2,3}</g>)', re.S)
LINE_TEXT = re.compile(r'<text style="([^"]*)" transform="translate\([\d.]+ [\d.]+\)">([^<]*)</text>')
# Outlier notes in plot coordinates: (x, anchor, first baseline, baseline step, wrap width or None to keep matplotlib's lines). Chosen clear
# of every stem and dot (tests check the boxes). Hampton Twp sits over the low tail it names, left-aligned near its first stem and below
# the "20" tick row: two lines would run into the stems at $140-160k there, so its words go one per line.
OUTLIERS = {"text_11": (45.0, "start", 258.1, 13, 52), "text_12": (292.0, "end", 245.0, 14, None)}


def wrap(text, px, width):
    """Greedy word wrap at an estimated DIST_EM advance; words are never split or changed."""
    lines, cur = [], ""
    for word in text.split(" "):
        trial = f"{cur} {word}" if cur else word
        if cur and len(trial) * px * DIST_EM > width:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    return lines + [cur]


def unwrap(lines):
    """matplotlib's wrapped lines joined back into the original sentence ("User-" + "Friendly" -> "User-Friendly")."""
    out = ""
    for ln in lines:
        out += ln if not out or out.endswith("-") else " " + ln
    return out


def distribution(svg):
    """The /nj/ distribution mobile SVG reflowed into the MOBILE_W viewBox (see the module docstring). Already reflowed: unchanged."""
    if f'viewBox="0 0 {MOBILE_W} ' in svg:
        return svg
    if svg.count(ORIGINAL_VIEWBOX) != 1:
        raise ValueError("not the original matplotlib distribution SVG")
    groups = {m.group(2): m for m in GROUP_TEXT.finditer(svg)}
    texts = {k: [(st, t) for st, t in LINE_TEXT.findall(m.group(3))] for k, m in groups.items()}

    def block(gid, px, step, y0, x=DIST_X, anchor="start", lines=None):
        style = texts[gid][0][0]
        style = re.sub(r"font-size: [\d.]+px", f"font-size: {px}px", style)
        if anchor == "end":
            style = style.replace("; fill:", "; text-anchor: end; fill:")
        lines = lines or wrap(unwrap([t for _, t in texts[gid]]), px, DIST_WRAP)
        return [f'<text style="{style}" transform="translate({x:g} {y0 + i * step:g})">{t}</text>' for i, t in enumerate(lines)]

    title = block("text_13", TITLE_PX, TITLE_STEP, 22)
    title_end = 22 + (len(title) - 1) * TITLE_STEP
    sub = block("text_14", NOTE_PX, NOTE_STEP, title_end + TITLE_STEP)
    sub_end = title_end + TITLE_STEP + (len(sub) - 1) * NOTE_STEP
    dy = round(sub_end + 20 - PLOT_TOP, 2)  # the plot box starts 20 units under the subtitle
    tick_y = AXIS_Y + 17.5  # x tick labels, clear of the "0" y tick label at the corner
    foot_y = tick_y + dy + 28
    foot = block("text_15", NOTE_PX, NOTE_STEP, foot_y)
    height = round(foot_y + (len(foot) - 1) * NOTE_STEP + 10, 1)
    notes = {}
    for gid, (x, anchor, y0, step, width) in OUTLIERS.items():
        lines = [t for _, t in texts[gid]]
        notes[gid] = block(gid, NOTE_PX, step, y0, x, anchor, wrap(" ".join(lines), NOTE_PX, width) if width else lines)

    new = {"text_11": notes["text_11"], "text_12": notes["text_12"], "text_13": title, "text_14": sub, "text_15": foot}
    indent = {k: re.match(r"\s*", m.group(3)).group(0) for k, m in groups.items()}
    svg = GROUP_TEXT.sub(lambda m: m.group(1) + indent[m.group(2)] + ("\n" + indent[m.group(2)]).join(new[m.group(2)]) + m.group(4), svg)

    svg = svg.replace(ORIGINAL_VIEWBOX, f'width="{MOBILE_W}" height="{height:g}" viewBox="0 0 {MOBILE_W} {height:g}"', 1)
    svg = svg.replace("M 0 374.4 \nL 280.8 374.4 \nL 280.8 0 \nL 0 0 \nz", f"M 0 {height:g} \nL {MOBILE_W} {height:g} \nL {MOBILE_W} 0 \nL 0 0 \nz", 1)
    svg = svg.replace('<g id="axes_1">', f'<g id="axes_1" transform="translate({DIST_DX} {dy:g})">', 1)

    def tick(m):
        x, y = m.group(2), float(m.group(3))
        ny = tick_y if m.group(1) == "middle" else y - 0.51 * 6.5 + 0.36 * NOTE_PX  # x ticks under the axis; y ticks re-centred
        return (f'<text style="font-size: {NOTE_PX}px; font-family: \'JetBrains Mono\'; text-anchor: {m.group(1)}; fill: #1a1d21" '
                f'x="{x}" y="{ny:g}" transform="rotate(-0 {x} {ny:g})">')
    svg = re.sub(r'<text style="font-size: 6\.5px; font-family: \'JetBrains Mono\'; text-anchor: (middle|end); fill: #1a1d21" '
                 r'x="([\d.]+)" y="([\d.]+)" transform="rotate\(-0 [\d.]+ [\d.]+\)">', tick, svg)
    svg = svg.replace("font-size: 7px; font-family: 'Space Grotesk'; text-anchor: middle; fill: #5b6470\" x=\"16.16\" y=\"213.7856\" "
                      "transform=\"rotate(-90 16.16 213.7856)\"",
                      f"font-size: {NOTE_PX}px; font-family: 'Space Grotesk'; text-anchor: middle; fill: #5b6470\" x=\"4\" y=\"213.7856\" "
                      "transform=\"rotate(-90 4 213.7856)\"", 1)
    svg = svg.replace("font-size: 7px; font-family: 'JetBrains Mono'; text-anchor: start", f"font-size: {NOTE_PX}px; font-family: 'JetBrains Mono'; text-anchor: start", 1)
    return svg


# --- effective text-size gate -----------------------------------------------------------------------------------------------------
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


def desktop_of(f):
    return f[: -len("-mobile.svg")] + "-desktop.svg"


def read(f):
    with open(f, encoding="utf-8", newline="") as fh:
        return fh.read()


def district_problems(f, svg):
    """Misfits of one district mobile chart, the part-time marks checked against the committed JSON row of each dot."""
    desktop = read(desktop_of(f))
    try:
        ftes = expected_ftes(desktop, load_rows(os.path.basename(f).split("-")[0]))
    except (OSError, ValueError, KeyError) as e:
        return problems(svg, desktop) + [f"cannot read the part-time marks from the JSON: {e}"]
    return problems(svg, desktop, ftes)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true")
    g.add_argument("--write", action="store_true")
    a = ap.parse_args(argv)
    bad, changed = [], 0
    for f in gated_files():
        svg = read(f)
        if a.write:
            new = distribution(svg) if f == DISTRIBUTION else fit(svg, read(desktop_of(f)))
            if new != svg:
                with open(f, "w", encoding="utf-8", newline="") as fh:
                    fh.write(new)
                changed += 1
            svg = new
        p = district_problems(f, svg) if f != DISTRIBUTION else []
        if p:
            bad.append((os.path.relpath(f, ROOT), p))
    for f, p in bad:
        print(f"{f}: {'; '.join(p)}")
    print(f"{len(files())} mobile charts, {changed} rewritten, {len(bad)} still misfit")
    small, nodes = [], {w: 0 for w in CONTENT_PX}
    for f in gated_files():
        s = small_text(read(f))
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
