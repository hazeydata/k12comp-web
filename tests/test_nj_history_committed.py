"""The committed (in-place) NJ history build: _config.yml excludes, byte-identity with a fresh build, and the tracked statewide CSV.

One committed file may differ from the fresh build, by one exact substitution: /nj/index.html's Dataset contentUrl (leftover 10,
tools/nj_api_index.py). SCOPED_EDITS names it. The 8 district pages with salary-guide tables (GUIDE_PAGES) may differ by PR #5 fix 1's
guide-table markup only (tools/nj_guide_tables.py: native sr-only caption, swipe cue). K12-FTE-PRESENTATION-001 allows one further rewrite,
`expected_final`: the 44 part-time districts' pages, /nj/, /about/ and llms.txt must equal tools/nj_fte_marks.py's rewrite of the build output
(the part-time badges, notes and caption suffixes; tests/test_k12_fte_presentation.py pins every string). K12-INDEXING-001 runs last:
`expected_final` then applies tools/nj_indexing.py's rewrite to the files it owns (every district page, /nj/, sitemap.xml; tests/test_k12_indexing.py
pins the markup), and the 21 county hubs and / must equal the tool's output. Every other committed file must equal the build byte for byte.
"""
import glob
import os
import re
import subprocess
import unittest

import nj_history_helpers as H
import nj_api_index as A  # tools/ is on sys.path through the helpers
import nj_guide_tables as G
import nj_fte_marks as N
import nj_indexing as I
import k12_indexing_helpers as X

STATEWIDE = "data/nj/nj-district-staff-history.csv"
# {committed file: (bytes in the fresh build, bytes in the committed file)}; each must occur exactly once in the build output.
SCOPED_EDITS = {"nj/index.html": (A.JSONLD_OLD.encode(), A.JSONLD_NEW.encode())}
# PR #5 fix 1: on exactly these pages the committed file is G.rewrite(build output), which must change it
GUIDE_PAGES = ("nj/bayonne-city-3401260/index.html", "nj/cherry-hill-twp-3403000/index.html", "nj/clifton-city-3403300/index.html",
               "nj/edison-twp-3404500/index.html", "nj/toms-river-regional-3416230/index.html",
               "nj/trenton-public-school-district-3416290/index.html", "nj/vineland-city-3416800/index.html",
               "nj/w-windsor-plainsboro-reg-3417700/index.html")


def expected_committed(rel, built):
    """What the committed file must be, given the fresh build's bytes: identical, the one scoped substitution, or fix 1's guide markup."""
    if rel in GUIDE_PAGES:
        want = G.rewrite(built.decode("utf-8")).encode("utf-8")
        if want == built:
            raise AssertionError(f"{rel}: the fresh build has no guide table to rewrite; the allowance no longer applies")
        return want
    if rel not in SCOPED_EDITS:
        return built
    old, new = SCOPED_EDITS[rel]
    if built.count(old) != 1 or built.count(new) != 0:
        raise AssertionError(f"{rel}: the fresh build does not hold the scoped text exactly once; the allowance no longer applies")
    return built.replace(old, new, 1)


def expected_final(rel, built):
    """What the committed file must be: `expected_fte`, then K12-INDEXING-001's rewrite (`expected_indexing`) on exactly the files it owns."""
    return expected_indexing(rel, expected_fte(rel, built))


_indexing = {}


def indexing_model():
    """tools/nj_indexing.py's model of the final tree: the /nj/ rows of the expected /nj/ page, the titles of the fresh build's pages."""
    if "model" not in _indexing:
        out, _ = H.built()
        nj = expected_fte("nj/index.html", H.rb(os.path.join(out, "nj", "index.html"))).decode("utf-8")
        _indexing["model"] = I.model_from_tree(out, nj_page=nj)
    return _indexing["model"]


