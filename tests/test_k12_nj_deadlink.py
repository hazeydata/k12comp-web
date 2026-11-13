"""K12-NJ-DEADLINK-001: the dead Edison Twp contract link (a short-link redirecting to a 404) must not reappear;
the district's current copy of the same document replaces it, and the extracted copy's sha256 is unchanged."""
import json
import os
import subprocess
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Built from parts so this file does not match its own scan.
DEAD = ("5il" + ".co/2u0cp", "eteacertifiedcontract" + "july2023june2028", "aptg" + ".co/D_3Yg2")
NEW_URL = ("https://files-backend.assets.thrillshare.com/documents/asset/uploaded_file/4500/Eps/"
           "7025b86b-a5ce-4996-9ba2-429cad8337e7/ETEA-Certified-Contract-July-2023-June-2028.pdf")
SHA = "0bec03d36d3e2685dd69653d43b2105c2e1aa26630750f485236176a787d8d07"
EXTS = (".html", ".json", ".md", ".js", ".css", ".xml", ".txt", ".csv", ".py")


def tracked():
    out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, check=True, capture_output=True).stdout
    return [f for f in out.decode().split("\0") if f.endswith(EXTS)]


class DeadLink(unittest.TestCase):
    def test_no_dead_strings_in_tracked_files(self):
        me = os.path.relpath(os.path.abspath(__file__), ROOT)
        bad = []
        for f in tracked():
            if f == me or not os.path.exists(os.path.join(ROOT, f)):
                continue
            with open(os.path.join(ROOT, f), encoding="utf-8", errors="replace") as fh:
                t = fh.read().lower()
            bad += [f"{f}: {d}" for d in DEAD if d.lower() in t]
        self.assertEqual(bad, [])

    def test_api_urls_and_sha(self):
        with open(os.path.join(ROOT, "api", "v1", "nj", "3404500.json"), encoding="utf-8") as fh:
            d = json.load(fh)
        cells = d["salary_cells"]
        self.assertTrue(cells)
        for c in cells:
            self.assertEqual(c["source_url"], NEW_URL)
            self.assertEqual(c["sha256"], SHA)
        self.assertTrue(d["contract_terms"])
        for ct in d["contract_terms"]:
            self.assertEqual(ct["source_url"], NEW_URL)
            self.assertEqual(ct["sha256"], SHA)
        srcs = [s for s in d["sources"] if s.get("sha256") == SHA]
        self.assertTrue(srcs)
        for s in srcs:
            self.assertEqual(s["url"], NEW_URL)

    def test_district_page(self):
        with open(os.path.join(ROOT, "nj", "edison-twp-3404500", "index.html"), encoding="utf-8") as fh:
            t = fh.read()
        self.assertIn(NEW_URL, t)
        self.assertIn('id="src-0bec03d36d3e"', t)
        for dd in DEAD:
            self.assertNotIn(dd.lower(), t.lower())


if __name__ == "__main__":
    unittest.main()
