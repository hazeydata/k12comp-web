"""Chart label edge gate (K12-CHART-LABEL-EDGE-001, bundles K12-NJ-YEAR-WRAP-001).

Runs last in the chart chain, after `nj_mobile_chart_fit.py`:
  nj_api_index -> nj_guide_tables -> nj_fte_marks -> nj_mobile_chart_fit -> nj_chart_label_edge
It owns two rules for the 1146 district charts (charts/d/<leaid>-{mobile,desktop}.svg) and changes nothing else in them.

Headroom rule. A text box (em box: baseline - 1.05 x font size at the top) can stick 0.2-0.5 px out of the top of a chart at some widths
(top-right value labels at baseline 14, keys at baseline 12), although its ink never does. Every chart therefore gets 4 units of empty
white headroom, in the header only:
    <svg xmlns="http://www.w3.org/2000/svg" width="W" height="H+4" viewBox="0 -4 W H+4" role="img"><rect y="-4" width="W" height="H+4" fill="#ffffff"/>
W and H are the chart's old width and height (mobile 304 x 300, desktop 1120 x 320 today; read, not fixed). No coordinate, text or style
changes, so nothing can collide. A file already in the new header is left alone (idempotent).

Axis rule (desktop only). A desktop value label whose box (`nj_mobile_chart_fit.value_box`, 14 px bold) overlaps the x-axis line band
(the #999999 line, y +/- 0.5) within the axis x span moves above its own dot: same x (dot x + 8, start-anchored), baseline = dot y - LIFT.
If that spot covers a dot (ink radius 4.75 for the hollow dot, covered by the 2-unit pad), a line segment, the key or another label, or is
nearer another dot, the next candidate is tried, in the order of `nj_mobile_chart_fit.place_value` (beside, above/below, left of the dot,
then further out; the label stays inside the plot, above the axis), and the build fails when none is clear. Only the label's x and y change. Today this moves 3414220's `$20,000` from
(840, 285) to (840, 270); labels right of the axis end (x > 1024) are not in the span and stay.

    python3 tools/nj_chart_label_edge.py --check   # exit 1 on any chart without the header, any text em box (or, with the same 1-unit
                                                    # pad, any estimated box) outside the viewBox, any desktop value label on the axis
    python3 tools/nj_chart_label_edge.py --write   # apply both rules in place, then check
"""
import argparse
import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nj_mobile_chart_fit as M  # noqa: E402

CHARS = M.CHARS
ROOT = M.ROOT
HEADROOM = 4  # units of white above every chart
PAD = 1  # an em box must stay this far inside the viewBox
ASCENT = 1.05  # em top = baseline - ASCENT x font size
OLD_HEADER = re.compile(
    r'<svg xmlns="http://www.w3.org/2000/svg" width="(\d+)" height="(\d+)" viewBox="0 0 \1 \2" role="img"><rect width="\1" height="\2" fill="#ffffff"/>')
NEW_HEADER = re.compile(
    r'<svg xmlns="http://www.w3.org/2000/svg" width="(\d+)" height="(\d+)" viewBox="0 -%d \1 \2" role="img">'
    r'<rect y="-%d" width="\1" height="\2" fill="#ffffff"/>' % (HEADROOM, HEADROOM))
TEXT = re.compile(r'<text( class="(?:v|key)")? x="([\d.]+)" y="([\d.]+)"( text-anchor="(?:end|middle)")?>([^<]*)</text>')
AXIS = re.compile(r'<line x1="([\d.]+)" x2="([\d.]+)" y1="([\d.]+)" y2="[\d.]+" stroke="#999999"/>')
VALUE_LABEL = re.compile(r'<text class="v" x="([\d.]+)" y="([\d.]+)"((?: text-anchor="end")?)>([^<]*)</text>')


def new_header(w, h):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h + HEADROOM}" viewBox="0 -{HEADROOM} {w} {h + HEADROOM}" role="img">'
            f'<rect y="-{HEADROOM}" width="{w}" height="{h + HEADROOM}" fill="#ffffff"/>')


