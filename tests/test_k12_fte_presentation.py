"""K12-FTE-PRESENTATION-001: superintendent salaries at FTE < 1 keep their published value and carry the approved part-time marker, badges and
notes. Counts are recounted fresh from the committed api/v1/nj JSON; the numbers below are goldens for this pin (web 02b5188f, data 42bfc2c3).
Every approved string (Lindsay's copy packet, sha abd37602) is pinned here as a literal, apart from tools/nj_fte_marks.py, so a change to the
tool's copy fails here. Charts are parsed independently of the tool. Tests that read git history skip only when git is missing."""
import contextlib
import glob
import io
import json
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
import nj_fte_marks as N  # noqa: E402
import nj_mobile_chart_fit as F  # noqa: E402
import nj_chart_label_edge as E  # noqa: E402  (K12-CHART-LABEL-EDGE-001: header and axis rule)
from chart_header_helpers import content_changes  # noqa: E402

BASE = "02b5188f6acd668c678b9e9de6622b7d3c8f43ad"  # web main this ticket starts from
GIT = shutil.which("git") is not None
needs_git = unittest.skipUnless(GIT, "git is needed")
ZERO_FIVE = [("3400069", "2019-20", "$6,892", "0.0"), ("3400930", "2024-25", "$201,571", "0.0"), ("3414790", "2019-20", "$10,000", "0.0"),
             ("3414790", "2023-24", "$15,000", "0.0"), ("3415420", "2026-27", "$169,320", "0")]
UNDER_ONE_KEY = {"3400069", "3400930", "3414790", "3415420"}
CLOSE = "Hollow dots mark years reported at less than one full-time position."
NOT_REPORTED = "Not reported ($0 in source)"


def rt(rel):
    with open(os.path.join(ROOT, *rel.split("/")), encoding="utf-8", newline="") as f:
        return f.read()


def rdf(path):
    with open(path, encoding="utf-8", newline="") as fh:
        return fh.read()


def at_base(rel):
    return subprocess.run(["git", "-C", ROOT, "show", f"{BASE}:{rel}"], capture_output=True, check=True).stdout.decode("utf-8")


def all_rows():
    """{leaid: JSON rows}, read fresh from the committed files."""
    out = {}
    for p in sorted(glob.glob(os.path.join(ROOT, "api", "v1", "nj", "[0-9]*.json"))):
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        out[d["nces_leaid"]] = d["superintendent_contracts"]
    return out


ROWS = all_rows()
PAGES = {leaid: p for p, leaid in N.pages()}


def is_part_time(r):
    return float(r["ufb_fte"]) < 1 and not r["salary_not_reported"]


def dollars(r):
    return f"${int(r['base_salary']):,}"


def badge_text(r):
    return f"Reported as {r['ufb_fte']} FTE" if float(r["ufb_fte"]) == 0 else f"Part-time · {r['ufb_fte']} FTE"


MARKED = {leaid: [r for r in rows if is_part_time(r)] for leaid, rows in ROWS.items()}
MARKED = {k: v for k, v in MARKED.items() if v}


def page_of(leaid):
    return rt(os.path.relpath(PAGES[leaid], ROOT).replace(os.sep, "/"))


def chart_dots(svg):
    """[(year, cy, fte or None)] per dot, parsed here: the dot's year is the tick label under its x."""
    year = {x: y for x, y in re.findall(r'<text x="([\d.]+)" y="(?:304|284)" text-anchor="middle">(\d{4}-\d\d)</text>', svg)}
    return [(cx, cy, f or None) for cx, cy, f in re.findall(
        r'<circle cx="([\d.]+)" cy="([\d.]+)" r="4" (?:fill="#458699"|fill="#fff" stroke="#458699" stroke-width="1\.5" class="pt" data-fte="([^"]*)")/>', svg)]


def desktop_dots(leaid):
    svg = rt(f"charts/d/{leaid}-desktop.svg")
    year = dict(re.findall(r'<text x="([\d.]+)" y="304" text-anchor="middle">(\d{4}-\d\d)</text>', svg))
    return [(year[cx], cy, f) for cx, cy, f in chart_dots(svg)]


class Recount(unittest.TestCase):
    """AC 1 and 3: the rule on the committed JSON, string forms numerically."""

    def test_counts_at_this_pin(self):
        rows = [r for rs in ROWS.values() for r in rs]
        self.assertEqual(len(rows), 4564)
        below = [r for r in rows if float(r["ufb_fte"]) < 1]
        self.assertEqual(len(below), 215)
        self.assertEqual(len({(r["nces_leaid"], r["school_year"]) for r in below}), 215)
        shown = [r for r in below if not r["salary_not_reported"]]
        self.assertEqual((len(shown), len({r["nces_leaid"] for r in shown})), (98, 44))
        self.assertEqual(len(below) - len(shown), 117)
        self.assertEqual(sorted((r["nces_leaid"], r["school_year"], dollars(r), r["ufb_fte"]) for r in shown if float(r["ufb_fte"]) == 0),
                         sorted(ZERO_FIVE))
        self.assertEqual(len(MARKED), 44)
        self.assertEqual(sum(len(v) for v in MARKED.values()), 98)
        self.assertEqual(sum(1 for rs in ROWS.values() if rs and rs[0]["school_year"] == "2026-27" and is_part_time(rs[0])), 10)  # the histogram's year; the table badges 16 (any year)

    def test_the_tool_counts_the_same(self):
        self.assertEqual({k: [r["school_year"] for r in v] for k, v in MARKED.items()},
                         {k: [r["school_year"] for r in N.marked_rows(ROWS[k])] for k in ROWS if N.marked_rows(ROWS[k])})

    def test_string_forms_are_handled_numerically(self):
        def row(fte, nr=False):
            return {"ufb_fte": fte, "salary_not_reported": nr, "base_salary": "0" if nr else "100000", "school_year": "2024-25"}
        for plain in ("1", "1.0", "1.00"):
            self.assertIsNone(N.marked_fte(row(plain)), plain)
        for part in ("0", "0.0", "0.2", "0.8"):
            self.assertEqual(N.marked_fte(row(part)), part)  # the raw string, never reformatted
        self.assertIsNone(N.marked_fte(row("0.0", nr=True)))  # below 1 FTE but no reported salary: no mark (AC 9)
        self.assertTrue(F.joined("0", "0.0") and F.joined("0.2", "0.20") and not F.joined("0.2", "0.3"))
        self.assertTrue(F.joined(None, None) and not F.joined(None, "0.2"))

    @needs_git
    def test_json_and_data_are_byte_identical_to_main(self):
        out = subprocess.run(["git", "-C", ROOT, "diff", "--stat", BASE, "--", "api", "data", "nj/history"], capture_output=True, check=True, text=True)
        self.assertEqual(out.stdout, "")