def expected_indexing(rel, want):
    """K12-INDEXING-001 (runs last): every district page, /nj/ and sitemap.xml are tools/nj_indexing.py's rewrite of the earlier result. The
    sitemap's page set is read from the committed tree, whose pages this module checks one by one (build pages here, hubs and / below)."""
    text = lambda b: b.decode("utf-8")  # noqa: E731
    if rel == "nj/index.html":
        return I.rewrite_nj(text(want), indexing_model()).encode("utf-8")
    if rel == "sitemap.xml":
        pages = {r: I.read(os.path.join(H.ROOT, *r.split("/"))) for r in I.html_files(H.ROOT)}
        return I.render_sitemap(text(want), pages).encode("utf-8")
    m = re.fullmatch(r"nj/[a-z0-9-]+-(\d{7})/index\.html", rel)
    if m:
        return I.rewrite_district(text(want), indexing_model(), m.group(1)).encode("utf-8")
    return want


def expected_fte(rel, built):
    """`expected_committed`, then K12-FTE-PRESENTATION-001's rewrite on exactly the files it owns (district pages
    of the districts with a part-time dot, /nj/, /about/, llms.txt). Any other file: unchanged."""
    want = expected_committed(rel, built)
    text = lambda b: b.decode("utf-8")  # noqa: E731
    if rel == "nj/index.html":
        return N.rewrite_nj(text(want), N.rows_of).encode("utf-8")
    if rel == "about/index.html":
        return N.rewrite_about(text(want)).encode("utf-8")
    if rel == "llms.txt":
        return N.rewrite_llms(text(want)).encode("utf-8")
    m = re.fullmatch(r"nj/[a-z0-9-]+-(\d{7})/index\.html", rel)
    if m and N.marked_rows(N.rows_of(m.group(1))):
        return N.rewrite_district(text(want), N.rows_of(m.group(1))).encode("utf-8")
    return want


def committed_files(out):
    rels = ["about/index.html", "llms.txt", "sitemap.xml", "nj/index.html", "nj/history/index.html", "history.css", "history.js",
            "data/nj/nj-history-coverage.csv", STATEWIDE]
    rels += [os.path.relpath(p, out).replace(os.sep, "/") for p in glob.glob(os.path.join(out, "nj", "*", "index.html"))]
    rels += [os.path.relpath(p, out).replace(os.sep, "/") for p in glob.glob(os.path.join(out, "data", "nj", "history", "*.csv"))]
    return sorted(set(rels))


class JekyllConfig(unittest.TestCase):
    def excludes(self):
        lines = H.rt(os.path.join(H.ROOT, "_config.yml")).splitlines()
        out, on = [], False
        for ln in lines:
            if ln.startswith("exclude:"):
                on = True
            elif on and ln.strip().startswith("- "):
                out.append(ln.strip()[2:].strip())
            elif on and ln.strip() and not ln.strip().startswith("#"):
                on = False
        return out

    def test_excludes_docs_tests_tools(self):
        ex = self.excludes()
        for d in ("docs", "tests", "tools"):
            self.assertIn(d, ex)

    def test_no_site_path_is_excluded(self):
        ex = [e.rstrip("/") for e in self.excludes()]
        site = ["CNAME", "robots.txt", "api", "charts", "fonts", "index.html", "nj", "data", "history.css", "history.js", "sitemap.xml", "llms.txt"]
        for s in site:
            if os.path.exists(os.path.join(H.ROOT, s)):
                self.assertNotIn(s, ex, s)
        for p in H.base_paths():
            if p.endswith(".html") or p in ("CNAME", "robots.txt"):
                top = p.split("/")[0]
                self.assertNotIn(top, ex, p)
                self.assertNotIn(p, ex, p)