def add_headroom(svg):
    """The chart with the headroom header; a chart that already has it is returned unchanged."""
    if NEW_HEADER.match(svg):
        return svg
    m = OLD_HEADER.match(svg)
    if not m:
        raise ValueError("unexpected chart header")
    return new_header(int(m.group(1)), int(m.group(2))) + svg[m.end():]


def remove_headroom(svg):
    """The chart in its old header (the inverse of add_headroom, for tests that compare with earlier commits)."""
    m = NEW_HEADER.match(svg)
    if not m:
        return svg
    w, h = int(m.group(1)), int(m.group(2)) - HEADROOM
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img"><rect width="{w}" height="{h}" fill="#ffffff"/>' + svg[m.end():]


def geometry(svg):
    """(left, top, right, bottom) of the chart's viewBox, from the header (either form)."""
    m = NEW_HEADER.match(svg)
    if m:
        w, h = int(m.group(1)), int(m.group(2))
        return 0, -HEADROOM, w, h - HEADROOM
    m = OLD_HEADER.match(svg)
    if not m:
        raise ValueError("unexpected chart header")
    return 0, 0, int(m.group(1)), int(m.group(2))


def font_sizes(svg):
    """(default, {class: px}) from the chart's <style> block."""
    style = re.search(r"<style>([^<]*)</style>", svg).group(1)
    by_class, default = {}, M.TICK_PX
    for sels, decls in M.CSS_RULE.findall(style):
        m = M.FONT_SIZE.search(decls)
        if not m:
            continue
        for sel in (s.strip() for s in sels.split(",")):
            if sel == "text":
                default = float(m.group(1))
            elif sel.startswith("."):
                by_class[sel[1:]] = float(m.group(1))
    return default, by_class


def edge_problems(svg):
    """Text nodes whose estimated box is not PAD units inside the viewBox: em top = baseline - 1.05 x size (exact), bottom = baseline + 0.25 x
    size, left and right from the monospace advance estimate (`nj_mobile_chart_fit.EM`)."""
    left, top, right, bottom = geometry(svg)
    default, by_class = font_sizes(svg)
    out = []
    for m in TEXT.finditer(svg):
        cls = (m.group(1) or "")[8:-1]
        px = by_class.get(cls, default)
        x, y, text = float(m.group(2)), float(m.group(3)), m.group(5)
        width = M.width_of(text, px)
        anchor = m.group(4) or ""
        x0 = x - width if "end" in anchor else x - width / 2 if "middle" in anchor else x
        box = (x0, y - ASCENT * px, x0 + width, y + 0.25 * px)
        for side, bad in (("top", box[1] < top + PAD), ("bottom", box[3] > bottom - PAD),
                          ("left", box[0] < left + PAD), ("right", box[2] > right - PAD)):
            if bad:
                out.append(f"text {text!r} at ({m.group(2)}, {m.group(3)}) leaves the viewBox ({side})")
    return out


# --- desktop axis rule -------------------------------------------------------------------------------------------------------------
def crosses_axis(box, axis):
    """True when a label box overlaps the axis line band (y +/- 0.5) within the axis x span. axis = (x1, x2, y)."""
    x1, x2, y = axis
    return box[1] < y + 0.5 and box[3] > y - 0.5 and box[0] < x2 and box[2] > x1


def axis_of(svg):
    m = AXIS.search(svg)
    return (float(m.group(1)), float(m.group(2)), float(m.group(3))) if m else None


def desktop_candidates(dot, text, axis):
    """(x, anchor_end, baseline) tries for a label that must leave the axis: LIFT above the dot first, then place_value's order (below,
    beside, left of the dot, then further out above and below), all start-aligned right of the dot or end-aligned left of it. The last
    year slot is the axis end, so no try is right-aligned at an edge."""
    cx, cy = dot
    above, below = cy - M.LIFT, cy + M.LIFT + M.VALUE_PX
    tries = [(cx + 8, False, above), (cx + 8, False, below), (cx + 8, False, cy + 5)]
    tries += [(cx - 8, True, y) for y in (above, cy + 5, below)]
    for k in range(1, 40):
        tries += [(cx + 8, False, above - 4 * k), (cx + 8, False, below + 4 * k)]
    return [t for t in tries if t[2] >= M.VALUE_PX]


