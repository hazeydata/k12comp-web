"""K12-CHART-MOBILE-TEXT-001: every SVG text node on the district mobile charts and the /nj/ distribution mobile chart is at least 12 CSS px
at 304 and 358 px content (336 and 390 px viewports); data, marks and true year positions are kept; desktop and source data are untouched.
Static checks against the committed tree and the base it starts from (b7e2da6, PR #5 head). Real-browser widths are builder evidence."""
import contextlib
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import nj_fte_marks as N  # noqa: E402  (K12-FTE-PRESENTATION-001, see Scope)
import nj_mobile_chart_fit as F  # noqa: E402
import nj_chart_label_edge as E  # noqa: E402  (K12-CHART-LABEL-EDGE-001: header)
from chart_header_helpers import content_changes  # noqa: E402

BASE = "b7e2da6dde06f4b102301c62ac296908f5f6477b"  # the tree this ticket starts from (PR #5 head)
MAIN = "a41b583835f15b30bb5a398c94beaa1e22e8297d"  # web main: desktop charts must still equal it (AC 10)
FTE_LEAIDS = {leaid for _, leaid in N.pages() if N.marked_rows(N.rows_of(leaid))}  # the 44 districts K12-FTE-PRESENTATION-001 marks
TOMS = "charts/d/3416230-mobile.svg"
DIST = "charts/chart3-nj-salary-distribution-mobile.svg"
ALT = re.compile(r'alt="Line chart of [^"]*?: ([^"]*?)\.(?: Not reported[^"]*)?"')


def rt(rel):
    with open(os.path.join(ROOT, *rel.split("/")), encoding="utf-8", newline="") as f:
        return f.read()


def at(commit, rel):
    return subprocess.run(["git", "-C", ROOT, "show", f"{commit}:{rel}"], capture_output=True, check=True).stdout.decode()


def rel(f):
    return os.path.relpath(f, ROOT).replace(os.sep, "/")


def quiet_main(argv):
    with contextlib.redirect_stdout(io.StringIO()) as buf:
        code = F.main(argv)
    return code, buf.getvalue()


def effective(svg, width):
    vb_w, sizes = F.text_sizes(svg)
    return [(t, u * width / vb_w) for t, u in sizes]


class Gate(unittest.TestCase):
    """AC 1-5: the effective text-size gate (D5)."""

    def test_gate_passes_on_the_committed_tree(self):
        code, out = quiet_main(["--check"])
        self.assertEqual(code, 0, out)
        self.assertIn("573 mobile charts, 0 rewritten, 0 still misfit", out)
        self.assertIn("574 mobile charts measured at 304/358 px content, 0 with text under 12 px; text nodes under 12 px: 0 at 304 px, 0 at 358 px", out)

    def test_every_text_node_is_at_least_12_px_at_both_widths(self):
        self.assertEqual(len(F.gated_files()), 574)
        for f in F.gated_files():
            svg = rt(rel(f))
            for w in F.CONTENT_PX:
                sizes = effective(svg, w)
                self.assertTrue(sizes, f)
                self.assertGreaterEqual(min(px for _, px in sizes), 12, (f, w))

    def test_gate_reproduces_the_review_measurements_at_base(self):
        """Ann's PR #5 review measured these in a browser at 336/390: same counts and minimums."""
        for path, counts, low in ((TOMS, (10, 9), 9.35), (DIST, (26, 22), 6.50)):
            small = F.small_text(at(BASE, path))
            self.assertEqual(tuple(sum(1 for s in small if s[0] == w) for w in F.CONTENT_PX), counts, path)
            self.assertAlmostEqual(min(s[2] for s in small), low, places=2)

    def test_gate_fails_on_the_base_charts_and_write_reproduces_the_committed_ones(self):
        with tempfile.TemporaryDirectory(prefix="k12-mobile-text-test-") as tmp:
            charts = os.path.join(tmp, "d")
            os.mkdir(charts)
            for leaid in ("3416230", "3402440", "3401470", "3412390"):
                for kind in ("mobile", "desktop"):
                    with open(os.path.join(charts, f"{leaid}-{kind}.svg"), "w", encoding="utf-8", newline="") as fh:
                        fh.write(at(BASE, f"charts/d/{leaid}-{kind}.svg"))
            dist = os.path.join(tmp, "chart3.svg")
            with open(dist, "w", encoding="utf-8", newline="") as fh:
                fh.write(at(BASE, DIST))
            with mock.patch.multiple(F, CHARS=charts, DISTRIBUTION=dist):
                code, out = quiet_main(["--check"])
                self.assertEqual(code, 1)
                self.assertIn("5 mobile charts measured at 304/358 px content, 5 with text under 12 px", out)
                self.assertEqual(quiet_main(["--write"])[0], 0)
                self.assertEqual(quiet_main(["--check"])[0], 0)
                for f in F.files():
                    self.assertEqual(E.add_headroom(F.read(f)), rt("charts/d/" + os.path.basename(f)), f)  # the committed charts also carry the headroom header
            self.assertEqual(F.read(dist), rt(DIST))

    def test_size_includes_css_rules_inline_style_and_ancestor_scale(self):
        svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 304 100"><style>text{font-size:12px}.s{font-size:10px}</style>'
               '<text>a</text><text class="s">b</text><text style="font-size: 14px" class="s">c</text>'
               '<g transform="translate(5 5) scale(0.5)"><text style="font-size: 20px">d</text></g>'
               '<g transform="rotate(-90 1 1)"><text font-size="9">e</text></g></svg>')
        self.assertEqual(F.text_sizes(svg), (304.0, [("a", 12.0), ("b", 10.0), ("c", 14.0), ("d", 10.0), ("e", 12.0)]))
        self.assertEqual([(t, round(px, 2)) for w, t, px in F.small_text(svg) if w == 304], [("b", 10.0), ("d", 10.0)])
        self.assertEqual([t for w, t, _ in F.small_text(svg) if w == 358], ["b", "d"])  # 10 x 358 / 304 = 11.78
        with self.assertRaises(ValueError):
            F.text_sizes('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><text>no size</text></svg>')