@unittest.skipUnless(H.DATA_REPO, "K12_DATA_REPO is needed for the fresh build")
class CommittedBuild(unittest.TestCase):
    def test_committed_files_match_a_fresh_build(self):
        out, _ = H.built()
        rels = committed_files(out)
        self.assertEqual(sum(r.startswith("data/nj/history/") for r in rels), 585)
        self.assertGreaterEqual(len(rels), 1170)
        bad = []
        for r in rels:
            p = os.path.join(H.ROOT, *r.split("/"))
            if not os.path.isfile(p) or H.rb(p) != expected_final(r, H.rb(os.path.join(out, *r.split("/")))):
                bad.append(r)
        self.assertEqual(bad, [])
        self.assertTrue(set(SCOPED_EDITS) <= set(rels))
        self.assertTrue(set(GUIDE_PAGES) <= set(rels))

    def test_the_guide_allowance_is_fix_1_markup_on_eight_pages_and_nothing_wider(self):
        self.assertEqual(len(GUIDE_PAGES), 8)
        self.assertEqual(sorted(os.path.relpath(p, H.ROOT).replace(os.sep, "/") for p in G.guide_pages()), sorted(GUIDE_PAGES))
        out, _ = H.built()
        # the build pages with guide tables are exactly these 8
        self.assertEqual(sorted(os.path.relpath(p, out).replace(os.sep, "/") for p in G.guide_pages(out)), sorted(GUIDE_PAGES))
        cue = re.compile(r'<p class="guide-cue" aria-hidden="true">[^<>]*</p>')
        cap = re.compile(r'<table aria-labelledby="guide-cap-\d+"><caption class="sr-only" id="guide-cap-\d+">')
        for rel in GUIDE_PAGES:
            built = H.rb(os.path.join(out, *rel.split("/"))).decode("utf-8")
            committed = X.undo(rel, H.rb(os.path.join(H.ROOT, *rel.split("/"))).decode("utf-8"))  # without K12-INDEXING-001's markup (expected_final pins that)
            self.assertNotEqual(committed, built)
            # undone here by hand, not through the tool: taking fix 1's markup out gives the build page back exactly
            self.assertEqual(cap.sub("<table><caption>", cue.sub("", committed)), built, rel)
            self.assertEqual(expected_committed(rel, built.encode()), committed.encode())
            # any other difference on the page is still a failure
            self.assertNotEqual(expected_committed(rel, built.replace("$", "USD ", 1).encode()), committed.encode())
        self.assertEqual(expected_committed("nj/absecon-city-3400660/index.html", b"x"), b"x")  # every other page: byte-identical
        with self.assertRaises(AssertionError):
            expected_committed(GUIDE_PAGES[0], b"<html>no guide</html>")

    def test_the_scoped_edit_is_one_exact_substitution_and_nothing_wider(self):
        self.assertEqual(list(SCOPED_EDITS), ["nj/index.html"])
        self.assertEqual(SCOPED_EDITS["nj/index.html"], (b'"contentUrl": "/api/v1/nj/"', b'"contentUrl": "/api/v1/nj/index.json"'))
        out, _ = H.built()
        built = H.rb(os.path.join(out, "nj", "index.html"))
        committed = N.strip_nj(X.undo("nj/index.html", H.rt(os.path.join(H.ROOT, "nj", "index.html")))).encode("utf-8")  # without the FTE or K12-INDEXING-001 markup (expected_final pins that)
        self.assertNotEqual(committed, built)  # the build still writes the old contentUrl; the committed page carries the edit
        self.assertEqual(len(committed) - len(built), len(b"index.json"))
        # worked out here from literals, not through expected_committed, so a helper that waves the file through cannot pass
        old, new = b'"contentUrl": "/api/v1/nj/"', b'"contentUrl": "/api/v1/nj/index.json"'
        self.assertEqual((built.count(old), built.count(new)), (1, 0))
        want = built.replace(old, new, 1)
        self.assertEqual(committed, want)
        self.assertEqual(expected_committed("nj/index.html", built), want)
        # the helper's answer depends on the build bytes it is given, never on what happens to be committed
        self.assertEqual(expected_committed("nj/index.html", b"<head>" + old + b"</head>"), b"<head>" + new + b"</head>")
        # any other difference on that page, or the same edit on another file, is still a failure
        self.assertNotEqual(committed + b" ", expected_committed("nj/index.html", built))
        self.assertEqual(expected_committed("about/index.html", built), built)
        for drifted in (built.replace(b"/api/v1/nj/", b"/api/v2/nj/"), built + SCOPED_EDITS["nj/index.html"][0],
                        built.replace(SCOPED_EDITS["nj/index.html"][0], SCOPED_EDITS["nj/index.html"][1])):
            with self.assertRaises(AssertionError):
                expected_committed("nj/index.html", drifted)

    def test_indexing_rewrite_is_applied_and_owns_exactly_its_files(self):
        """K12-INDEXING-001: the rewrite changes every district page, /nj/ and the sitemap of the earlier result, and nothing else."""
        out, _ = H.built()
        rels = committed_files(out)
        owned = []
        for r in rels:
            fte = expected_fte(r, H.rb(os.path.join(out, *r.split("/"))))
            if expected_indexing(r, fte) != fte:
                owned.append(r)
        self.assertEqual(len([r for r in owned if re.fullmatch(r"nj/[a-z0-9-]+-\d{7}/index\.html", r)]), 586)
        self.assertEqual(sorted(r for r in owned if not re.fullmatch(r"nj/[a-z0-9-]+-\d{7}/index\.html", r)), ["nj/index.html", "sitemap.xml"])
        # the rewrite is the last step: undoing it gives the earlier result back on every page it owns
        for r in owned:
            if r.endswith(".html"):
                fte = expected_fte(r, H.rb(os.path.join(out, *r.split("/"))))
                self.assertEqual(X.undo(r, H.rb(os.path.join(H.ROOT, *r.split("/")))), fte, r)

    def test_committed_hubs_and_home_are_the_tool_output(self):
        """K12-INDEXING-001: the 21 county hubs (new files) and / (not part of the history build) equal tools/nj_indexing.py's output."""
        model = indexing_model()
        have = sorted(os.path.relpath(p, H.ROOT).replace(os.sep, "/") for p in glob.glob(os.path.join(H.ROOT, "nj", "county", "*", "index.html")))
        self.assertEqual(have, sorted(I.hub_rel(c) for c in model.counties))
        self.assertEqual(len(have), 21)
        for c in model.counties:
            self.assertEqual(H.rb(os.path.join(H.ROOT, *I.hub_rel(c).split("/"))), I.render_hub(model, c).encode("utf-8"), c)
        self.assertEqual(H.rt(os.path.join(H.ROOT, "index.html")), I.rewrite_home(X.at_base("index.html").decode("utf-8"), model))
        self.assertEqual(sorted(os.listdir(os.path.join(H.ROOT, "nj", "county"))), sorted(I.county_slug(c) for c in model.counties))

    def test_no_stale_committed_history_csv(self):
        out, _ = H.built()
        fresh = {r for r in committed_files(out) if r.startswith("data/nj/history/")}
        have = {os.path.relpath(p, H.ROOT).replace(os.sep, "/") for p in glob.glob(os.path.join(H.ROOT, "data", "nj", "history", "*.csv"))}
        self.assertEqual(have, fresh)


class StatewideCsv(unittest.TestCase):
    def test_statewide_csv_is_tracked_not_ignored(self):
        tracked = subprocess.run(["git", "-C", H.ROOT, "ls-files", "-z"], capture_output=True, check=True).stdout.decode().split("\0")
        self.assertIn(STATEWIDE, tracked)
        self.assertNotIn(STATEWIDE, H.rt(os.path.join(H.ROOT, ".gitignore")).splitlines())

    @unittest.skipUnless(H.DATA_REPO, "K12_DATA_REPO is needed for the fresh build")
    def test_statewide_csv_matches_a_fresh_build(self):
        out, _ = H.built()
        self.assertEqual(H.rb(os.path.join(H.ROOT, *STATEWIDE.split("/"))), H.rb(os.path.join(out, *STATEWIDE.split("/"))))


if __name__ == "__main__":
    unittest.main()