class Strings(unittest.TestCase):
    """Every approved string, exactly."""

    def test_badges_notes_and_captions(self):
        self.assertEqual(N.BADGE_PART_TIME.format(fte="0.2"), "Part-time · 0.2 FTE")
        self.assertEqual(N.BADGE_REPORTED.format(fte="0.0"), "Reported as 0.0 FTE")
        self.assertEqual(N.badge("0"), "Reported as 0 FTE")
        self.assertEqual(N.badge("0.3"), "Part-time · 0.3 FTE")
        self.assertEqual(N.suffix("0.2"), " (part-time, 0.2 FTE)")
        self.assertEqual(N.suffix("0.0"), " (reported as 0.0 FTE)")
        self.assertEqual(N.CAPTION_CLOSE, CLOSE)
        self.assertEqual(N.SUMMARY_NOTE.format(badge="Part-time · 0.2 FTE"),
                         '<p class="note"><span class="badge">Part-time · 0.2 FTE</span> Salary as published by the district to NJDOE. '
                         '<a href="/about/#part-time">Why</a></p>')
        self.assertEqual(N.HISTORY_NOTE.format(badge="Part-time · 0.2 FTE"),
                         '<p class="note"><span class="badge">Part-time · 0.2 FTE</span> See the note below.</p>')
        self.assertEqual(N.TERM_ENDED_PART_TIME_NOTE.format(badge="Part-time · 0.2 FTE"),
                         '<p class="note"><span class="badge">Term ended</span> <span class="badge">Part-time · 0.2 FTE</span> See the notes below.</p>')
        self.assertEqual(N.FTE_NOTE,
                         '<p class="note" id="fte-note">Part-time: the district reported the superintendent at less than one full-time position. '
                         'The FTE in the badge is that share of one full-time position, not a staff total. Salaries are as published by the '
                         'district to NJDOE. <a href="/about/#part-time">Why</a></p>')
        self.assertEqual(N.CHART_NOTE,
                         '<p class="note" id="fte-chart-note">Hollow dots are years the district reported at less than one full-time position, '
                         "usually part-time. Salaries are as published by the district to NJDOE, so these years don't compare directly with "
                         'full-time years. <a href="/about/#part-time">Why</a></p>')
        self.assertEqual(N.NJ_NOTE,
                         '<p class="note" id="fte-nj-note">Some values, including the lowest, are for part-time positions: the district reported '
                         'its superintendent at less than one full-time position. They are shown as published to NJDOE and marked in the table '
                         'below. <a href="/about/#part-time">Why</a></p>')
        self.assertEqual(N.NJ_CELL_BADGE.format(badge="Part-time · 0.3 FTE"), ' <span class="badge">Part-time · 0.3 FTE</span>')

    def test_about_block_and_llms_line(self):
        self.assertEqual(N.ABOUT_BLOCK,
                         '<h3 id="part-time">Part-time superintendents</h3><p>Some districts report their superintendent at less than one '
                         'full-time position. The budget file records this as FTE: 0.2 FTE is 0.2 of a full-time position, not a staff total. We '
                         "show each salary as the district published it to NJDOE and mark part-time years, which don't compare directly with "
                         'full-time years. Part-time is not the same as shared service. A salary reported at 0 or 0.0 FTE is shown as reported. '
                         'The JSON download names this field ufb_fte.</p>')
        self.assertEqual(N.LLMS_LINE,
                         'Partial FTE: superintendent rows with ufb_fte below 1 (string as published, such as "0.2", "0" or "0.0") are the '
                         "district's reported share of one full-time position, not a staff FTE total. Pages mark them \"Part-time · {fte} FTE\", "
                         'or "Reported as {fte} FTE" for 0 and 0.0. Salaries are values as published, never scaled.')

    def test_key_labels_and_the_nj_alt_text(self):
        self.assertEqual((F.KEY_LABEL, F.KEY_LABEL_ZERO), ("Part-time", "Under 1.0 FTE"))
        self.assertEqual(N.LOW_TAIL, ("3406630", "Hampton Twp"))
        alt = ("A histogram of 551 New Jersey districts by 2026-27 superintendent base salary, in $10,000 bins. Most districts sit between "
               "$150,000 and $280,000 (490 of 551), peaking at 54 districts in $190,000 to $199,999 and 55 in $220,000 to $229,999. The median is "
               "$206,606. A thin low tail reaches Hampton Twp at $56,225 (part-time, 0.3 FTE) and the high end is Newark City at $330,978.")
        page = rt("nj/index.html")
        self.assertEqual(page.count(alt), 2)  # the img alt and the figcaption, identical
        self.assertIn(f'alt="{alt}"', page)
        self.assertIn(f"<figcaption>{alt}</figcaption>", page)

    def test_the_committed_files_carry_the_strings(self):
        self.assertEqual(rt("about/index.html").count(N.ABOUT_BLOCK), 1)
        about = rt("about/index.html")
        self.assertIn('<h3 id="term-quirk">', about)
        self.assertEqual(about[about.index('<h3 id="term-quirk">'):].split("</p>", 1)[1][:len(N.ABOUT_BLOCK)], N.ABOUT_BLOCK)
        llms = rt("llms.txt")
        self.assertTrue(llms.endswith("\n" + N.LLMS_LINE + "\n"))
        self.assertEqual(llms.count("Partial FTE:"), 1)

    @needs_git
    def test_about_and_llms_change_only_by_the_insert(self):
        self.assertEqual(rt("about/index.html").replace(N.ABOUT_BLOCK, ""), at_base("about/index.html"))
        self.assertEqual(rt("llms.txt"), at_base("llms.txt") + N.LLMS_LINE + "\n")

    def test_copy_packet_when_present(self):
        packet = os.environ.get("K12_FTE_COPY_PACKET", "")  # path to the approved writing copy-packet.md (sha256 abd37602...), if available
        if not packet or not os.path.isfile(packet):
            self.skipTest("K12_FTE_COPY_PACKET is not set to the copy packet")
        text = rdf(packet)
        for s in (N.FTE_NOTE, N.CHART_NOTE, N.NJ_NOTE, N.ABOUT_BLOCK, N.LLMS_LINE, N.CAPTION_CLOSE, N.SUMMARY_NOTE.format(badge="Part-time · {fte} FTE"),
                  N.HISTORY_NOTE.format(badge="Part-time · {fte} FTE"), N.TERM_ENDED_PART_TIME_NOTE.format(badge="Part-time · {fte} FTE")):
            self.assertIn(s, text)