def move_axis_labels(svg):
    """The desktop chart with each value label on the x-axis moved above its dot (see the module docstring). Raises ValueError when no
    candidate is clear. A chart with no such label is returned unchanged."""
    axis = axis_of(svg)
    if axis is None:
        return svg
    width = geometry(svg)[2]
    labels = list(VALUE_LABEL.finditer(svg))
    owners = M.value_owners(svg)
    dots = [(float(x), float(y)) for x, y in M.DESKTOP_DOT.findall(svg)]
    segments = M.polyline_segments(svg)
    boxes = [M.value_box(float(m.group(1)), bool(m.group(3)), float(m.group(2)), m.group(4)) for m in labels]
    key_boxes = [M.key_box(float(m[0]), float(m[1]), m[4]) for m in M.KEY_PARTS.findall(svg)]
    out, last = [], 0
    for i, m in enumerate(labels):
        if not crosses_axis(boxes[i], axis):
            continue
        own = dots[owners[i][1]]
        others = [b for j, b in enumerate(boxes) if j != i] + key_boxes
        for t in desktop_candidates(own, m.group(4), axis):
            box = M.value_box(t[0], t[1], t[2], m.group(4))
            if (crosses_axis(box, axis) or box[3] > axis[2] or box[0] < 0 or box[2] > width - M.MARGIN
                    or M.covers_marks(box, dots, segments, others, 2)
                    or M.nearer_dot(box, own, dots)):
                continue
            end = ' text-anchor="end"' if t[1] else ""
            out.append(svg[last:m.start()] + f'<text class="v" x="{t[0]:.1f}" y="{t[2]:.1f}"{end}>{m.group(4)}</text>')
            last = m.end()
            boxes[i] = box
            break
        else:
            raise ValueError(f"no clear spot off the axis for value label {m.group(4)!r}")
    return "".join(out) + svg[last:]


def axis_problems(svg):
    axis = axis_of(svg)
    if axis is None:
        return []
    return [f"value label {t!r} at ({x}, {y}) sits on the x-axis"
            for x, y, e, t in VALUE_LABEL.findall(svg)
            if crosses_axis(M.value_box(float(x), bool(e), float(y), t), axis)]


# --- chain -----------------------------------------------------------------------------------------------------------------------
def files():
    return sorted(glob.glob(os.path.join(CHARS, "*-mobile.svg")) + glob.glob(os.path.join(CHARS, "*-desktop.svg")))


def convert(f, svg):
    """The chart as `--write` leaves it."""
    svg = add_headroom(svg)
    return move_axis_labels(svg) if f.endswith("-desktop.svg") else svg


def problems(f, svg):
    """Every misfit of one chart: header, text box edges, and (desktop) the axis."""
    if not NEW_HEADER.match(svg):
        out = ["not the headroom header (width x height, viewBox 0 -4, white rect y -4)"]
    else:
        out = []
    try:
        out += edge_problems(svg)
    except ValueError as e:
        out.append(str(e))
    if f.endswith("-desktop.svg"):
        out += axis_problems(svg)
    return out


def main(argv=None, chars=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true")
    g.add_argument("--write", action="store_true")
    a = ap.parse_args(argv)
    paths = files() if chars is None else sorted(glob.glob(os.path.join(chars, "*-mobile.svg")) + glob.glob(os.path.join(chars, "*-desktop.svg")))
    changed, bad, n = 0, 0, 0
    for f in paths:
        svg = M.read(f)
        if a.write:
            new = convert(f, svg)
            if new != svg:
                with open(f, "w", encoding="utf-8", newline="") as fh:
                    fh.write(new)
                changed += 1
            svg = new
        for p in problems(f, svg):
            bad += 1
            print(f"{os.path.basename(f)}: {p}")
        n += 1
    print(f"{n} charts, {changed} rewritten, {bad} problems")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
