"""PR #5 fix list, fix 1 (K12-SITE-NJ-HISTORY-001): native sr-only guide-table caption at every width, swipe cue, sticky Step column,
source line wrapping. Static checks of the committed tree against web main a41b5838; no data repo needed.
The real-browser checks (336/390/1280 px, initial and scrolled right) are in tests/test_nj_guide_tables_browser.py."""
import contextlib
import io
import os
import re
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import nj_guide_tables as G  # noqa: E402

FIX_BASE = "a41b583835f15b30bb5a398c94beaa1e22e8297d"  # web main; the 8 guide pages are unchanged from it up to 52421ace
APPROVED_CUE = "Swipe to see more columns →"  # Lindsay-approved copy (writing/scroll-cue.txt); the one place to update with SCROLL_CUE
OLD_PLACEHOLDER = "Scroll for more columns"
GUIDE_PAGES = ["nj/bayonne-city-3401260/index.html", "nj/cherry-hill-twp-3403000/index.html", "nj/clifton-city-3403300/index.html",
               "nj/edison-twp-3404500/index.html", "nj/toms-river-regional-3416230/index.html",
               "nj/trenton-public-school-district-3416290/index.html", "nj/vineland-city-3416800/index.html",
               "nj/w-windsor-plainsboro-reg-3417700/index.html"]
TABLES = {"nj/bayonne-city-3401260/index.html": 12, "nj/cherry-hill-twp-3403000/index.html": 2, "nj/clifton-city-3403300/index.html": 4,
          "nj/edison-twp-3404500/index.html": 5, "nj/toms-river-regional-3416230/index.html": 6,
          "nj/trenton-public-school-district-3416290/index.html": 3, "nj/vineland-city-3416800/index.html": 4,
          "nj/w-windsor-plainsboro-reg-3417700/index.html": 4}


def rt(rel):
    with open(os.path.join(ROOT, *rel.split("/")), encoding="utf-8", newline="") as f:
        return f.read()


def at_base(rel):
    return subprocess.run(["git", "-C", ROOT, "show", f"{FIX_BASE}:{rel}"], capture_output=True, check=True).stdout.decode()


def by_hand_undo(page):
    """Written here, not through the tool: the committed page with fix 1's markup taken back out."""
    page = re.sub(r'<p class="guide-cue" aria-hidden="true">[^<>]*</p>', "", page)
    return re.sub(r'<table aria-labelledby="guide-cap-\d+"><caption class="sr-only" id="guide-cap-\d+">',
                  "<table><caption>", page)


def sections(page):
    return re.findall(r'<section class="grid [a-z]+">(.*?)</section>', page, re.S)


class CueCopy(unittest.TestCase):
    def test_cue_is_the_approved_wording(self):
        self.assertEqual(G.SCROLL_CUE, APPROVED_CUE)

    def test_old_placeholder_is_nowhere_in_the_tree(self):
        out = subprocess.run(["git", "-C", ROOT, "grep", "-l", "-I", OLD_PLACEHOLDER, "--", ".", ":!tests/test_nj_guide_tables.py"],
                             capture_output=True, text=True)
        self.assertEqual(out.stdout, "")

    def test_every_cue_on_the_site_uses_the_constant(self):
        n = 0
        for rel in GUIDE_PAGES:
            cues = re.findall(r'<p class="guide-cue" aria-hidden="true">([^<>]*)</p>', rt(rel))
            self.assertEqual(set(cues) - {G.SCROLL_CUE}, set(), rel)
            n += len(cues)
        self.assertEqual(n, 23)  # the 23 tables with 3+ header cells; Bayonne (12) and Edison (5) are Step + one column


