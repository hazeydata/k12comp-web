"""Leftovers 7 and 10 of K12-SITE-NJ-HISTORY-001: mobile guide tables and charts fit at 336/390 px; the /nj/ Dataset JSON-LD
points at a real JSON file (/api/v1/nj/index.json) and /api/v1/nj/ has an index page for people.
Static checks against the committed tree, web main a41b5838 (the tree these fixes start from) and history base 3b50ce10.
No data repo is needed. Real-browser widths are builder evidence. tests/test_jsonld_content_urls.py reads every JSON-LD target."""
import contextlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import nj_api_index as A  # noqa: E402
import nj_fte_marks as N  # noqa: E402  (K12-FTE-PRESENTATION-001: the one allowed further edit, see FTE_PAGES)
import nj_mobile_chart_fit as F  # noqa: E402
from chart_header_helpers import content_changes  # noqa: E402
from nj_history import render as R  # noqa: E402

FIX_BASE = "a41b583835f15b30bb5a398c94beaa1e22e8297d"  # web main before these fixes
HISTORY_BASE = "3b50ce10b88e80188e6c8265634b68b482c1a81f"  # the base the history build starts from (AC 23/24)
# Everything these fixes may change since FIX_BASE, by exact path or one exact pattern. Site files first, then unpublished files.
# nj/index.html: only the contentUrl, checked below. The NJ distribution mobile SVG: K12-CHART-MOBILE-TEXT-001 (tests/test_k12_chart_mobile_text.py)
# K12-FTE-PRESENTATION-001 adds: the 44 part-time districts' desktop charts and pages (FTE_CHARTS, FTE_PAGES, from the committed JSON), /about/ and llms.txt.
SITE_MODIFIED = re.compile(r"style\.css|charts/d/\d{7}-mobile\.svg|nj/index\.html|charts/chart3-nj-salary-distribution-mobile\.svg|about/index\.html|llms\.txt")
FTE_LEAIDS = {leaid for _, leaid in N.pages() if N.marked_rows(N.rows_of(leaid))}
FTE_CHARTS = {f"charts/d/{leaid}-desktop.svg" for leaid in FTE_LEAIDS}
FTE_PAGES = {os.path.relpath(p, ROOT).replace(os.sep, "/") for p, leaid in N.pages() if leaid in FTE_LEAIDS}
# PR #5 fix 1 (tools/nj_guide_tables.py): the 8 guide pages, each by exact path; tests/test_nj_guide_tables.py checks their diff
GUIDE_PAGES = {"nj/bayonne-city-3401260/index.html", "nj/cherry-hill-twp-3403000/index.html", "nj/clifton-city-3403300/index.html",
               "nj/edison-twp-3404500/index.html", "nj/toms-river-regional-3416230/index.html",
               "nj/trenton-public-school-district-3416290/index.html", "nj/vineland-city-3416800/index.html",
               "nj/w-windsor-plainsboro-reg-3417700/index.html"}
SITE_ADDED = {"api/v1/nj/index.html", "api/v1/nj/index.json"}
OTHER_MODIFIED = {"docs/nj-history.md", "tests/test_nj_history_committed.py"}
OTHER_ADDED = {"tools/nj_chart_label_edge.py", "tests/chart_header_helpers.py", "tests/test_k12_chart_label_edge.py",  # K12-CHART-LABEL-EDGE-001
               "tests/test_k12_chart_label_edge_browser.py", "tests/test_k12_nj_year_wrap.py",
               "tests/test_jsonld_content_urls.py", "tests/test_nj_leftovers_7_10.py", "tools/jsonld_content_urls.py",
               "tools/nj_api_index.py", "tools/nj_mobile_chart_fit.py",
               "tests/test_nj_guide_tables.py", "tests/test_nj_guide_tables_browser.py", "tools/nj_guide_tables.py",  # PR #5 fix 1
               "tests/test_nj_api_index_browser.py",  # PR #5 fix list, QG nit (/api/v1/nj/ file names)
               "tests/test_k12_chart_mobile_text.py",  # K12-CHART-MOBILE-TEXT-001
               "tools/nj_fte_marks.py", "tests/test_k12_fte_presentation.py",  # K12-FTE-PRESENTATION-001
               "tests/test_k12_nj_county_wrap.py"}  # K12-NJ-COUNTY-WRAP-001


def rt(rel):
    with open(os.path.join(ROOT, *rel.split("/")), encoding="utf-8", newline="") as f:
        return f.read()


def rb(rel):
    with open(os.path.join(ROOT, *rel.split("/")), "rb") as f:
        return f.read()


def show(commit, rel):
    return subprocess.run(["git", "-C", ROOT, "show", f"{commit}:{rel}"], capture_output=True, check=True).stdout