class Districts(unittest.TestCase):
    """AC 5-7 for every district mobile chart."""

    def charts(self):
        for f in F.files():
            yield rel(f), rt(rel(f)), F.read(F.desktop_of(f))

    def test_every_chart_is_drawn_in_the_304_viewbox_and_fits(self):
        for path, svg, desktop in self.charts():
            self.assertTrue(svg.startswith('<svg xmlns="http://www.w3.org/2000/svg" width="304" height="304" viewBox="0 -4 304 304"'), path)  # K12-CHART-LABEL-EDGE-001 headroom
            self.assertEqual(F.problems(svg, desktop), [], path)
            self.assertEqual(F.fit(svg, desktop), svg, path)  # idempotent

    def test_dot_years_match_the_page_alt_text_and_sit_at_true_positions(self):
        """The alt text on each district page is an independent record of the plotted years and values."""
        pages = {re.search(r"-(\d{7})$", d).group(1): d for d in os.listdir(os.path.join(ROOT, "nj")) if re.search(r"-\d{7}$", d)}
        for path, svg, desktop in self.charts():
            alt = ALT.search(rt(f"nj/{pages[path[9:16]]}/index.html")).group(1)
            years = [int(y) for y in re.findall(r"(\d{4})-\d\d \$", alt)]
            got, first, last = F.years_of_dots(desktop)
            self.assertEqual(got, years, path)
            xs = [float(x) for x, _ in F.DOT.findall(svg)]
            for x, y in zip(xs, years):
                self.assertAlmostEqual(x, F.PLOT_L + (y - first) * (F.PLOT_R - F.PLOT_L) / (last - first), delta=0.051, msg=path)

    def test_values_heights_lines_and_gridlines_are_kept(self):
        def keep(svg):
            m = F.DISTRICT.match(svg)
            # K12-FTE-PRESENTATION-001 re-cuts lines at part-time dots: compare the y pairs of each segment, not where a polyline starts
            lines = [(p.split(",")[1], q.split(",")[1]) for pts in F.POLYLINE.findall(m.group("lines")) for p, q in zip(pts.split(), pts.split()[1:])]
            return (m.group("style"), F.GRID.findall(m.group("grid")), lines, [y for _, y in F.DOT.findall(svg)],
                    [v[3] for v in F.VALUE.findall(svg)])
        for path, svg, _ in self.charts():
            new, old = keep(svg), keep(at(BASE, path))
            if 'class="pt"' in svg:  # a re-cut chart keeps a subset of the old segments (tests/test_k12_fte_presentation.py pins the rule)
                self.assertEqual(new[:2] + new[3:], old[:2] + old[3:], path)
                rest = list(old[2])
                for seg in new[2]:
                    rest.remove(seg)
            else:
                self.assertEqual(new, old, path)

    def test_lines_join_the_same_dots_as_before(self):
        def joins(svg):
            dots = F.DOT.findall(svg)
            return [[dots.index(tuple(p.split(","))) for p in pts.split()] for pts in F.POLYLINE.findall(svg)]
        def segments(svg):
            return [(a, b) for pts in joins(svg) for a, b in zip(pts, pts[1:])]
        for path, svg, _ in self.charts():
            if 'class="pt"' in svg:  # K12-FTE-PRESENTATION-001 re-cuts lines at part-time dots: only segments are removed, none added
                rest = segments(at(BASE, path))
                for seg in segments(svg):
                    rest.remove(seg)
            else:
                self.assertEqual(joins(svg), joins(at(BASE, path)), path)

    def test_year_labels_follow_the_rule(self):
        """AC 7: the latest axis year, then every k-th year back; evenly spaced; each at its true position."""
        for path, svg, desktop in self.charts():
            _, first, last = F.years_of_dots(desktop)
            ticks = [(float(x), t) for x, t in F.TICK.findall(svg)]
            want = F.year_labels(first, last)
            self.assertEqual([t for _, t in ticks], [F.school_year(y) for y in want], path)
            self.assertEqual(want[-1], last, path)
            self.assertGreaterEqual(want[0], first, path)
            self.assertLess(want[0] - first, max(want[1] - want[0], 1) if len(want) > 1 else 1, path)  # no room for one more step
            self.assertEqual(len({b - a for a, b in zip(want, want[1:])}), min(len(want) - 1, 1), path)
            for (x, _), y in zip(ticks, want):
                self.assertAlmostEqual(x, F.PLOT_L + (y - first) * (F.PLOT_R - F.PLOT_L) / (last - first), delta=0.051, msg=path)

    def test_toms_river_reference_chart(self):
        svg = rt(TOMS)
        self.assertEqual(F.TICK.findall(svg), [("80.0", "2020-21"), ("144.0", "2022-23"), ("208.0", "2024-25"), ("272.0", "2026-27")])
        self.assertEqual([x for x, _ in F.DOT.findall(svg)], [f"{48 + 32 * i:.1f}" for i in range(8)])
        self.assertEqual(F.VALUE.findall(svg), [("298.0", "24.9", ' text-anchor="end"', "$228,160")])
        self.assertEqual(sorted(px for _, px in effective(svg, 304)), [12.0] * 9 + [14.0])

    def test_slot_spaced_charts_now_have_true_year_spacing(self):
        """Burlington Co Spec Serv: 2019-20, 2025-26, 2026-27. The desktop (unchanged) spaces them evenly; mobile spaces them by year."""
        self.assertEqual([x for x, _ in F.DOT.findall(rt("charts/d/3402440-mobile.svg"))], ["48.0", "240.0", "272.0"])
        self.assertEqual([x for x, _ in F.DESKTOP_DOT.findall(rt("charts/d/3402440-desktop.svg"))], ["64.0", "544.0", "1024.0"])

    def labels(self, svg, desktop):
        """[(text, anchor_end, x, baseline, ink box, own dot)] for every value label, its dot found through the desktop twin."""
        dots = [(float(x), float(y)) for x, y in F.DOT.findall(svg)]
        out = []
        for (_, i), m in zip(F.value_owners(desktop), F.VALUE.finditer(svg)):
            x, y, end, text = float(m.group(1)), float(m.group(2)), bool(m.group(3)), m.group(4)
            w = len(text) * F.VALUE_PX * F.EM
            left = x - w if end else x
            out.append((text, end, x, y, (left, y - 0.75 * F.VALUE_PX, left + w, y + 0.25 * F.VALUE_PX), dots[i]))
        return out

    def test_far_value_labels_have_one_leader_to_their_dot_and_near_ones_none(self):
        """Review fix 2: a label more than 20 units from its dot is joined to it by one thin grey line (#999, 0.75, no arrowhead) running
        from the label's nearest box edge to the dot; nearer labels have no leader."""
        line = re.compile(r"<line ([^>]*)/>")
        far = []
        for path, svg, desktop in self.charts():
            leaders = []
            for ln in line.findall(svg):
                a = dict(re.findall(r'([\w-]+)="([^"]*)"', ln))
                if a.get("stroke") == "#999":
                    self.assertEqual(a.get("stroke-width"), "0.75", path)
                    self.assertNotIn("marker-end", a, path)
                    leaders.append(tuple(float(a[k]) for k in ("x1", "y1", "x2", "y2")))
            for text, _, _, _, (l, t, r, b), (cx, cy) in self.labels(svg, desktop):
                near = (min(max(cx, l), r), min(max(cy, t), b))
                dist = ((near[0] - cx) ** 2 + (near[1] - cy) ** 2) ** 0.5

                def joins(ln):
                    ends = [(ln[0], ln[1]), (ln[2], ln[3])]
                    on_edge = [e for e in ends if l - 0.06 <= e[0] <= r + 0.06 and t - 0.06 <= e[1] <= b + 0.06
                               and min(e[0] - l, r - e[0], e[1] - t, b - e[1]) <= 0.06]
                    at_dot = [e for e in ends if ((e[0] - cx) ** 2 + (e[1] - cy) ** 2) ** 0.5 <= 4]
                    return bool(on_edge) and bool(at_dot) and on_edge[0] != at_dot[0]
                mine = [ln for ln in leaders if joins(ln)]
                if dist > 20:
                    far.append(path[9:16])
                    self.assertEqual(len(mine), 1, (path, text, dist))
                    self.assertAlmostEqual(min(((e[0] - near[0]) ** 2 + (e[1] - near[1]) ** 2) ** 0.5
                                               for e in ((mine[0][0], mine[0][1]), (mine[0][2], mine[0][3]))), 0, delta=0.08)
                    leaders.remove(mine[0])
                else:
                    self.assertEqual(mine, [], (path, text, dist))
            self.assertEqual(leaders, [], path)  # no stray leaders
        self.assertEqual(far, ["3403930", "3405550", "3406870", "3410320", "3411280", "3411310", "3412390", "3414880"])

    def test_a_dot_before_the_last_year_has_its_label_start_aligned_beside_it(self):
        """Review fix 3: when the labelled dot is not at the rightmost year slot, the label starts about 6 units right of the dot, never
        right-aligned at the plot edge over the empty years."""
        seen = {}
        for path, svg, desktop in self.charts():
            for text, end, x, y, _, (cx, cy) in self.labels(svg, desktop):
                if cx < F.PLOT_R - 0.5:
                    seen[path[9:16]] = round(x - cx, 1)
                    self.assertFalse(end, (path, text))
                    self.assertTrue(6 <= x - cx <= 8, (path, text, x, cx))
                    self.assertLessEqual(abs(y - cy), F.LIFT + F.VALUE_PX, (path, text))
        self.assertEqual(seen, {"3403660": 8, "3406150": 8, "3412030": 8, "3414220": 6, "3414790": 8, "3417790": 8})
        self.assertEqual(F.VALUE.findall(rt("charts/d/3414220-mobile.svg")), [("214.0", "250.0", "", "$20,000")])  # dot at x=208

    def test_label_placement_avoids_marks_and_other_dots(self):
        dots = [(100.0, 100.0), (200.0, 50.0), (272.0, 120.0)]
        segments = list(zip(dots, dots[1:]))
        x, end, y = F.place_value("$100,000", dots[2], dots, segments, [])
        box = F.value_box(x, end, y, "$100,000")
        self.assertFalse(F.covers_marks(box, dots, segments, [], 1))
        self.assertFalse(F.nearer_dot(box, dots[2], dots))
        self.assertTrue(F.segment_hits((0, 0), (10, 10), (4, 4, 6, 6)))
        self.assertFalse(F.segment_hits((0, 0), (10, 0), (4, 4, 6, 6)))


