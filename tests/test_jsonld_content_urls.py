"""Every JSON-LD contentUrl that says application/json (or text/csv) must be that, on disk, as GitHub Pages would serve it.

K12-SITE-NJ-HISTORY-001 leftover 10. The first fix put an HTML index at /api/v1/nj/ while the /nj/ Dataset still called that URL
application/json; a test that only asked "does something exist there" passed. These tests read the target and parse it, for every
JSON-LD block of every published page, and prove the checker rejects the bad shapes. No data repo and no network are needed; any
attempt to open a socket fails the test.
"""
import contextlib
import io
import json
import os
import shutil
import socket
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import jsonld_content_urls as J  # noqa: E402
import nj_api_index as A  # noqa: E402

HOST = "example.test"


def cli(site):
    """(exit code, printed text) of the command-line check."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        rc = J.main(["--site", site])
    return rc, out.getvalue()


def _no_network(*_a, **_k):
    raise AssertionError("the JSON-LD check tried to open a network socket")


class NoNetwork(unittest.TestCase):
    def setUp(self):
        for name in ("socket", "create_connection", "getaddrinfo"):
            p = mock.patch.object(socket, name, _no_network)
            p.start()
            self.addCleanup(p.stop)


class CommittedTree(NoNetwork):
    @classmethod
    def setUpClass(cls):
        cls.checked, cls.problems, cls.blocks = J.check(ROOT)

    def test_no_problem_anywhere(self):
        self.assertEqual(self.problems, [])

    def test_every_jsonld_block_of_every_page_is_walked(self):
        pages = J.html_pages(ROOT, J.jekyll_excludes(ROOT))
        self.assertEqual(len(pages), 594)
        n = 0
        for rel in pages:
            with open(os.path.join(ROOT, *rel.split("/")), encoding="utf-8") as f:
                n += f.read().count("application/ld+json")
        self.assertEqual((n, self.blocks), (1173, 1173))

    def test_the_one_json_claim_is_the_nj_dataset_and_its_target_is_json(self):
        js = [c for c in self.checked if c[2] == "application/json"]
        self.assertEqual(js, [("nj/index.html", "/api/v1/nj/index.json", "application/json", "api/v1/nj/index.json")])
        with open(os.path.join(ROOT, "api", "v1", "nj", "index.json"), "rb") as f:  # read again here, not through the tool
            doc = json.loads(f.read().decode("utf-8"))
        self.assertIsInstance(doc, dict)
        self.assertEqual(doc["count"], 586)

    def test_no_json_claim_is_missed_by_the_walker(self):
        """A plain text count of application/json encodingFormats over all pages equals what the walker checked."""
        n = 0
        for rel in J.html_pages(ROOT, J.jekyll_excludes(ROOT)):
            with open(os.path.join(ROOT, *rel.split("/")), encoding="utf-8") as f:
                n += f.read().count('"encodingFormat": "application/json"')
        self.assertEqual(n, 1)
        self.assertEqual(sum(c[2] == "application/json" for c in self.checked), n)

    def test_csv_claims_are_checked_too(self):
        cs = [c for c in self.checked if c[2] == "text/csv"]
        self.assertEqual(len(cs), 586)  # 585 district history files and the statewide file
        self.assertTrue(all(c[1].startswith("https://k12comp.com/data/nj/") and c[3].startswith("data/nj/") for c in cs))

    def test_html_index_is_not_called_json_by_any_page(self):
        for page, url, fmt, rel in self.checked:
            self.assertFalse(rel.endswith(".html"), (page, url))
        with open(os.path.join(ROOT, "api", "v1", "nj", "index.html"), encoding="utf-8") as f:
            page = f.read()
        self.assertNotIn("application/ld+json", page)
        self.assertNotIn("application/json", page)

    def test_cli_passes_on_the_committed_tree(self):
        rc, out = cli(ROOT)
        self.assertEqual(rc, 0)
        self.assertIn("1 application/json, 586 text/csv; 0 problems", out)


class Fixture(NoNetwork):
    """A tiny site in a temp dir: /nj/index.html carries one Dataset block; each test points its contentUrl somewhere."""

    def setUp(self):
        super().setUp()
        self.tmp = tempfile.mkdtemp(prefix="k12-jsonld-test-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.site = os.path.join(self.tmp, "site")
        self.put("CNAME", HOST + "\n")
        self.put("_config.yml", "exclude:\n  - docs\n  - tests\n  - tools\n")
        self.put("api/v1/nj/3400004.json", '{"district": "A", "nces_leaid": "3400004"}\n')
        self.put("api/v1/nj/index.json", '{"count": 1, "files": [{"url": "/api/v1/nj/3400004.json"}]}\n')
        self.put("api/v1/nj/index.html", "<!doctype html><html><body><a href=\"/api/v1/nj/3400004.json\">3400004.json</a></body></html>\n")

    def put(self, rel, text, base=None):
        p = os.path.join(base or self.site, *rel.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(text if isinstance(text, bytes) else text.encode("utf-8"))

    def page(self, url, fmt="application/json", rel="nj/index.html", wrap=None):
        dist = {"@type": "DataDownload", "contentUrl": url, "encodingFormat": fmt}
        doc = wrap(dist) if wrap else {"@context": "https://schema.org", "@type": "Dataset", "name": "x", "distribution": dist}
        self.put(rel, f'<!doctype html><html><head><script type="application/ld+json">{json.dumps(doc)}</script></head><body></body></html>')

    def run_check(self):
        return J.check(self.site)

    def assertGood(self, want_rel):
        checked, problems, _ = self.run_check()
        self.assertEqual(problems, [])
        self.assertEqual([c[3] for c in checked], [want_rel])

    def assertBad(self, needle):
        checked, problems, _ = self.run_check()
        self.assertEqual(checked, [])
        self.assertEqual(len(problems), 1, problems)
        self.assertIn(needle, problems[0])
        rc, out = cli(self.site)
        self.assertEqual(rc, 1)
        self.assertIn("PROBLEM", out)


class GoodTargets(Fixture):
    def test_root_relative(self):
        self.page("/api/v1/nj/index.json")
        self.assertGood("api/v1/nj/index.json")

    def test_absolute_url_on_the_cname_host_is_read_from_disk(self):
        for u in (f"https://{HOST}/api/v1/nj/index.json", f"http://www.{HOST}/api/v1/nj/index.json", f"https://{HOST.upper()}:443/api/v1/nj/index.json"):
            self.page(u)
            self.assertGood("api/v1/nj/index.json")

    def test_page_relative(self):
        self.page("../api/v1/nj/index.json")
        self.assertGood("api/v1/nj/index.json")
        self.page("3400004.json", rel="api/v1/nj/list/index.html")
        os.remove(os.path.join(self.site, "nj", "index.html"))
        self.put("api/v1/nj/list/3400004.json", "[]")
        self.assertGood("api/v1/nj/list/3400004.json")

    def test_query_fragment_and_percent_encoding(self):
        self.put("api/v1/nj/my file.json", "[1, 2]")
        self.page("/api/v1/nj/my%20file.json?v=2#top")
        self.assertGood("api/v1/nj/my file.json")

    def test_format_with_parameters_and_case(self):
        self.page("/api/v1/nj/index.json", fmt="Application/JSON; charset=utf-8")
        self.assertGood("api/v1/nj/index.json")

    def test_nested_graph_and_distribution_list(self):
        self.page("/api/v1/nj/index.json", wrap=lambda d: {"@context": "https://schema.org", "@graph": [
            {"@type": "WebPage"}, {"@type": "Dataset", "distribution": [{"@type": "DataDownload", "contentUrl": "/x.pdf", "encodingFormat": "application/pdf"}, d]}]})
        self.assertGood("api/v1/nj/index.json")

    def test_unchecked_formats_are_left_alone(self):
        self.page("/nowhere.pdf", fmt="application/pdf")
        self.assertEqual(self.run_check()[:2], ([], []))

    def test_csv_target(self):
        self.put("data/a.csv", "a,b\n1,2\n")
        self.page(f"https://{HOST}/data/a.csv", fmt="text/csv")
        self.assertGood("data/a.csv")


class BadTargets(Fixture):
    def test_the_first_fix_is_rejected_directory_url_with_an_html_index(self):
        self.page("/api/v1/nj/")  # exists, returns 200, and is HTML: the independent FAIL
        self.assertBad("directory URL")

    def test_directory_url_without_trailing_slash(self):
        self.page("/api/v1/nj")
        self.assertBad("directory URL")

    def test_missing_target(self):
        self.page("/api/v1/nj/nope.json")
        self.assertBad("no such file")

    def test_html_file_named_as_json_target(self):
        self.page("/api/v1/nj/index.html")
        self.assertBad("is not a .json file")

    def test_valid_json_under_an_html_name_is_still_not_served_as_json(self):
        self.put("api/v1/nj/data.html", '{"ok": true}')
        self.page("/api/v1/nj/data.html")
        self.assertBad("is not a .json file")

    def test_json_name_with_html_content(self):
        self.put("api/v1/nj/index.json", "<!doctype html><html><body>not json</body></html>")
        self.page("/api/v1/nj/index.json")
        self.assertBad("is not valid application/json")

    def test_truncated_json(self):
        self.put("api/v1/nj/index.json", '{"count": 1, "files": [')
        self.page("/api/v1/nj/index.json")
        self.assertBad("is not valid application/json")

    def test_empty_file(self):
        self.put("api/v1/nj/index.json", "")
        self.page("/api/v1/nj/index.json")
        self.assertBad("is not valid application/json")

    def test_nan_is_not_json(self):
        self.put("api/v1/nj/index.json", '{"count": NaN}')
        self.page("/api/v1/nj/index.json")
        self.assertBad("is not valid application/json")

    def test_not_utf8(self):
        self.put("api/v1/nj/index.json", b'{"district": "\xff\xfe"}')
        self.page("/api/v1/nj/index.json")
        self.assertBad("is not valid application/json")

    def test_other_host_is_not_fetched_and_not_accepted(self):
        self.page("https://example.org/api/v1/nj/index.json")
        self.assertBad("another host")

    def test_non_web_scheme(self):
        self.page("file:///etc/hostname.json")
        self.assertBad("not a web URL")

    def test_path_above_the_site_root(self):
        self.put("outside.json", "{}", base=self.tmp)
        for u in ("/../outside.json", "../../outside.json", f"https://{HOST}/a/../../outside.json", "/%2e%2e/outside.json"):
            self.page(u)
            self.assertBad("above the site root")

    def test_unpublished_paths(self):
        for rel in ("tools/x.json", "_data/x.json", ".well-known/x.json"):
            self.put(rel, "{}")
            self.page("/" + rel)
            self.assertBad("not published")

    def test_empty_and_non_string_content_url(self):
        for u in ("", 7, None):
            self.page(u)
            self.assertBad("not a non-empty string")

    def test_one_bad_url_in_a_list_is_reported(self):
        self.page(["/api/v1/nj/index.json", "/api/v1/nj/"])
        checked, problems, _ = self.run_check()
        self.assertEqual(([c[3] for c in checked], len(problems)), (["api/v1/nj/index.json"], 1))

    def test_unparseable_jsonld_block(self):
        self.put("nj/index.html", '<html><head><script type="application/ld+json">{"distribution": </script></head></html>')
        self.assertBad("does not parse")

    def test_csv_claim_with_missing_or_wrong_target(self):
        self.page("/data/none.csv", fmt="text/csv")
        self.assertBad("no such file")
        self.page("/api/v1/nj/index.json", fmt="text/csv")
        self.assertBad("is not a .csv file")

    def test_unpublished_pages_are_not_walked_but_published_ones_are(self):
        self.page("/api/v1/nj/nope.json", rel="tests/fixture.html")
        self.assertEqual(self.run_check()[:2], ([], []))
        self.page("/api/v1/nj/nope.json", rel="about/index.html")
        self.assertBad("no such file")


class RealPageRegression(Fixture):
    """The committed /nj/ page and API index files, copied into a temp site; then the old contentUrl is put back."""

    def setUp(self):
        super().setUp()
        for rel in ("nj/index.html", "api/v1/nj/index.html", "api/v1/nj/index.json", "CNAME", "_config.yml"):
            with open(os.path.join(ROOT, *rel.split("/")), "rb") as f:
                self.put(rel, f.read())

    def test_committed_page_passes(self):
        self.assertGood("api/v1/nj/index.json")

    def test_old_content_url_fails_even_though_the_html_index_exists(self):
        p = os.path.join(self.site, "nj", "index.html")
        with open(p, "rb") as f:
            page = f.read()
        self.assertEqual(page.count(A.JSONLD_NEW.encode()), 1)
        self.put("nj/index.html", page.replace(A.JSONLD_NEW.encode(), A.JSONLD_OLD.encode(), 1))
        self.assertTrue(os.path.isfile(os.path.join(self.site, "api", "v1", "nj", "index.html")))
        self.assertBad("directory URL")

    def test_index_json_replaced_by_the_html_index_fails(self):
        shutil.copyfile(os.path.join(self.site, "api", "v1", "nj", "index.html"), os.path.join(self.site, "api", "v1", "nj", "index.json"))
        self.assertBad("is not valid application/json")

    def test_index_json_removed_fails(self):
        os.remove(os.path.join(self.site, "api", "v1", "nj", "index.json"))
        self.assertBad("no such file")


if __name__ == "__main__":
    unittest.main()