class Charts(unittest.TestCase):
    """AC 4, 5, 10, 14, 15, 17: the marker on the 44 desktop and mobile charts, parsed here."""

    def test_marked_dots_are_exactly_the_part_time_reported_rows(self):
        n = {"desktop": 0, "mobile": 0}
        for f in sorted(glob.glob(os.path.join(ROOT, "charts", "d", "*-desktop.svg"))):
            leaid = os.path.basename(f).split("-")[0]
            want = sorted((r["school_year"], r["ufb_fte"]) for r in MARKED.get(leaid, []))
            svg = rt(f"charts/d/{leaid}-desktop.svg")
            got = sorted((y, fte) for y, _, fte in desktop_dots(leaid) if fte is not None)
            self.assertEqual(got, want, leaid)
            n["desktop"] += len(got)
            mobile = rt(f"charts/d/{leaid}-mobile.svg")
            mdots = chart_dots(mobile)
            self.assertEqual([d[2] for d in mdots], [d[2] for d in chart_dots(svg)], leaid)  # carried by index
            n["mobile"] += sum(1 for d in mdots if d[2] is not None)
            self.assertEqual(svg.count('class="pt"'), len(want), leaid)
            self.assertEqual(mobile.count('class="pt"'), len(want), leaid)
        self.assertEqual(n, {"desktop": 98, "mobile": 98})

    def test_data_fte_is_the_published_string(self):
        for leaid, rows in MARKED.items():
            got = [(y, f) for y, _, f in desktop_dots(leaid) if f is not None]
            for (y, f), r in zip(sorted(got), sorted(rows, key=lambda r: r["school_year"])):
                self.assertEqual((y, f), (r["school_year"], r["ufb_fte"]))
        for leaid, year, _, fte in ZERO_FIVE:
            self.assertIn(f'class="pt" data-fte="{fte}"/>', rt(f"charts/d/{leaid}-desktop.svg"))

    def test_hollow_dot_form_and_the_key_is_last(self):
        for leaid in MARKED:
            for kind in ("desktop", "mobile"):
                svg = rt(f"charts/d/{leaid}-{kind}.svg")
                self.assertEqual(len(re.findall(r'<circle cx="[\d.]+" cy="[\d.]+" r="4" fill="#fff" stroke="#458699" stroke-width="1.5" class="pt" data-fte="0(?:\.\d)?"/>', svg)),
                                 len(MARKED[leaid]), (leaid, kind))
                label = "Under 1.0 FTE" if leaid in UNDER_ONE_KEY else "Part-time"
                m = re.search(r'<circle class="key" cx="([\d.]+)" cy="8\.0" r="4" fill="#fff" stroke="#458699" stroke-width="1\.5"/>'
                              rf'<text class="key" x="([\d.]+)" y="12\.0">{label}</text></svg>\Z', svg)
                self.assertIsNotNone(m, (leaid, kind))
                self.assertAlmostEqual(float(m.group(2)) - float(m.group(1)), 8, delta=0.11)
                self.assertEqual(svg.count('class="key"'), 2)
                self.assertTrue(svg.startswith('<svg xmlns="http://www.w3.org/2000/svg"'))

    def test_chart_with_no_part_time_dot_has_no_key_or_mark(self):
        for f in glob.glob(os.path.join(ROOT, "charts", "d", "*.svg")):
            leaid = os.path.basename(f).split("-")[0]
            if leaid not in MARKED and "chart3" not in f:
                svg = rt(os.path.relpath(f, ROOT).replace(os.sep, "/"))
                self.assertNotIn('class="pt"', svg, f)
                self.assertNotIn('class="key"', svg, f)

    @needs_git
    def test_only_the_44_districts_charts_change(self):
        out = content_changes(BASE, subprocess.run(["git", "-C", ROOT, "diff", "--name-only", BASE, "--", "charts/d"],
                                                   capture_output=True, check=True, text=True).stdout.split())  # K12-CHART-LABEL-EDGE-001: not counting the header; 3414220's desktop label y is its own test
        self.assertEqual(len(out), 88)
        self.assertEqual(sorted(out), sorted(f"charts/d/{leaid}-{k}.svg" for leaid in MARKED for k in ("desktop", "mobile")))
        self.assertEqual(subprocess.run(["git", "-C", ROOT, "diff", "--name-only", BASE, "--", "charts/chart3-nj-salary-distribution-desktop.svg",
                                         "charts/chart3-nj-salary-distribution-mobile.svg"], capture_output=True, check=True, text=True).stdout, "")

    @needs_git
    def test_values_dots_and_style_are_kept_and_lines_only_lose_segments(self):
        """AC 2 and OQ-4: every text.v, every dot's coordinates and the <style> block are byte-unchanged; a re-cut line keeps point strings."""
        v = re.compile(r'<text class="v"[^>]*>[^<]*</text>')
        dot = re.compile(r'<circle cx="([\d.]+)" cy="([\d.]+)" r="4"')
        style = re.compile(r"<style>.*?</style>")
        seg = lambda s: [(a, b) for pts in re.findall(r'<polyline[^>]*points="([^"]*)"', s) for a, b in zip(pts.split(), pts.split()[1:])]  # noqa: E731
        removed = 0
        for leaid in MARKED:
            old, new = at_base(f"charts/d/{leaid}-desktop.svg"), rt(f"charts/d/{leaid}-desktop.svg")
            if leaid == "3414220":  # K12-CHART-LABEL-EDGE-001: the one label the axis rule lifts above its dot (y 285.0 -> 270.0), nothing else
                new = new.replace('<text class="v" x="840.0" y="270.0">$20,000</text>', '<text class="v" x="840.0" y="285.0">$20,000</text>')
            self.assertEqual(v.findall(new), v.findall(old), leaid)
            self.assertEqual(dot.findall(new), dot.findall(old), leaid)
            self.assertEqual(style.findall(new), style.findall(old), leaid)
            rest = seg(old)
            for s in seg(new):
                rest.remove(s)
            removed += len(rest)
            # the line rule, read back: every segment joins two full-time or two same-FTE part-time dots
            at = {f"{x},{y}": f for x, y, f in chart_dots(new)}
            for a, b in seg(new):
                self.assertTrue((at[a] is None and at[b] is None) or (at[a] is not None and at[b] is not None and float(at[a]) == float(at[b])), (leaid, a, b))
        self.assertEqual(removed, 73)  # the dataviz packet: 73 of 3,812 segments removed in 41 of the 44 charts

    @needs_git
    def test_write_rebuilds_the_committed_charts_from_main_and_a_second_write_changes_nothing(self):
        """Desktop (nj_fte_marks) and mobile (nj_mobile_chart_fit --write) from the 02b5188f charts reproduce the committed ones, for all 573 pairs."""
        with tempfile.TemporaryDirectory(prefix="k12-fte-charts-") as tmp:
            tar = subprocess.run(["git", "-C", ROOT, "archive", BASE, "charts"], capture_output=True, check=True).stdout
            subprocess.run(["tar", "-x", "-C", tmp], input=tar, check=True)
            charts = os.path.join(tmp, "charts", "d")
            for f in sorted(glob.glob(os.path.join(charts, "*-desktop.svg"))):
                leaid = os.path.basename(f).split("-")[0]
                rows = ROWS[leaid]
                with open(f, encoding="utf-8", newline="") as fh:
                    cur = fh.read()
                with open(f, "w", encoding="utf-8", newline="") as fh:
                    fh.write(N.render_chart(cur, rows))
                self.assertEqual(N.render_chart(N.render_chart(cur, rows), rows), N.render_chart(cur, rows), leaid)  # idempotent
            dist = os.path.join(tmp, "charts", "chart3-nj-salary-distribution-mobile.svg")
            with mock.patch.object(F, "CHARS", charts), mock.patch.object(F, "DISTRIBUTION", dist), contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(F.main(["--write"]), 0, out.getvalue())
            self.assertIn("573 mobile charts, 44 rewritten, 0 still misfit", out.getvalue())
            with mock.patch.object(F, "CHARS", charts), mock.patch.object(F, "DISTRIBUTION", dist), contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(F.main(["--write"]), 0)
                self.assertEqual(F.main(["--check"]), 0)
            self.assertIn("573 mobile charts, 0 rewritten, 0 still misfit", out.getvalue())
            for f in glob.glob(os.path.join(charts, "*.svg")):
                self.assertEqual(E.convert(f, rdf(f)) if "chart3" not in f else rdf(f), rt("charts/d/" + os.path.basename(f)), f)  # + headroom header, axis rule


