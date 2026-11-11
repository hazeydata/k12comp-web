"""The committed (in-place) NJ history build: _config.yml excludes, byte-identity with a fresh build, and the tracked statewide CSV.

One committed file may differ from the fresh build, by one exact substitution: /nj/index.html's Dataset contentUrl (leftover 10,
tools/nj_api_index.py). SCOPED_EDITS names it; every other committed file must equal the build byte for byte.
"""
import glob
import os
import subprocess
import unittest

import nj_history_helpers as H
import nj_api_index as A  # tools/ is on sys.path through the helpers

STATEWIDE = "data/nj/nj-district-staff-history.csv"
# {committed file: (bytes in the fresh build, bytes in the committed file)}; each must occur exactly once in the build output.
SCOPED_EDITS = {"nj/index.html": (A.JSONLD_OLD.encode(), A.JSONLD_NEW.encode())}


def expected_committed(rel, built):
    """What the committed file must be, given the fresh build's bytes: identical, or the one scoped substitution applied."""
    if rel not in SCOPED_EDITS:
        return built
    old, new = SCOPED_EDITS[rel]
    if built.count(old) != 1 or built.count(new) != 0:
        raise AssertionError(f"{rel}: the fresh build does not hold the scoped text exactly once; the allowance no longer applies")
    return built.replace(old, new, 1)


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
            if not os.path.isfile(p) or H.rb(p) != expected_committed(r, H.rb(os.path.join(out, *r.split("/")))):
                bad.append(r)
        self.assertEqual(bad, [])
        self.assertTrue(set(SCOPED_EDITS) <= set(rels))

    def test_the_scoped_edit_is_one_exact_substitution_and_nothing_wider(self):
        self.assertEqual(list(SCOPED_EDITS), ["nj/index.html"])
        self.assertEqual(SCOPED_EDITS["nj/index.html"], (b'"contentUrl": "/api/v1/nj/"', b'"contentUrl": "/api/v1/nj/index.json"'))
        out, _ = H.built()
        built = H.rb(os.path.join(out, "nj", "index.html"))
        committed = H.rb(os.path.join(H.ROOT, "nj", "index.html"))
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