def at_base(rel):
    return show(FIX_BASE, rel).decode()


def district_files():
    return sorted(n for n in os.listdir(A.API) if re.fullmatch(r"\d{7}\.json", n))


def quiet_main(argv):
    with contextlib.redirect_stdout(io.StringIO()):
        return A.main(argv)


class Leftover7aGuideTables(unittest.TestCase):
    def test_guide_cells_do_not_wrap_on_mobile(self):
        css = rt("style.css")
        m = re.search(r"@media \(max-width:640px\)\{\.grid th,\.grid td\.num\{white-space:nowrap\}\}", css)
        self.assertIsNotNone(m)

    def test_only_that_line_is_added_to_style_css(self):
        old, new = at_base("style.css").splitlines(), rt("style.css").splitlines()
        added = [ln for ln in new if ln not in old and "K12-FTE-PRESENTATION-001" not in ln
                 and ln not in ("#districts td:nth-of-type(3){white-space:nowrap}", "#districts td:nth-of-type(1){white-space:nowrap}")]  # K12-FTE-PRESENTATION-001: its two lines are pinned in test_k12_fte_presentation.py; K12-CHART-LABEL-EDGE-001: the Year rule in test_k12_nj_year_wrap.py; K12-NJ-COUNTY-WRAP-001: the County rule in test_k12_nj_county_wrap.py
        self.assertEqual([ln for ln in old if ln not in new], [])
        self.assertEqual(len(added), 4, added)  # this line, then the PR #5 fix list's three (tests/test_nj_guide_tables.py, test_nj_api_index_browser.py)
        self.assertIn(".grid td.num", added[0])
        self.assertTrue(all("PR #5 fix" in ln for ln in added[1:]), added[1:])

    def test_guide_tables_scroll_inside_their_region(self):
        css = rt("style.css")
        self.assertIn("@media (max-width:640px){.grid .table-wrap{overflow:auto;", css)


class Leftover7bMobileCharts(unittest.TestCase):
    """K12-CHART-MOBILE-TEXT-001 turned the leftover 7b fitter into the mobile generator (x redrawn in a 304 viewBox, true year positions,
    one year-label rule); tests/test_k12_chart_mobile_text.py checks that in full. What stays from 7b: every chart fits, values stay."""
    def test_every_mobile_chart_fits(self):
        bad = {f: F.problems(rt(os.path.relpath(f, ROOT).replace(os.sep, "/")), F.read(F.desktop_of(f))) for f in F.files()}
        bad = {k: v for k, v in bad.items() if v}
        self.assertEqual(len(F.files()), 573)
        self.assertEqual(bad, {})

    def test_fit_is_idempotent(self):
        for f in F.files():
            s = rt(os.path.relpath(f, ROOT).replace(os.sep, "/"))
            self.assertEqual(F.fit(s, F.read(F.desktop_of(f))), s, f)

    def test_the_base_misfits_are_detected(self):
        s = at_base("charts/d/3416230-mobile.svg")
        p = F.problems(s)
        self.assertTrue(any("$228,160" in x for x in p), p)
        self.assertTrue(any("2025-26 and 2026-27 overlap" in x for x in p), p)

    def test_values_and_their_heights_stay(self):
        for f in F.files():
            rel = os.path.relpath(f, ROOT).replace(os.sep, "/")
            old, new = at_base(rel), rt(rel)
            self.assertEqual([m.group(4) for m in F.VALUE.finditer(new)], [m.group(4) for m in F.VALUE.finditer(old)], rel)
            self.assertEqual([y for _, y in F.DOT.findall(new)], [y for _, y in F.DOT.findall(old)], rel)

    def test_desktop_charts_are_unchanged(self):
        out = content_changes(FIX_BASE, subprocess.run(["git", "-C", ROOT, "diff", "--name-only", FIX_BASE, "--", "charts"],
                                                       capture_output=True, check=True, text=True).stdout.split())  # K12-CHART-LABEL-EDGE-001: not counting the header
        self.assertTrue(out)
        self.assertEqual([p for p in out if not re.fullmatch(r"charts/d/\d{7}-mobile\.svg|charts/chart3-nj-salary-distribution-mobile\.svg", p)
                          and p not in FTE_CHARTS], [])  # K12-FTE-PRESENTATION-001: exactly the part-time districts' desktop charts
        self.assertEqual({p for p in out if p.endswith("-desktop.svg")}, FTE_CHARTS)