class MobileGate(unittest.TestCase):
    """AC 14: `--check` fails on a missing or extra mark, a joined segment the rule separates, and a missing, extra, wrong or crowded key."""

    @classmethod
    def setUpClass(cls):
        cls.leaid = "3414790"  # 4 marked dots: two FTE 0.0, with full-time dots between them
        cls.svg = rt(f"charts/d/{cls.leaid}-mobile.svg")
        cls.desktop = rt(f"charts/d/{cls.leaid}-desktop.svg")
        cls.ftes = F.expected_ftes(cls.desktop, ROWS[cls.leaid])

    def problems(self, svg, ftes=None):
        return F.problems(svg, self.desktop, self.ftes if ftes is None else ftes)

    def test_the_committed_chart_is_clean(self):
        self.assertEqual(self.problems(self.svg), [])
        self.assertEqual(sum(f is not None for f in self.ftes), len(MARKED[self.leaid]))

    def test_a_removed_mark_fails(self):
        m = re.search(r'<circle cx="([\d.]+)" cy="([\d.]+)" r="4" fill="#fff" stroke="#458699" stroke-width="1.5" class="pt" data-fte="[^"]*"/>', self.svg)
        bad = self.svg.replace(m.group(0), f'<circle cx="{m.group(1)}" cy="{m.group(2)}" r="4" fill="#458699"/>', 1)
        self.assertTrue(any("not marked" in p for p in self.problems(bad)), self.problems(bad))

    def test_an_extra_mark_fails(self):
        m = re.search(r'<circle cx="([\d.]+)" cy="([\d.]+)" r="4" fill="#458699"/>', self.svg)
        bad = self.svg.replace(m.group(0), f'<circle cx="{m.group(1)}" cy="{m.group(2)}" r="4" fill="#fff" stroke="#458699" stroke-width="1.5" class="pt" data-fte="0.5"/>', 1)
        self.assertTrue(any("marked part-time" in p for p in self.problems(bad)), self.problems(bad))

    def test_a_wrong_data_fte_fails(self):
        bad = self.svg.replace('data-fte="0.0"', 'data-fte="0.5"', 1)
        self.assertTrue(any("data-fte 0.5" in p for p in self.problems(bad)), self.problems(bad))

    def test_a_segment_the_rule_separates_fails(self):
        # join the first two dots (a hollow and a full-time one, or two unlike ones) with one line
        dots = re.findall(r'<circle cx="([\d.]+)" cy="([\d.]+)" r="4"', self.svg)
        flags = F.dot_ftes(self.svg)
        i = next(i for i in range(len(dots) - 1) if not F.joined(flags[i], flags[i + 1]))
        line = f'<polyline fill="none" stroke="#458699" stroke-width="3" points="{dots[i][0]},{dots[i][1]} {dots[i + 1][0]},{dots[i + 1][1]}"/>'
        bad = self.svg.replace("<circle", line + "<circle", 1)
        self.assertTrue(any("the FTE rule separates" in p for p in self.problems(bad)), self.problems(bad))

    def test_key_problems(self):
        key = re.search(r'<circle class="key".*?</text>', self.svg).group(0)
        self.assertEqual(self.problems(self.svg.replace(key, "")), ["a part-time dot but no key"])
        self.assertTrue(any("2 keys" in p for p in self.problems(self.svg.replace(key, key + key))))
        self.assertTrue(any("reads 'Part-time'" in p for p in self.problems(self.svg.replace("Under 1.0 FTE", "Part-time"))))
        # a key placed over the plot's data (within the pads) or outside the plot
        first = re.search(r'<circle cx="([\d.]+)" cy="([\d.]+)" r="4"', self.svg).groups()
        for cx, cy in (first, ("20.0", "8.0")):  # on a dot; left of the plot
            moved = re.sub(r'(<circle class="key" cx=")[\d.]+(" cy=")[\d.]+', rf"\g<1>{cx}\g<2>{cy}", key)
            moved = re.sub(r'(<text class="key" x=")[\d.]+(" y=")[\d.]+', rf"\g<1>{float(cx) + 8}\g<2>{float(cy) + 4}", moved)
            self.assertTrue(any("key is within" in p for p in self.problems(self.svg.replace(key, moved))), (cx, cy))

    def test_a_key_on_a_chart_with_no_part_time_dot_fails(self):
        toms = rt("charts/d/3416230-mobile.svg")
        toms_desktop = rt("charts/d/3416230-desktop.svg")
        key = re.search(r'<circle class="key".*?</text>', self.svg).group(0)
        bad = toms.replace("</svg>", key + "</svg>")
        self.assertTrue(F.DISTRICT.match(bad))
        self.assertTrue(any("key on a chart with no part-time dot" in p for p in F.problems(bad, toms_desktop, F.expected_ftes(toms_desktop, ROWS["3416230"]))))

    def test_check_exits_1_on_a_fixture_with_one_marker_removed(self):
        with tempfile.TemporaryDirectory(prefix="k12-fte-gate-") as tmp:
            for kind in ("mobile", "desktop"):
                shutil.copy(os.path.join(ROOT, "charts", "d", f"{self.leaid}-{kind}.svg"), tmp)
            f = os.path.join(tmp, f"{self.leaid}-mobile.svg")
            svg = rdf(f)
            m = re.search(r'<circle cx="([\d.]+)" cy="([\d.]+)" r="4" fill="#fff" [^>]*/>', svg)
            with open(f, "w", encoding="utf-8", newline="") as fh:
                fh.write(svg.replace(m.group(0), f'<circle cx="{m.group(1)}" cy="{m.group(2)}" r="4" fill="#458699"/>', 1))
            dist = os.path.join(ROOT, "charts", "chart3-nj-salary-distribution-mobile.svg")
            with mock.patch.object(F, "CHARS", tmp), mock.patch.object(F, "DISTRIBUTION", dist), contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(F.main(["--check"]), 1)
            self.assertIn("not marked", out.getvalue())

    def test_all_mobile_charts_and_the_distribution_pass_at_both_widths(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(F.main(["--check"]), 0, out.getvalue())
        self.assertIn("573 mobile charts, 0 rewritten, 0 still misfit", out.getvalue())
        self.assertIn("text nodes under 12 px: 0 at 304 px, 0 at 358 px", out.getvalue())
        for leaid in MARKED:
            svg = rt(f"charts/d/{leaid}-mobile.svg")
            key = [(t, px) for t, px in F.text_sizes(svg)[1] if t in ("Part-time", "Under 1.0 FTE")]
            self.assertEqual(len(key), 1)
            for w in F.CONTENT_PX:
                self.assertGreaterEqual(key[0][1] * w / 304, 12)


class DistrictPages(unittest.TestCase):
    """AC 5-10: the 44 pages."""

    def test_the_chart_note_is_on_exactly_the_44_pages_after_the_chart(self):
        with_note = set()
        for leaid, p in PAGES.items():
            page = page_of(leaid)
            if 'id="fte-chart-note"' in page:
                with_note.add(leaid)
                self.assertEqual(page.count(N.CHART_NOTE), 1)
                self.assertIn("</figure>" + N.CHART_NOTE, page)
                self.assertGreaterEqual(len(MARKED[leaid]), 1)
                self.assertIn('class="pt"', rt(f"charts/d/{leaid}-desktop.svg"))
                self.assertEqual(page.count('id="fte-note"'), 1)
            else:
                for s in ("fte-note", "Part-time", "Reported as", "(part-time,", "(reported as", "Hollow dots", "about/#part-time"):
                    self.assertNotIn(s, page, (leaid, s))
        self.assertEqual(with_note, set(MARKED))

    def test_fte_note_follows_the_term_note_else_the_history_list(self):
        for leaid in MARKED:
            page = page_of(leaid)
            if 'id="term-note"' in page:
                self.assertRegex(page, r'<p class="note" id="term-note">[^<]*<a href="/about/#term-quirk">Why</a></p>' + re.escape(N.FTE_NOTE))
            else:
                self.assertIn("</ol>" + N.FTE_NOTE, page)

    def test_alt_and_figcaption_are_identical_and_carry_each_fte(self):
        for leaid, rows in MARKED.items():
            page = page_of(leaid)
            alt = re.search(r'<img [^>]*alt="([^"]*)"', page).group(1)
            cap = re.search(r"<figcaption>(.*?)</figcaption>", page).group(1)
            self.assertEqual(alt, cap, leaid)
            self.assertTrue(cap.endswith(" " + CLOSE), leaid)
            for r in rows:
                want = f"{r['school_year']} {dollars(r)} " + (f"(reported as {r['ufb_fte']} FTE)" if float(r["ufb_fte"]) == 0 else f"(part-time, {r['ufb_fte']} FTE)")
                self.assertEqual(cap.count(want), 1, (leaid, want))
            self.assertEqual(len(re.findall(r"\((?:part-time,|reported as) 0[.\d]* FTE\)", cap)), len(rows), leaid)
            self.assertEqual(cap.count(CLOSE), 1)

    @needs_git
    def test_history_rows(self):
        badges = 0
        for leaid, rows in MARKED.items():
            new, old = page_of(leaid), at_base(os.path.relpath(PAGES[leaid], ROOT).replace(os.sep, "/"))
            li = re.compile(r'<li class="hrow">.*?</li>')
            news, olds = li.findall(new), li.findall(old)
            self.assertEqual(len(news), len(olds))
            self.assertEqual(len(olds), len(ROWS[leaid]))
            for n, o, r in zip(news, olds, ROWS[leaid]):
                if not is_part_time(r):
                    self.assertEqual(n, o, (leaid, r["school_year"]))  # rows at FTE >= 1 and not-reported rows below 1 FTE: byte-unchanged
                    continue
                badges += 1
                meta = re.search(r'<p class="hmeta">.*?</p>', o)
                tail = o[meta.end():]
                text = badge_text(r)
                if tail.startswith('<p class="note"><span class="badge">Term ended</span> See the note below.</p>'):
                    mid = f'<p class="note"><span class="badge">Term ended</span> <span class="badge">{text}</span> See the notes below.</p>'
                    tail = tail[len('<p class="note"><span class="badge">Term ended</span> See the note below.</p>'):]
                else:
                    mid = f'<p class="note"><span class="badge">{text}</span> See the note below.</p>'
                self.assertEqual(n, o[:meta.end()] + mid + tail, (leaid, r["school_year"]))
        self.assertEqual(badges, 98)

    def test_roosevelt_golden(self):
        page = page_of("3414220")
        self.assertIn('<span class="hy num">2024-25</span><span class="hs num">$20,000</span></div><p class="hmeta">Superintendent · contract '
                      '<span class="num">2023-07-01 – 2024-06-30</span> · 52 work days · 0 vacation · 0 sick · shared service yes</p>'
                      '<p class="note"><span class="badge">Term ended</span> <span class="badge">Part-time · 0.2 FTE</span> See the notes below.</p>', page)
        self.assertIn("2019-20 $130,000; 2021-22 $130,000; 2024-25 $20,000 (part-time, 0.2 FTE). Not reported ($0 in source) for 2022-23, 2023-24, "
                      "2026-27, left out of the chart. " + CLOSE, page)
        self.assertIn(f'<p class="big num">{NOT_REPORTED}</p><dl class="facts">', page)  # the summary row is Not reported: no badge
        self.assertEqual(page.count("Part-time · 0.2 FTE"), 1)
        self.assertEqual(page.count('class="badge">Term ended'), 1)
        self.assertEqual(page.count("See the note below."), 0)
        # the term note and the part-time note: Term ended first, then the part-time note after it
        self.assertIn('<a href="/about/#term-quirk">Why</a></p>' + N.FTE_NOTE, page)

    def test_latest_summaries(self):
        pages = {}
        for leaid in PAGES:
            page = page_of(leaid)
            m = re.search(r'<p class="big num">([^<]*)</p>(<p class="note"><span class="badge">[^<]*</span> Salary as published[^<]*<a href="/about/#part-time">Why</a></p>)?', page)
            pages[leaid] = m.groups()
        want = {leaid for leaid, rows in ROWS.items() if rows and is_part_time(rows[0])}
        self.assertEqual(len(want), 14)
        self.assertEqual({k for k, (_, note) in pages.items() if note}, want)
        for leaid in want:
            big, note = pages[leaid]
            self.assertEqual(big, dollars(ROWS[leaid][0]))
            self.assertEqual(note, N.SUMMARY_NOTE.format(badge=badge_text(ROWS[leaid][0])))
        self.assertIsNone(pages["3414220"][1])
        self.assertIn('<span class="badge">Part-time · 0.3 FTE</span> Salary as published by the district to NJDOE.', page_of("3406630"))
        self.assertIn('<p class="big num">$169,320</p><p class="note"><span class="badge">Reported as 0 FTE</span> Salary as published', page_of("3415420"))

    def test_the_five_zero_fte_goldens(self):
        for leaid, year, value, fte in ZERO_FIVE:
            page = page_of(leaid)
            self.assertIn(f"{year} {value} (reported as {fte} FTE)", page)
            self.assertIn(f'<span class="hy num">{year}</span><span class="hs num">{value}</span>', page)
            self.assertRegex(page, rf'<span class="hy num">{year}</span><span class="hs num">\{value}</span></div><p class="hmeta">.*?</p><p class="note">'
                                   rf'(?:<span class="badge">Term ended</span> )?<span class="badge">Reported as {re.escape(fte)} FTE</span> See the notes? below\.</p>')
            self.assertNotIn(f"Part-time · {fte} FTE", page)
            self.assertIn(f'data-fte="{fte}"/>', rt(f"charts/d/{leaid}-desktop.svg"))
            self.assertIn(f'data-fte="{fte}"/>', rt(f"charts/d/{leaid}-mobile.svg"))

    def test_no_name_no_partner_no_free_text(self):
        for leaid in MARKED:
            page = page_of(leaid)
            for word in ("person_name", "ufb_comments", "ufb_shared_job_desc", "Plantedname"):
                self.assertNotIn(word, page)

    @needs_git
    def test_every_other_byte_of_a_page_is_unchanged(self):
        """Removing this ticket's markup gives the main page back exactly (AC 2, 9, 17); every salary string is the same multiset."""
        for leaid in PAGES:
            rel = os.path.relpath(PAGES[leaid], ROOT).replace(os.sep, "/")
            new, old = rt(rel), at_base(rel)
            self.assertEqual(N.strip_district(new), old, rel)
            self.assertEqual(sorted(re.findall(r"\$[\d,]+", new)), sorted(re.findall(r"\$[\d,]+", old)), rel)
            for cls in ("hs num", "big num"):
                self.assertEqual(re.findall(rf'<[a-z]+ class="{cls}">([^<]*)<', new), re.findall(rf'<[a-z]+ class="{cls}">([^<]*)<', old), (rel, cls))
            if leaid not in MARKED:
                self.assertEqual(new, old, rel)

    @needs_git
    def test_no_derived_number_anywhere(self):
        """The only new digits are the FTE strings the JSON publishes: strip the approved copy and nothing remains."""
        for leaid in MARKED:
            page = page_of(leaid)
            shown = re.findall(r"(?<![\d.$,])(\d+(?:\.\d+)?) FTE\b", page)
            self.assertTrue(shown, leaid)
            self.assertLessEqual(set(shown), {r["ufb_fte"] for r in ROWS[leaid]}, leaid)  # each is a ufb_fte string of this district, as published
            for dollars_ in re.findall(r"\$[\d,]+", page):
                self.assertIn(dollars_, {dollars(r) for r in ROWS[leaid]} | {"$20k"} | set(re.findall(r"\$[\d,]+k?", at_base(os.path.relpath(PAGES[leaid], ROOT).replace(os.sep, "/")))), (leaid, dollars_))


class NjPage(unittest.TestCase):
    """AC 11: /nj/."""

    def test_sixteen_badges_in_the_table(self):
        page = rt("nj/index.html")
        cells = re.findall(r'<a href="/nj/[^"]*-(\d+)/">[^<]*</a></th><td>[^<]*</td><td class="num">(\$[\d,]+)( <span class="badge">[^<]*</span>)?</td><td><span class="muted">(\d{4}-\d\d)</span>', page)
        self.assertEqual(len(cells), 575)  # the districts with a latest reported salary (a golden for this pin)
        # recomputed fresh from the JSON: the reported row(s) of the year and value the table shows, part-time when float(ufb_fte) < 1
        want = {}
        for leaid, value, _, year in cells:
            hit = [r for r in ROWS[leaid] if r["school_year"] == year and not r["salary_not_reported"] and dollars(r) == value]
            self.assertTrue(hit, leaid)
            if float(hit[0]["ufb_fte"]) < 1:
                want[leaid] = hit[0]
        self.assertEqual(len(want), 16)
        got = {leaid: b for leaid, _, b, year in cells if b}
        self.assertEqual(set(got), set(want))
        for leaid, b in got.items():
            self.assertEqual(b, f' <span class="badge">{badge_text(want[leaid])}</span>')
        self.assertIn('<td class="num">$56,225 <span class="badge">Part-time · 0.3 FTE</span></td>', page)
        self.assertIn('<td class="num">$169,320 <span class="badge">Reported as 0 FTE</span></td>', page)
        self.assertEqual(page.count('class="badge">Part-time'), 14)
        self.assertEqual(page.count('class="badge">Reported as'), 2)

    def test_the_six_earlier_year_rows_carry_their_exact_badges(self):
        page = rt("nj/index.html")
        for leaid, value, year, fte, text in [("3400069", "$12,000", "2020-21", "0.1", "Part-time · 0.1 FTE"),
                                              ("3401020", "$61,200", "2023-24", "0.3", "Part-time · 0.3 FTE"),
                                              ("3407050", "$61,800", "2023-24", "0.3", "Part-time · 0.3 FTE"),
                                              ("3407200", "$69,500", "2020-21", "0.1", "Part-time · 0.1 FTE"),
                                              ("3414220", "$20,000", "2024-25", "0.2", "Part-time · 0.2 FTE"),
                                              ("3414790", "$15,000", "2023-24", "0.0", "Reported as 0.0 FTE")]:
            self.assertTrue(any(r["school_year"] == year and dollars(r) == value and r["ufb_fte"] == fte for r in ROWS[leaid]), leaid)
            row = re.search(r'<a href="/nj/[^"]*-' + leaid + r'/">[^<]*</a></th><td>[^<]*</td>(<td class="num">[^<]*(?:<span[^<]*</span>)?</td>)<td><span class="muted">' + year + "</span>", page)
            self.assertTrue(row, leaid)
            self.assertEqual(row.group(1), f'<td class="num">{value} <span class="badge">{text}</span></td>', leaid)

    def test_the_note_follows_the_histogram_before_the_list(self):
        page = rt("nj/index.html")
        self.assertEqual(page.count(N.NJ_NOTE), 1)
        self.assertRegex(page, r"</figcaption></figure>" + re.escape(N.NJ_NOTE) + r'\n<h2 id="list">')

    @needs_git
    def test_every_other_byte_of_nj_is_unchanged_and_values_are_kept(self):
        new, old = rt("nj/index.html"), at_base("nj/index.html")
        self.assertEqual(N.strip_nj(new), old)
        self.assertEqual(re.findall(r'<td class="num">(\$[\d,]+)', new), re.findall(r'<td class="num">(\$[\d,]+)', old))
        self.assertEqual(sorted(re.findall(r"\$[\d,]+", new)), sorted(re.findall(r"\$[\d,]+", old)))

    @needs_git
    def test_histogram_svgs_are_byte_identical(self):
        out = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", BASE, "--", "charts/chart3-nj-salary-distribution-desktop.svg"],
                             capture_output=True, check=True, text=True).stdout
        self.assertEqual(out, "")

    @needs_git
    def test_css_gains_only_the_badge_wrap_rule(self):
        old, new = at_base("style.css").splitlines(), rt("style.css").splitlines()
        self.assertEqual([ln for ln in old if ln not in new], [])
        added = [ln for ln in new if ln not in old and "K12-FTE-PRESENTATION-001" in ln]
        self.assertEqual(len(added), 2, added)
        self.assertTrue(added[0].startswith("td.num>.badge{display:flex;width:fit-content;margin-left:auto;"))
        self.assertTrue(added[1].lstrip().startswith("#districts td.num>.badge{margin-left:0}"))
        self.assertFalse(any(re.search(r"td\.num\s*(>\s*)?\.badge", ln) for ln in old))  # nothing like it existed
        self.assertEqual([ln for ln in new if ln not in old], added)  # and nothing else


