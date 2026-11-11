"""Leftovers 7 and 10 of K12-SITE-NJ-HISTORY-001: mobile guide tables and charts fit at 336/390 px; /api/v1/nj/ has an index.
Static checks against the committed tree and web main a41b5838 (the tree these fixes start from). Real-browser widths are builder evidence."""
import os
import re
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import nj_api_index as A  # noqa: E402
import nj_mobile_chart_fit as F  # noqa: E402

FIX_BASE = "a41b583835f15b30bb5a398c94beaa1e22e8297d"  # web main before these fixes


def rt(rel):
    with open(os.path.join(ROOT, *rel.split("/")), encoding="utf-8", newline="") as f:
        return f.read()


def at_base(rel):
    return subprocess.run(["git", "-C", ROOT, "show", f"{FIX_BASE}:{rel}"], capture_output=True, check=True).stdout.decode()


def svg_labels_removed(svg):
    """The SVG with its value labels and x-axis year labels taken out (the only parts leftover 7b may change)."""
    return F.TICK.sub("", F.VALUE.sub("", svg))


class Leftover7aGuideTables(unittest.TestCase):
    def test_guide_cells_do_not_wrap_on_mobile(self):
        css = rt("style.css")
        m = re.search(r"@media \(max-width:640px\)\{\.grid th,\.grid td\.num\{white-space:nowrap\}\}", css)
        self.assertIsNotNone(m)

    def test_only_that_line_is_added_to_style_css(self):
        old, new = at_base("style.css").splitlines(), rt("style.css").splitlines()
        added = [ln for ln in new if ln not in old]
        self.assertEqual([ln for ln in old if ln not in new], [])
        self.assertEqual(len(added), 1, added)
        self.assertIn(".grid td.num", added[0])

    def test_guide_tables_scroll_inside_their_region(self):
        css = rt("style.css")
        self.assertIn("@media (max-width:640px){.grid .table-wrap{overflow:auto;", css)


class Leftover7bMobileCharts(unittest.TestCase):
    def test_every_mobile_chart_fits(self):
        bad = {f: F.problems(rt(os.path.relpath(f, ROOT).replace(os.sep, "/"))) for f in F.files()}
        bad = {k: v for k, v in bad.items() if v}
        self.assertEqual(len(F.files()), 573)
        self.assertEqual(bad, {})

    def test_fit_is_idempotent(self):
        for f in F.files():
            s = rt(os.path.relpath(f, ROOT).replace(os.sep, "/"))
            self.assertEqual(F.fit(s), s, f)

    def test_the_base_misfits_are_detected(self):
        s = at_base("charts/d/3416230-mobile.svg")
        p = F.problems(s)
        self.assertTrue(any("$228,160" in x for x in p), p)
        self.assertTrue(any("2025-26 and 2026-27 overlap" in x for x in p), p)

    def test_only_labels_change_and_values_stay(self):
        for f in F.files():
            rel = os.path.relpath(f, ROOT).replace(os.sep, "/")
            old, new = at_base(rel), rt(rel)
            self.assertEqual(svg_labels_removed(new), svg_labels_removed(old), rel)
            self.assertEqual([m.group(4) for m in F.VALUE.finditer(new)], [m.group(4) for m in F.VALUE.finditer(old)], rel)
            nt, ot = F.TICK.findall(new), F.TICK.findall(old)
            self.assertTrue(set(nt) <= set(ot), rel)
            if ot:
                self.assertEqual(nt[0], ot[0], rel)
                self.assertEqual(nt[-1], ot[-1], rel)

    def test_desktop_charts_are_unchanged(self):
        out = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", FIX_BASE, "--", "charts"], capture_output=True, check=True, text=True).stdout.split()
        self.assertTrue(out)
        self.assertEqual([p for p in out if not re.fullmatch(r"charts/d/\d{7}-mobile\.svg", p)], [])


class Leftover10ApiIndex(unittest.TestCase):
    def test_index_exists_and_is_fresh(self):
        self.assertEqual(rt("api/v1/nj/index.html"), A.render())

    def test_index_lists_every_json_file_once(self):
        page = rt("api/v1/nj/index.html")
        files = sorted(os.path.basename(f) for f in A.glob.glob(os.path.join(A.API, "*.json")))
        self.assertEqual(len(files), 586)
        self.assertEqual(sorted(re.findall(r'<a href="/api/v1/nj/(\d{7}\.json)">', page)), files)

    def test_district_links_resolve(self):
        for p in re.findall(r'<a href="/nj/([a-z0-9-]+-\d{7})/">', rt("api/v1/nj/index.html")):
            self.assertTrue(os.path.isfile(os.path.join(ROOT, "nj", p, "index.html")), p)

    def test_jsonld_content_url_now_resolves(self):
        self.assertIn('"contentUrl": "/api/v1/nj/"', rt("nj/index.html"))
        self.assertTrue(os.path.isfile(os.path.join(ROOT, "api", "v1", "nj", "index.html")))

    def test_no_existing_file_changes_except_leftover_7(self):
        out = subprocess.run(["git", "-C", ROOT, "diff", "--name-status", FIX_BASE], capture_output=True, check=True, text=True).stdout.splitlines()
        allowed = re.compile(r"(style\.css|charts/d/\d{7}-mobile\.svg|docs/nj-history\.md)")
        modified = [ln.split("\t", 1)[1] for ln in out if ln.startswith("M")]
        self.assertEqual([p for p in modified if not allowed.fullmatch(p)], [])
        self.assertEqual([ln for ln in out if ln[0] not in "MA"], [])

    def test_no_person_fields_in_index(self):
        page = rt("api/v1/nj/index.html").lower()
        for word in ("superintendent_name", "first_name", "last_name", "employee"):
            self.assertNotIn(word, page)


if __name__ == "__main__":
    unittest.main()
