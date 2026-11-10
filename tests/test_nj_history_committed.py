"""The committed (in-place) NJ history build: _config.yml excludes, byte-identity with a fresh build, and the tracked statewide CSV."""
import glob
import os
import subprocess
import unittest

import nj_history_helpers as H

STATEWIDE = "data/nj/nj-district-staff-history.csv"


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
            if not os.path.isfile(p) or H.rb(p) != H.rb(os.path.join(out, *r.split("/"))):
                bad.append(r)
        self.assertEqual(bad, [])

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