class Distribution(unittest.TestCase):
    """AC 3, 4, 6, 9, 13 for the /nj/ distribution mobile chart."""
    TEXT = re.compile(r"<text [^>]*>[^<]*</text>")

    def test_reflow_is_reproducible_from_the_matplotlib_original_and_idempotent(self):
        self.assertEqual(F.distribution(at(BASE, DIST)), rt(DIST))
        self.assertEqual(F.distribution(rt(DIST)), rt(DIST))
        self.assertEqual(at(BASE, DIST), at(MAIN, DIST))

    def test_words_are_verbatim(self):
        """Title, subtitle and source note keep their words (D4, AC 13 N/A): only line breaks change."""
        def blocks(svg):
            return {gid: [t for _, t in F.LINE_TEXT.findall(m.group(3))] for m, gid in ((m, m.group(2)) for m in F.GROUP_TEXT.finditer(svg))}
        old, new = blocks(at(BASE, DIST)), blocks(rt(DIST))
        self.assertEqual(set(old), {"text_11", "text_12", "text_13", "text_14", "text_15"})
        for gid in ("text_13", "text_14", "text_15"):
            self.assertEqual(" ".join(new[gid]), F.unwrap(old[gid]), gid)
            self.assertGreater(len(new[gid]), 1)
        self.assertIn("NJDOE User-Friendly Budget files", " ".join(new["text_15"]))
        self.assertEqual(new["text_11"], ["Hampton", "Twp", "$56,225"])  # one word per line (review fix 1), same words
        self.assertEqual(" ".join(new["text_11"]), " ".join(old["text_11"]))
        self.assertEqual(new["text_12"], old["text_12"])
        strip = re.compile(r"<[^>]+>")
        self.assertEqual(sorted(strip.sub("", t) for t in self.TEXT.findall(rt(DIST)) if "translate(" not in t),
                         sorted(strip.sub("", t) for t in self.TEXT.findall(at(BASE, DIST)) if "translate(" not in t))

    def test_marks_are_only_translated(self):
        def marks(svg):
            svg = self.TEXT.sub("", svg)
            svg = re.sub(r'<svg [^>]*>', "", svg, count=1)
            svg = re.sub(r'<g id="axes_1"[^>]*>', '<g id="axes_1">', svg, count=1)
            svg = re.sub(r'<path d="M 0 [\d.]+ \nL [\d.]+ [\d.]+ \nL [\d.]+ 0 \nL 0 0 \nz', "BACKGROUND", svg, count=1)
            return re.sub(r">\s+<", "><", svg)  # text blocks have more lines now: drop the whitespace between tags
        self.assertEqual(marks(rt(DIST)), marks(at(BASE, DIST)))
        self.assertRegex(rt(DIST), r'<g id="axes_1" transform="translate\(8 [\d.]+\)">')

    def text_boxes(self, svg):
        """(estimated ink boxes (word, left, top, right, bottom) of every text node in viewBox units, plot dx, dy, the axes markup)."""
        dx, dy = (float(v) for v in re.search(r'<g id="axes_1" transform="translate\(([\d.]+) ([\d.]+)\)">', svg).groups())
        axes = svg[svg.index('<g id="axes_1"'):svg.index('<g id="text_13">')]
        boxes = []
        for m in self.TEXT.finditer(svg):
            t = m.group(0)
            px = float(re.search(r"font-size: ([\d.]+)px", t).group(1))
            word = re.search(r">([^<]*)<", t).group(1)
            pos = re.search(r'x="([\d.]+)" y="([\d.]+)"', t) or re.search(r"translate\(([\d.]+) ([\d.]+)\)", t)
            x, y = float(pos.group(1)), float(pos.group(2))
            if m.start() > svg.index('<g id="axes_1"') and m.start() < svg.index('<g id="text_13">'):
                x, y = x + dx, y + dy
            w = len(word) * px * F.EM
            if "rotate(-90" in t:  # the y-axis title runs bottom to top, centred on y
                boxes.append((word, x - 0.75 * px, y - w / 2, x + 0.25 * px, y + w / 2))
                continue
            left = x - w if "text-anchor: end" in t else x - w / 2 if "text-anchor: middle" in t else x
            left += (len(word) - len(word.lstrip())) * px * F.EM  # " median $206,606" starts at the median line; a space has no ink
            boxes.append((word, left, y - 0.75 * px, left + len(word.strip()) * px * F.EM, y + 0.25 * px))
        return boxes, dx, dy, axes

    def test_text_stays_inside_the_viewbox_and_clear_of_stems_dots_and_other_text(self):
        svg = rt(DIST)
        width, height = (float(v) for v in re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', svg).groups())
        self.assertEqual(width, 304)
        boxes, dx, dy, axes = self.text_boxes(svg)
        for b in boxes:
            self.assertTrue(b[1] >= 0 and b[2] >= 0 and b[3] <= width and b[4] <= height, b)
        for i, a in enumerate(boxes):
            for b in boxes[i + 1:]:
                self.assertFalse(a[1] < b[3] and b[1] < a[3] and a[2] < b[4] and b[2] < a[4], (a, b))
        stems = [(float(x) + dx, float(top) + dy, float(bottom) + dy)
                 for x, bottom, top in re.findall(r'<path d="M ([\d.]+) ([\d.]+) \nL [\d.]+ ([\d.]+) \n" clip-path', axes)]
        dots = [(float(x) + dx, float(y) + dy) for x, y in re.findall(r'<use xlink:href="#m4e4e25f855" x="([\d.]+)" y="([\d.]+)"', axes)]
        self.assertEqual((len(stems), len(dots)), (27, 26))  # 26 bins + the median line
        for word, l, t, r, b in boxes:
            for x, top, bottom in stems:
                self.assertFalse(l - 1 < x < r + 1 and t - 1 < bottom and top - 1.3 < b + 1, (word, x))
            for x, y in dots:
                self.assertFalse(l - 2.3 < x < r + 2.3 and t - 2.3 < y < b + 2.3, (word, x, y))

    def test_hampton_note_sits_over_the_low_tail_at_least_6_units_clear_of_the_20_tick_label(self):
        """Review fix 1: at 304 px content 1 viewBox unit is 1 CSS px. The note is left-aligned near the first low-tail stem, below the
        20 tick level, at least 6 units from the "20" label's box (and from every other tick label)."""
        svg = rt(DIST)
        boxes, dx, dy, axes = self.text_boxes(svg)
        note = [b for b in boxes if b[0] in ("Hampton", "Twp", "$56,225")]
        self.assertEqual([b[0] for b in note], ["Hampton", "Twp", "$56,225"])
        ticks = [b for b in boxes if b[0] in ("0", "20", "40", "60")]
        self.assertEqual(len(ticks), 4)

        def gap(a, b):
            return (max(a[1] - b[3], 0, b[1] - a[3]) ** 2 + max(a[2] - b[4], 0, b[2] - a[4]) ** 2) ** 0.5
        twenty = next(b for b in ticks if b[0] == "20")
        self.assertGreaterEqual(min(gap(n, twenty) for n in note), 6)
        for t in ticks:
            self.assertGreaterEqual(min(gap(n, t) for n in note), 6, t[0])
        tick20_y = float(re.search(r'<use xlink:href="#mef0032ba88" x="[\d.]+" y="([\d.]+)"', axes.split('id="ytick_2"')[1]).group(1)) + dy
        first_stem = min(float(x) for x in re.findall(r'<path d="M ([\d.]+) [\d.]+ \nL [\d.]+ [\d.]+ \n" clip-path', axes)) + dx
        self.assertGreater(min(n[2] for n in note), tick20_y)  # below the 20 level
        self.assertTrue(all(abs(n[1] - first_stem) <= 3 for n in note), first_stem)  # left-aligned at the low tail


class Scope(unittest.TestCase):
    """AC 10 and 12: desktop charts, pages, CSS and source data are untouched; only mobile chart SVGs change on the site."""

    def test_only_the_in_scope_mobile_svgs_change_on_the_site(self):
        out = subprocess.run(["git", "-C", ROOT, "diff", "--name-status", BASE], capture_output=True, check=True, text=True).stdout.splitlines()
        site = [ln for ln in out if not ln.split("\t", 1)[1].startswith(("docs/", "tests/", "tools/"))]
        self.assertTrue(site)
        for ln in site:
            # K12-FTE-PRESENTATION-001 also changes the part-time districts' desktop charts and pages, /nj/, /about/, llms.txt, style.css
            self.assertRegex(ln, r"^M\t(charts/d/\d{7}-(mobile|desktop)\.svg|charts/chart3-nj-salary-distribution-mobile\.svg"
                                 r"|nj/[a-z0-9-]+-\d{7}/index\.html|nj/index\.html|about/index\.html|llms\.txt|style\.css)$")

    def test_desktop_charts_equal_web_main(self):
        out = content_changes(MAIN, subprocess.run(["git", "-C", ROOT, "diff", "--name-only", MAIN, "--", "charts", "data"],
                                                   capture_output=True, check=True, text=True).stdout.split())  # K12-CHART-LABEL-EDGE-001: not counting the header
        self.assertEqual([p for p in out if not re.fullmatch(r"charts/d/\d{7}-mobile\.svg|charts/chart3-nj-salary-distribution-mobile\.svg", p)
                          and p not in {f"charts/d/{leaid}-desktop.svg" for leaid in FTE_LEAIDS}], [])  # K12-FTE-PRESENTATION-001: the part-time districts only
        self.assertEqual({p for p in out if p.endswith("-desktop.svg")}, {f"charts/d/{leaid}-desktop.svg" for leaid in FTE_LEAIDS})


if __name__ == "__main__":
    unittest.main()