class Markup(unittest.TestCase):
    def test_the_eight_guide_pages_and_forty_tables(self):
        self.assertEqual([os.path.relpath(p, ROOT).replace(os.sep, "/") for p in G.guide_pages()], GUIDE_PAGES)
        for rel, n in TABLES.items():
            self.assertEqual(len(sections(rt(rel))), n, rel)

    def test_tool_check_passes_and_write_is_idempotent(self):
        with contextlib.redirect_stdout(io.StringIO()) as buf:
            self.assertEqual(G.main(["--check"]), 0)
        self.assertIn("8 guide pages, 40 guide tables, 0 stale", buf.getvalue())
        for rel in GUIDE_PAGES:
            self.assertEqual(G.rewrite(rt(rel)), rt(rel), rel)

    def test_the_only_change_from_web_main_is_fix_1_markup(self):
        for rel in GUIDE_PAGES:
            base, now = at_base(rel), rt(rel)
            self.assertNotEqual(base, now, rel)
            self.assertEqual(by_hand_undo(now), base, rel)
            self.assertEqual(G.rewrite(base), now, rel)

    def test_previous_visible_caption_publication_migrates_without_copy_changes(self):
        for rel in GUIDE_PAGES:
            previous = subprocess.run(["git", "-C", ROOT, "show", f"16f00528:{rel}"], capture_output=True, check=True).stdout.decode()
            self.assertEqual(G.rewrite(previous), rt(rel), rel)

    def test_native_sr_only_caption_text_unchanged_and_named_table(self):
        for rel in GUIDE_PAGES:
            base_caps = re.findall(r"<caption>([^<>]*)</caption>", at_base(rel))
            page = rt(rel)
            self.assertNotIn('class="guide-caption"', page, rel)
            caps = []
            for i, body in enumerate(sections(page), 1):
                h3 = re.search(r"<h3>([^<>]*)</h3>", body).group(1)
                m = re.search(rf'<div class="table-wrap" tabindex="0" role="region" aria-label="([^"]*)"><table aria-labelledby="guide-cap-{i}">'
                              rf'<caption class="sr-only" id="guide-cap-{i}">([^<>]*)</caption>', body)
                self.assertIsNotNone(m, (rel, i))
                self.assertEqual(m.group(1), m.group(2))
                self.assertEqual(m.group(1), h3)
                self.assertLess(body.index('class="table-wrap"'), body.index('<caption class="sr-only"'))
                caps.append(m.group(1))
            self.assertEqual(caps, base_caps, rel)
            ids = re.findall(r'id="(guide-cap-\d+)"', page)
            self.assertEqual(len(ids), len(set(ids)), rel)

    def test_cue_only_on_tables_with_more_than_one_lane(self):
        for rel in GUIDE_PAGES:
            for body in sections(rt(rel)):
                cols = len(re.findall(r'<th scope="col"', body))
                self.assertEqual('class="guide-cue"' in body, cols >= 3, (rel, cols))
                if cols >= 3:
                    self.assertLess(body.index('class="guide-cue"'), body.index('class="table-wrap"'))

    def test_every_cell_is_unchanged(self):
        for rel in GUIDE_PAGES:
            cells = lambda p: re.findall(r"<t[hd][^>]*>([^<]*)</t[hd]>", p)
            self.assertEqual(cells(rt(rel)), cells(at_base(rel)), rel)

    def test_tool_refuses_unexpected_markup(self):
        page = rt(GUIDE_PAGES[0])
        for bad in (page.replace('<table aria-labelledby="guide-cap-1">', "<table>", 1),
                    page.replace('id="guide-cap-1">Teacher', 'id="guide-cap-1">Other', 1)):
            with self.assertRaises((ValueError, AttributeError)):
                G.rewrite(bad)

    def test_a_new_cue_wording_replaces_the_old_one(self):
        page = rt(GUIDE_PAGES[1])
        old = G.SCROLL_CUE
        try:
            G.SCROLL_CUE = "Other words"
            new = G.rewrite(page)
        finally:
            G.SCROLL_CUE = old
        self.assertNotIn(old, new)
        self.assertEqual(new.count("Other words"), page.count(old))
        self.assertEqual(G.rewrite(new), page)


class Css(unittest.TestCase):
    def test_fix_1_rules(self):
        css = rt("style.css")
        self.assertIn(".grid caption.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}.guide-cue{display:none}", css)
        mobile = re.search(r"@media \(max-width:640px\)\{\.guide-cue\{display:block;[^\n]*", css).group(0)
        for rule in (".grid tr>th:first-child{position:sticky;left:0;", ".grid .src-short{text-wrap:balance}",
                     "main .grid .src-short a{display:inline;padding:12px 0}"):
            self.assertIn(rule, mobile)

    def test_style_css_only_gains_lines(self):
        old, new = at_base("style.css").splitlines(), rt("style.css").splitlines()
        self.assertEqual([ln for ln in old if ln not in new], [])
        added = [ln for ln in new if ln not in old]
        self.assertEqual(len(added), 4, added)  # leftover 7a, fix 1 (all widths, mobile), then the /api/v1/nj/ rule
        self.assertEqual(new[-3:], added[1:])
        self.assertTrue(all("PR #5 fix 1" in ln for ln in added[1:3]), added[1:3])


if __name__ == "__main__":
    unittest.main()