class Leftover10ApiIndex(unittest.TestCase):
    def test_index_files_exist_and_are_fresh(self):
        self.assertEqual(rt("api/v1/nj/index.html"), A.render())
        self.assertEqual(rt("api/v1/nj/index.json"), A.render_json())
        self.assertEqual(quiet_main(["--check"]), 0)

    def test_api_directory_holds_the_586_district_files_and_the_two_indexes_only(self):
        self.assertEqual(len(district_files()), 586)
        self.assertEqual(sorted(os.listdir(A.API)), sorted(district_files() + ["index.html", "index.json"]))

    def test_index_lists_every_json_file_once(self):
        page = rt("api/v1/nj/index.html")
        self.assertEqual(sorted(re.findall(r'<a href="/api/v1/nj/(\d{7}\.json)">', page)), district_files())

    def test_district_links_resolve(self):
        for p in re.findall(r'<a href="/nj/([a-z0-9-]+-\d{7})/">', rt("api/v1/nj/index.html")):
            self.assertTrue(os.path.isfile(os.path.join(ROOT, "nj", p, "index.html")), p)

    def test_index_json_lists_every_file_once_and_agrees_with_each_file(self):
        raw = rt("api/v1/nj/index.json")
        doc = json.loads(raw)
        self.assertEqual(set(doc), {"count", "description", "files", "license", "state"})
        self.assertEqual((doc["count"], doc["state"], doc["license"]), (586, "NJ", "https://creativecommons.org/licenses/by/4.0/"))
        self.assertEqual(len(doc["files"]), 586)
        self.assertEqual([os.path.basename(e["url"]) for e in doc["files"]], district_files())
        for e in doc["files"]:
            self.assertEqual(set(e), {"district", "nces_leaid", "page", "url"})
            self.assertEqual(e["url"], f"/api/v1/nj/{e['nces_leaid']}.json")
            with open(os.path.join(ROOT, *e["url"].strip("/").split("/")), encoding="utf-8") as f:
                d = json.load(f)
            self.assertEqual((e["district"], e["nces_leaid"]), (d["district"], d["nces_leaid"]), e["url"])
            self.assertRegex(e["page"], rf"^/nj/[a-z0-9-]+-{e['nces_leaid']}/$")
            self.assertTrue(os.path.isfile(os.path.join(ROOT, *e["page"].strip("/").split("/"), "index.html")), e["page"])

    def test_index_json_is_written_like_the_district_files(self):
        for rel in ("api/v1/nj/index.json", "api/v1/nj/" + district_files()[0]):
            raw = rt(rel)
            self.assertEqual(raw, json.dumps(json.loads(raw), indent=1, sort_keys=True) + "\n", rel)

    def test_html_and_json_indexes_list_the_same_rows(self):
        rows = re.findall(r'<tr><td><a href="(/api/v1/nj/\d{7}\.json)">[^<]*</a></td><td>(.*?)</td><td><a href="(/nj/[^"]+/)">', rt("api/v1/nj/index.html"))
        doc = json.loads(rt("api/v1/nj/index.json"))
        self.assertEqual([(u, A.html.unescape(n), p) for u, n, p in rows], [(e["url"], e["district"], e["page"]) for e in doc["files"]])
        self.assertIn('<a href="/api/v1/nj/index.json">index.json</a>', rt("api/v1/nj/index.html"))

    def test_nj_dataset_distribution_names_the_json_index(self):
        blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', rt("nj/index.html"), re.S)
        self.assertEqual(len(blocks), 1)
        ds = json.loads(blocks[0])
        self.assertEqual(ds["distribution"], {"@type": "DataDownload", "contentUrl": "/api/v1/nj/index.json", "encodingFormat": "application/json"})
        self.assertIsInstance(json.loads(rt("api/v1/nj/index.json")), dict)  # the target parses as JSON; see also test_jsonld_content_urls.py

    def test_nj_page_differs_from_web_main_by_the_content_url_only(self):
        old = show(FIX_BASE, "nj/index.html")
        self.assertEqual((old.count(A.JSONLD_OLD.encode()), old.count(A.JSONLD_NEW.encode())), (1, 0))
        page = N.strip_nj(rb("nj/index.html").decode()).encode()  # without K12-FTE-PRESENTATION-001's markup (checked in test_k12_fte_presentation.py)
        self.assertEqual(page, old.replace(A.JSONLD_OLD.encode(), A.JSONLD_NEW.encode(), 1))

    def test_ac24_nj_page_differs_from_history_base_by_the_history_link_and_the_content_url_only(self):
        new = N.strip_nj(rb("nj/index.html").decode()).encode()  # without K12-FTE-PRESENTATION-001's markup
        self.assertEqual((new.count(A.JSONLD_NEW.encode()), new.count(R.nj_link().encode())), (1, 1))
        back = new.replace(A.JSONLD_NEW.encode(), A.JSONLD_OLD.encode(), 1).replace(R.nj_link().encode(), b"", 1)
        self.assertEqual(back, show(HISTORY_BASE, "nj/index.html"))

    def test_ac23_every_history_base_path_still_exists_and_the_json_files_are_byte_identical(self):
        paths = subprocess.run(["git", "-C", ROOT, "ls-tree", "-r", "--name-only", HISTORY_BASE], capture_output=True, check=True, text=True).stdout.splitlines()
        self.assertEqual(len(paths), 2350)
        self.assertEqual([p for p in paths if not os.path.isfile(os.path.join(ROOT, *p.split("/")))], [])
        api = [p for p in paths if p.startswith("api/v1/nj/")]
        self.assertEqual([os.path.basename(p) for p in api], district_files())
        changed = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", HISTORY_BASE, "--", *api, "CNAME", "robots.txt"],
                                 capture_output=True, check=True, text=True).stdout.split()
        self.assertEqual(changed, [])

    def test_nj_page_edit_is_scoped_idempotent_and_refuses_anything_else(self):
        old, new = A.JSONLD_OLD.encode(), A.JSONLD_NEW.encode()
        page = b'<head>{"distribution": {' + old + b', "encodingFormat": "application/json"}}</head><p>"/api/v1/nj/"</p>'
        once = A.nj_page(page)
        self.assertEqual(once, page.replace(old, new))
        self.assertEqual(len(once) - len(page), len(b"index.json"))
        self.assertEqual(A.nj_page(once), once)
        for bad in (b"<head></head>", page + old, once + new, page + new):
            with self.assertRaises(SystemExit):
                A.nj_page(bad)

    def test_check_fails_on_a_stale_tree_and_write_repairs_it_without_touching_the_repo(self):
        with tempfile.TemporaryDirectory(prefix="k12-api-index-test-") as tmp:
            paths = {"OUT": os.path.join(tmp, "index.html"), "OUT_JSON": os.path.join(tmp, "index.json"), "NJ_PAGE": os.path.join(tmp, "nj.html")}
            with open(paths["NJ_PAGE"], "wb") as f:
                f.write(show(FIX_BASE, "nj/index.html"))  # still has the old contentUrl
            with mock.patch.multiple(A, **paths):
                self.assertEqual(quiet_main(["--check"]), 1)  # all three missing or stale
                self.assertEqual(quiet_main(["--write"]), 0)
                self.assertEqual(quiet_main(["--check"]), 0)
                for name, rel in (("OUT", "api/v1/nj/index.html"), ("OUT_JSON", "api/v1/nj/index.json"), ("NJ_PAGE", "nj/index.html")):
                    with open(paths[name], "rb") as f:
                        want = N.strip_nj(rb(rel).decode()).encode() if rel == "nj/index.html" else rb(rel)  # the page without the FTE markup
                        self.assertEqual(f.read(), want, rel)
                with open(paths["OUT_JSON"], "w", encoding="utf-8") as f:
                    f.write("<!doctype html>")
                self.assertEqual(quiet_main(["--check"]), 1)

    def test_no_file_changes_since_web_main_except_the_scoped_leftover_7_and_10_edits(self):
        out = subprocess.run(["git", "-C", ROOT, "diff", "--name-status", FIX_BASE], capture_output=True, check=True, text=True).stdout.splitlines()
        self.assertEqual([ln for ln in out if ln[0] not in "MA"], [])  # nothing deleted, renamed or retyped
        modified = set(content_changes(FIX_BASE, [ln.split("\t", 1)[1] for ln in out if ln.startswith("M")]))  # K12-CHART-LABEL-EDGE-001: not counting the header
        added = {ln.split("\t", 1)[1] for ln in out if ln.startswith("A")}
        unpublished = ("docs/", "tests/", "tools/")
        self.assertEqual(sorted(p for p in modified if not p.startswith(unpublished) and not SITE_MODIFIED.fullmatch(p) and p not in GUIDE_PAGES
                                 and p not in FTE_PAGES and p not in FTE_CHARTS), [])
        self.assertEqual({p for p in modified if p.startswith("nj/") and p != "nj/index.html"}, GUIDE_PAGES | FTE_PAGES)
        self.assertEqual({p for p in added if not p.startswith(unpublished)}, SITE_ADDED)
        self.assertEqual({p for p in modified if p.startswith(unpublished)}, OTHER_MODIFIED)
        self.assertEqual({p for p in added if p.startswith(unpublished)}, OTHER_ADDED)

    def test_no_person_fields_in_either_index(self):
        for rel in ("api/v1/nj/index.html", "api/v1/nj/index.json"):
            page = rt(rel).lower()
            for word in ("superintendent_name", "first_name", "last_name", "employee", "salary", "contract"):
                if word in ("salary", "contract") and rel.endswith(".html"):
                    continue  # the page's one sentence says what the files hold
                self.assertNotIn(word, page, (rel, word))


if __name__ == "__main__":
    unittest.main()
