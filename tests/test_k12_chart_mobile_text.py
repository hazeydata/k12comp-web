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
import nj_mobile_chart_fit as F  # noqa: E402

BASE = "b7e2da6dde06f4b102301c62ac296908f5f6477b"  # the tree this ticket starts from (PR #5 head)
MAIN = "a41b583835f15b30bb5a398c94beaa1e22e8297d"  # web main: desktop charts must still equal it (AC 10)
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
                    self.assertEqual(F.read(f), rt("charts/d/" + os.path.basename(f)), f)
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
            self.assertTrue(svg.startswith('<svg xmlns="http://www.w3.org/2000/svg" width="304" height="300" viewBox="0 0 304 300"'), path)
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
            lines = [[p.split(",")[1] for p in pts.split()] for pts in F.POLYLINE.findall(m.group("lines"))]
            return (m.group("style"), F.GRID.findall(m.group("grid")), lines, [y for _, y in F.DOT.findall(svg)],
                    [v[3] for v in F.VALUE.findall(svg)])
        for path, svg, _ in self.charts():
            self.assertEqual(keep(svg), keep(at(BASE, path)), path)

    def test_lines_join_the_same_dots_as_before(self):
        def joins(svg):
            dots = F.DOT.findall(svg)
            return [[dots.index(tuple(p.split(","))) for p in pts.split()] for pts in F.POLYLINE.findall(svg)]
        for path, svg, _ in self.charts():
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
        for gid in ("text_11", "text_12"):
            self.assertEqual(new[gid], old[gid], gid)
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

    def test_text_stays_inside_the_viewbox_and_clear_of_stems_dots_and_other_text(self):
        svg = rt(DIST)
        width, height = (float(v) for v in re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', svg).groups())
        self.assertEqual(width, 304)
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


class Scope(unittest.TestCase):
    """AC 10 and 12: desktop charts, pages, CSS and source data are untouched; only mobile chart SVGs change on the site."""

    def test_only_the_in_scope_mobile_svgs_change_on_the_site(self):
        out = subprocess.run(["git", "-C", ROOT, "diff", "--name-status", BASE], capture_output=True, check=True, text=True).stdout.splitlines()
        site = [ln for ln in out if not ln.split("\t", 1)[1].startswith(("docs/", "tests/", "tools/"))]
        self.assertTrue(site)
        for ln in site:
            self.assertRegex(ln, r"^M\t(charts/d/\d{7}-mobile\.svg|charts/chart3-nj-salary-distribution-mobile\.svg)$")

    def test_desktop_charts_equal_web_main(self):
        out = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", MAIN, "--", "charts", "data"],
                             capture_output=True, check=True, text=True).stdout.split()
        self.assertEqual([p for p in out if not re.fullmatch(r"charts/d/\d{7}-mobile\.svg|charts/chart3-nj-salary-distribution-mobile\.svg", p)], [])


if __name__ == "__main__":
    unittest.main()