class Fixtures(unittest.TestCase):
    """AC 1 (two rows in a year), AC 18 (canary), AC 14/15 (check, idempotence) on fixtures built from real files."""

    @classmethod
    def setUpClass(cls):
        cls.leaid = "3401470"  # two 2026-27 rows, all full-time at this pin
        cls.rows = json.loads(json.dumps(ROWS[cls.leaid]))
        cls.svg = rt(f"charts/d/{cls.leaid}-desktop.svg")
        cls.page = page_of(cls.leaid)

    def test_this_district_has_two_full_time_rows_in_2026_27(self):
        self.assertEqual([(r["school_year"], r["ufb_fte"]) for r in self.rows[:2]], [("2026-27", "1"), ("2026-27", "1")])
        self.assertEqual(N.render_chart(self.svg, self.rows), self.svg)  # nothing to mark: unchanged
        self.assertEqual(N.rewrite_district(self.page, self.rows), self.page)

    def test_one_part_time_row_of_two_marks_only_that_dot(self):
        rows = json.loads(json.dumps(self.rows))
        rows[1]["ufb_fte"] = "0.5"
        out = N.render_chart(self.svg, rows)
        dots = chart_dots(out)
        self.assertEqual([i for i, d in enumerate(dots) if d[2] is not None], [len(dots) - 1])  # the second 2026-27 dot only
        self.assertEqual(dots[-1][2], "0.5")
        self.assertEqual(out.count('class="pt"'), 1)
        self.assertEqual(out.count('class="key"'), 2)
        page = N.rewrite_district(self.page, rows)
        self.assertEqual(page.count("Part-time · 0.5 FTE"), 1)
        self.assertEqual(page.count('id="fte-chart-note"') + page.count('id="fte-note"'), 2)
        self.assertIn("2026-27 $329,189; 2026-27 $88,509 (part-time, 0.5 FTE).", page)
        self.assertNotIn("$329,189 (part-time", page)
        self.assertNotIn('<p class="big num">$329,189</p><p class="note">', page)  # the summary row is the full-time one
        self.assertEqual(N.strip_district(page), self.page)  # and removing it leaves the original page
        rows[0]["ufb_fte"] = "0.5"
        self.assertIn('<p class="big num">$329,189</p><p class="note"><span class="badge">Part-time · 0.5 FTE</span>', N.rewrite_district(self.page, rows))

    def test_rows_below_one_fte_without_a_salary_are_not_marked(self):
        rows = json.loads(json.dumps(self.rows))
        rows[3]["ufb_fte"] = "0.5"
        rows[3]["salary_not_reported"], rows[3]["base_salary"] = True, "0"
        with self.assertRaises(ValueError):  # the chart still draws that year's dot: the rows no longer match the chart
            N.render_chart(self.svg, rows)

    def test_planted_name_never_reaches_output(self):
        rows = json.loads(json.dumps(ROWS["3414220"]))
        for r in rows:
            r["person_name"] = r["ufb_comments"] = r["ufb_shared_job_desc"] = "Jane Plantedname"
        svg, page = rt("charts/d/3414220-desktop.svg"), page_of("3414220")
        outs = [N.render_chart(svg, rows), N.rewrite_district(page, rows), N.rewrite_nj(rt("nj/index.html"), lambda leaid: rows if leaid == "3414220" else ROWS[leaid])]
        for o in outs:
            self.assertNotIn("Plantedname", o)
            self.assertNotIn("Jane", o)
        self.assertEqual(outs[0], svg)  # the committed chart is already this chart
        self.assertEqual(outs[1], page)
        self.assertEqual(N.render_chart(svg, ROWS["3414220"]), svg)

    def tree(self, tmp):
        os.makedirs(os.path.join(tmp, "charts", "d"))
        for leaid in ("3414220", "3416230"):
            for kind in ("desktop", "mobile"):
                shutil.copy(os.path.join(ROOT, "charts", "d", f"{leaid}-{kind}.svg"), os.path.join(tmp, "charts", "d"))
            rel = os.path.relpath(PAGES[leaid], ROOT)
            os.makedirs(os.path.join(tmp, os.path.dirname(rel)))
            shutil.copy(PAGES[leaid], os.path.join(tmp, rel))
        for rel in ("nj/index.html", "about/index.html", "llms.txt"):
            os.makedirs(os.path.dirname(os.path.join(tmp, rel)), exist_ok=True)
            shutil.copy(os.path.join(ROOT, rel), os.path.join(tmp, rel))

    def run_tool(self, tmp, arg):
        with mock.patch.object(N, "ROOT", tmp), mock.patch.object(F, "CHARS", os.path.join(tmp, "charts", "d")), contextlib.redirect_stdout(io.StringIO()) as out:
            code = N.main([arg])
        return code, out.getvalue()

    @needs_git
    def test_check_fails_on_a_removed_or_extra_marker_and_write_repairs_it(self):
        with tempfile.TemporaryDirectory(prefix="k12-fte-check-") as tmp:
            self.tree(tmp)
            self.assertEqual(self.run_tool(tmp, "--check")[0], 0)
            f = os.path.join(tmp, "charts", "d", "3414220-desktop.svg")
            good = rdf(f)
            for name, bad in (("removed", good.replace('fill="#fff" stroke="#458699" stroke-width="1.5" class="pt" data-fte="0.2"', 'fill="#458699"')),
                              ("extra", good.replace('<circle cx="64.0" cy="24.0" r="4" fill="#458699"/>',
                                                     '<circle cx="64.0" cy="24.0" r="4" fill="#fff" stroke="#458699" stroke-width="1.5" class="pt" data-fte="0.5"/>')),
                              ("key gone", re.sub(r'<circle class="key".*?</text>', "", good)),
                              ("wrong label", good.replace(">Part-time<", ">Under 1.0 FTE<"))):
                self.assertNotEqual(bad, good, name)
                with open(f, "w", encoding="utf-8", newline="") as fh:
                    fh.write(bad)
                code, out = self.run_tool(tmp, "--check")
                self.assertEqual(code, 1, name)
                self.assertIn("3414220-desktop.svg", out)
                self.assertEqual(self.run_tool(tmp, "--write")[0], 0)
                self.assertEqual(rdf(f), good, name)
            # a page with a missing badge, a wrong caption suffix, a stray note and a plain page with a stray marker
            p = os.path.join(tmp, os.path.relpath(PAGES["3414220"], ROOT))
            good = rdf(p)
            for name, bad in (("badge", good.replace('<span class="badge">Part-time · 0.2 FTE</span> ', "")),
                              ("suffix", good.replace("(part-time, 0.2 FTE)", "(part-time, 0.3 FTE)")),
                              ("note", good.replace(N.FTE_NOTE, "")), ("chart note", good.replace(N.CHART_NOTE, N.CHART_NOTE * 2))):
                self.assertNotEqual(bad, good, name)
                with open(p, "w", encoding="utf-8", newline="") as fh:
                    fh.write(bad)
                self.assertEqual(self.run_tool(tmp, "--check")[0], 1, name)
            with open(p, "w", encoding="utf-8", newline="") as fh:
                fh.write(good)
            t = os.path.join(tmp, os.path.relpath(PAGES["3416230"], ROOT))
            toms = rdf(t)
            with open(t, "w", encoding="utf-8", newline="") as fh:
                fh.write(toms.replace("</ol>", "</ol>" + N.FTE_NOTE, 1))
            self.assertEqual(self.run_tool(tmp, "--check")[0], 1)  # a note on a page with no part-time row

    @needs_git
    def test_double_write_is_idempotent_on_a_temp_copy_of_main(self):
        with tempfile.TemporaryDirectory(prefix="k12-fte-write-") as tmp:
            self.tree(tmp)
            # put the files back to main's bytes, then write twice
            for rel in ("nj/index.html", "about/index.html", "llms.txt", os.path.relpath(PAGES["3414220"], ROOT), os.path.relpath(PAGES["3416230"], ROOT),
                        "charts/d/3414220-desktop.svg", "charts/d/3416230-desktop.svg"):
                with open(os.path.join(tmp, rel), "w", encoding="utf-8", newline="") as fh:
                    fh.write(at_base(rel.replace(os.sep, "/")))
            self.assertEqual(self.run_tool(tmp, "--check")[0], 1)
            code, out = self.run_tool(tmp, "--write")
            self.assertEqual(code, 0)
            self.assertIn("5 files rewritten", out)  # 3414220's chart and page, /nj/, /about/, llms.txt; Toms River (no part-time row) stays as main
            code, out = self.run_tool(tmp, "--write")
            self.assertIn("0 files rewritten", out)
            self.assertEqual(self.run_tool(tmp, "--check")[0], 0)
            for rel in ("nj/index.html", "about/index.html", "llms.txt", os.path.relpath(PAGES["3414220"], ROOT), "charts/d/3414220-desktop.svg"):
                got = rdf(os.path.join(tmp, rel))
                if rel.endswith(".svg"):
                    got = E.convert(rel, got)  # K12-CHART-LABEL-EDGE-001: the chain's last step (headroom header, axis rule)
                self.assertEqual(got, rt(rel.replace(os.sep, "/")), rel)


class Docs(unittest.TestCase):
    def test_docstrings_describe_the_marker_key_and_line_rule(self):
        doc = F.__doc__
        for s in ("class=\"pt\"", "data-fte", "Under 1.0 FTE", "Part-time", "same numeric FTE", "KEY_SPOTS", "tools/nj_fte_marks.py", "--check"):
            self.assertIn(s, doc)
        self.assertIn("nj_mobile_chart_fit", N.__doc__)
        self.assertIn("--check", N.__doc__)

    def test_the_docs_name_the_tool(self):
        self.assertIn("nj_fte_marks.py", rt("docs/nj-history.md"))


if __name__ == "__main__":
    unittest.main()
