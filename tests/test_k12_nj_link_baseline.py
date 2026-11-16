"""K12-NJ-UPKEEP-001: /nj/ link baseline (tools/nj_link_baseline.py) and the chart3 mobile "districts" label inside the left edge.
No network: the live checker runs against a stub transport and a fake clock; mutation runs use scratch trees in a TemporaryDirectory."""
import contextlib
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
import nj_link_baseline as L  # noqa: E402
import nj_mobile_chart_fit as F  # noqa: E402

BASELINE = os.path.join(ROOT, "docs", "nj-link-baseline.tsv")
DIST = os.path.join(ROOT, "charts", "chart3-nj-salary-distribution-mobile.svg")
PDF = "https://example.org/docs/contract.pdf"
CSV = "https://example.org/data/employees.csv"
WITH_SPACE = "https://example.org/cs/Certificated%20Staff%202021.zip"
QUERY = "https://example.org/DisplayFile.aspx?itemId=1"


def run(argv, **kw):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        rc = L.main(argv, **kw)
    return rc, out.getvalue()


def write(root, rel, text):
    p = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def page(links, local=("/style.css", "../", "/nj/a/")):
    ld = json.dumps({"@context": "https://schema.org", "isBasedOn": [QUERY], "license": "https://creativecommons.org/licenses/by/4.0/"})
    return ("<!doctype html><html><head><link rel=\"stylesheet\" href=\"/style.css\">"
            "<meta property=\"og:url\" content=\"https://k12comp.com/nj/\">"
            "<script async src=\"https://gc.zgo.at/count.js\"></script>"
            f"<script type=\"application/ld+json\">{ld}</script></head><body>"
            + "".join(f'<a href="{u}">x</a>' for u in links) + "".join(f'<a href="{u}">l</a>' for u in local)
            + '<form action="https://hazeydata.ai/api/subscribe"></form><a href="#top">t</a><a href="mailto:a@b.c">m</a></body></html>')


def fixture(root):
    """A small site tree: two /nj/ pages, one api JSON, one data CSV, and a matching baseline."""
    write(root, "index.html", "home")
    write(root, "style.css", "")
    write(root, "nj/index.html", page([PDF, WITH_SPACE + "#p2"]))
    write(root, "nj/a/index.html", page([CSV, PDF], local=("../", "https://k12comp.com/nj/a/", "../../style.css")))
    write(root, "api/v1/nj/1.json", json.dumps({"sources": [{"url": CSV}, {"url": PDF}], "note": f"see {WITH_SPACE}#p2."}))
    write(root, "data/nj/history/1.csv", f"leaid,url,sha\n1,{CSV},abc\n")
    rows = [L.COLUMNS]
    for u in sorted([PDF, CSV, WITH_SPACE + "#p2", QUERY]):
        rows.append((u, "1", "nj/index.html", "200", u.split("#")[0], "application/pdf", "10", "", "", "2026-11-16T00:00:00Z"))
    write(root, "docs/nj-link-baseline.tsv", "".join("\t".join(r) + "\n" for r in rows))


def row(url="https://h.example/f.pdf", ctype="application/pdf", length="100", lm="Mon, 01 Jan 2024 00:00:00 GMT", etag='"e1"'):
    return {"url": url, "pages": "1", "example_page": "nj/index.html", "status": "200", "final_url": url, "content_type": ctype,
            "content_length": length, "last_modified": lm, "etag": etag, "checked_at_utc": "2026-11-16T00:00:00Z"}


def hdrs(ctype="application/pdf", length="100", lm="Mon, 01 Jan 2024 00:00:00 GMT", etag='"e1"', **more):
    h = {"Content-Type": ctype, "Content-Length": length}
    if lm:
        h["Last-Modified"] = lm
    if etag:
        h["ETag"] = etag
    h.update(more)
    return h


class FakeClock:
    """Monotonic time moves only by sleep() and by each stubbed request's duration; the wall clock follows it."""

    def __init__(self):
        self.t = 1000.0

    def monotonic(self):
        return self.t

    def sleep(self, s):
        assert s >= 0
        self.t += s

    def utcnow(self):
        import datetime
        return datetime.datetime(2026, 11, 16, tzinfo=datetime.timezone.utc) + datetime.timedelta(seconds=self.t)


class Stub:
    """(method, url) -> Response or NetError; records every call; each call takes 0.2 s of fake time."""

    def __init__(self, table, clock=None):
        self.table, self.calls, self.clock = table, [], clock

    def request(self, method, url, headers, timeout):
        self.calls.append((method, url, dict(headers), timeout))
        if self.clock:
            self.clock.t += 0.2
        r = self.table.get((method, url))
        if r is None:
            r = self.table.get(("*", url))
        if isinstance(r, L.NetError):
            raise r
        return r


def check(table, url="https://h.example/f.pdf", base="row"):
    """Classify one stubbed URL against `base`: its default baseline row, a given row, or None (no baseline row)."""
    clock = FakeClock()
    stub = Stub(table, clock)
    facts = L.Checker(stub, clock).check(url)
    return L.classify(facts, row(url) if base == "row" else base), facts, stub


# --- offline -----------------------------------------------------------------------------------------------------------------------
class OfflineRepo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rc, cls.out = run(["--offline"])
        cls.scan = L.scan(ROOT)

    def test_offline_passes_on_the_repo_tree(self):
        self.assertEqual(self.rc, 0, self.out)
        self.assertIn("pages scanned: 609\n", self.out)  # K12-INDEXING-001: 588 + the 21 county hubs
        self.assertIn("unique external URLs: 18 ", self.out)
        self.assertIn("unresolved local refs: 0\n", self.out)
        self.assertRegex(self.out, r"local refs: \d+ \(\d+ unique targets\)")
        self.assertTrue(self.out.rstrip().endswith("offline: OK"))

    def test_default_mode_is_offline(self):
        rc, out = run([])
        self.assertEqual((rc, out), (self.rc, self.out))

    def test_the_baseline_has_one_row_per_url_all_2xx(self):
        with open(BASELINE, encoding="utf-8", newline="") as fh:
            lines = fh.read().split("\n")
        self.assertEqual(lines[-1], "")
        self.assertEqual(tuple(lines[0].split("\t")), L.COLUMNS)
        rows = [dict(zip(L.COLUMNS, ln.split("\t"))) for ln in lines[1:-1]]
        urls = [r["url"] for r in rows]
        self.assertEqual(urls, sorted(set(urls)))  # one row per URL, sorted by url
        self.assertEqual(set(urls), set(self.scan["urls"]))
        self.assertEqual(len(rows), 18)
        for r in rows:
            self.assertRegex(r["status"], r"^2\d\d$", r["url"])
            for k in ("url", "pages", "example_page", "final_url", "content_type", "content_length", "checked_at_utc"):
                self.assertTrue(r[k], f"{r['url']}: {k}")
            self.assertEqual(int(r["pages"]), len(self.scan["urls"][r["url"]]["pages"]), r["url"])
            self.assertIn(r["example_page"], self.scan["urls"][r["url"]]["pages"] | self.scan["urls"][r["url"]]["files"])
            self.assertRegex(r["checked_at_utc"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")

    def test_the_eighteen_hosts(self):
        hosts = sorted(L.host_of(u) for u in self.scan["urls"])
        self.assertEqual(hosts.count("www.nj.gov"), 15)
        self.assertEqual(set(hosts) - {"www.nj.gov"}, {"files-backend.assets.thrillshare.com", "resources.finalsite.net",
                                                      "www.west-windsor-plainsboro.k12.nj.us"})

    def test_no_live_check_in_ci(self):
        for d, _, names in os.walk(os.path.join(ROOT, ".github")):
            for n in names:
                with open(os.path.join(d, n), encoding="utf-8", errors="replace") as fh:
                    self.assertNotIn("--live", fh.read(), n)
                    fh.seek(0)
                    self.assertNotIn("--write-baseline", fh.read(), n)


class OfflineMutations(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        fixture(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def offline(self):
        return run(["--offline", "--root", self.root])

    def test_fixture_passes_and_counts(self):
        rc, out = self.offline()
        self.assertEqual(rc, 0, out)
        self.assertIn("pages scanned: 2\n", out)
        self.assertIn("unique external URLs: 4 ", out)  # excluded: schema.org, CC licence, GoatCounter, hazeydata, k12comp.com
        s = L.scan(self.root)
        self.assertIn(WITH_SPACE + "#p2", s["urls"])  # exact published string: no decoding, fragment kept for dedupe
        self.assertEqual(s["urls"][QUERY]["pages"], {"nj/index.html", "nj/a/index.html"})  # JSON-LD
        self.assertEqual(s["urls"][CSV]["files"], {"api/v1/nj/1.json", "data/nj/history/1.csv"})  # CSV cell, not "url,abc"
        self.assertEqual(s["unresolved"], [])

    def test_new_url_on_a_page_fails(self):
        p = os.path.join(self.root, "nj", "a", "index.html")
        with open(p, encoding="utf-8") as fh:
            t = fh.read()
        write(self.root, "nj/a/index.html", t.replace("</body>", '<a href="https://new.example/x.pdf">n</a></body>'))
        rc, out = self.offline()
        self.assertEqual(rc, 1)
        self.assertIn("FAIL no baseline row: https://new.example/x.pdf (on 1 pages, 0 api/data files, e.g. nj/a/index.html)", out)

    def test_new_url_in_an_api_json_fails(self):
        write(self.root, "api/v1/nj/2.json", json.dumps({"sources": [{"url": "https://new.example/y.csv"}]}))
        rc, out = self.offline()
        self.assertEqual(rc, 1)
        self.assertIn("FAIL no baseline row: https://new.example/y.csv (on 0 pages, 1 api/data files, e.g. api/v1/nj/2.json)", out)

    def test_new_url_in_data_fails(self):
        write(self.root, "data/nj/history/2.csv", "leaid,url\n2,https://new.example/z.zip\n")
        rc, out = self.offline()
        self.assertEqual(rc, 1)
        self.assertIn("FAIL no baseline row: https://new.example/z.zip", out)

    def test_stale_baseline_row_fails(self):
        with open(os.path.join(self.root, "docs", "nj-link-baseline.tsv"), "a", encoding="utf-8") as fh:
            fh.write("\t".join(("https://gone.example/old.pdf", "1", "nj/index.html", "200", "https://gone.example/old.pdf", "application/pdf",
                                "1", "", "", "2026-11-16T00:00:00Z")) + "\n")
        rc, out = self.offline()
        self.assertEqual(rc, 1)
        self.assertIn("FAIL stale baseline row (on no page, JSON or data file): https://gone.example/old.pdf", out)

    def test_non_2xx_baseline_row_fails(self):
        p = os.path.join(self.root, "docs", "nj-link-baseline.tsv")
        with open(p, encoding="utf-8") as fh:
            t = fh.read()
        write(self.root, "docs/nj-link-baseline.tsv", t.replace(f"{CSV}\t1\tnj/index.html\t200", f"{CSV}\t1\tnj/index.html\t404"))
        rc, out = self.offline()
        self.assertEqual(rc, 1)
        self.assertIn(f"FAIL baseline row is not 2xx (404): {CSV}", out)

    def test_missing_baseline_fails(self):
        os.remove(os.path.join(self.root, "docs", "nj-link-baseline.tsv"))
        rc, out = self.offline()
        self.assertEqual(rc, 1)
        self.assertIn("FAIL no baseline file", out)

    def test_local_href_to_a_missing_file_fails(self):
        with open(os.path.join(self.root, "nj", "index.html"), encoding="utf-8") as fh:
            t = fh.read()
        write(self.root, "nj/index.html", t.replace("</body>", '<a href="/nj/no-such-district-0000000/">d</a>'
                                                                '<img src="missing.png"><a href="https://k12comp.com/nj/gone/">g</a></body>'))
        rc, out = self.offline()
        self.assertEqual(rc, 1)
        self.assertIn("unresolved local refs: 3\n", out)
        for ref in ("/nj/no-such-district-0000000/", "missing.png", "https://k12comp.com/nj/gone/"):
            self.assertIn(f"FAIL unresolved local ref: {ref} on nj/index.html", out)

    def test_local_target_forms(self):
        self.assertEqual(L.local_target("nj/a/index.html", "../"), "nj")
        self.assertEqual(L.local_target("nj/a/index.html", "/"), "")
        self.assertEqual(L.local_target("nj/a/index.html", "https://k12comp.com/nj/a/?x=1#y"), "nj/a")
        self.assertEqual(L.local_target("nj/a/index.html", "a%20b.pdf"), "nj/a/a b.pdf")
        self.assertIsNone(L.local_target("nj/a/index.html", "https://www.nj.gov/x.csv"))
        self.assertIsNone(L.local_target("nj/a/index.html", "#top"))
        self.assertIsNone(L.local_target("nj/a/index.html", "mailto:a@b.c"))


# --- classifier (stubbed responses, one case each) --------------------------------------------------------------------------------
U = "https://h.example/f.pdf"
U2 = "https://h.example/new/f.pdf"


class Classifier(unittest.TestCase):
    def assertClass(self, table, want, base=None, reason=None):
        (c, why), facts, stub = check(table, base="row" if base is None else base)
        self.assertEqual(c, want, (why, facts))
        if reason:
            self.assertIn(reason, "; ".join(why))
        return facts, stub

    def test_200_pass(self):
        facts, stub = self.assertClass({("HEAD", U): L.Response(200, hdrs())}, "PASS")
        self.assertEqual([c[0] for c in stub.calls], ["HEAD"])
        self.assertEqual(facts["final_url"], U)

    def test_301_then_200_pass(self):
        facts, stub = self.assertClass({("HEAD", U): L.Response(301, {"Location": "/new/f.pdf"}), ("HEAD", U2): L.Response(200, hdrs())}, "PASS")
        self.assertEqual(facts["final_url"], U2)
        self.assertEqual([c[:2] for c in stub.calls], [("HEAD", U), ("HEAD", U2)])

    def test_404_fail(self):
        self.assertClass({("*", U): L.Response(404, {})}, "FAIL", reason="status 404")

    def test_410_fail(self):
        self.assertClass({("*", U): L.Response(410, {})}, "FAIL", reason="status 410")

    def test_500_fail(self):
        self.assertClass({("*", U): L.Response(500, {})}, "FAIL", reason="status 500")

    def test_301_then_404_fail(self):
        facts, _ = self.assertClass({("*", U): L.Response(301, {"Location": U2}), ("*", U2): L.Response(404, {})}, "FAIL",
                                    reason="status 404 after redirects (chain 301 -> 404 -> 301 -> 404)")
        self.assertEqual(facts["final_url"], U2)

    def test_dns_failure_fail(self):
        self.assertClass({("*", U): L.NetError("dns", "Name or service not known")}, "FAIL", reason="DNS failure")

    def test_tls_failure_fail(self):
        self.assertClass({("*", U): L.NetError("tls", "CERTIFICATE_VERIFY_FAILED")}, "FAIL", reason="TLS failure")

    def test_connection_failure_fail(self):
        self.assertClass({("*", U): L.NetError("conn", "ConnectionRefusedError")}, "FAIL", reason="connection failure")

    def test_redirect_loop_fail(self):
        self.assertClass({("*", U): L.Response(302, {"Location": U})}, "FAIL", reason="more than 10 redirects")

    def test_401_warn(self):
        self.assertClass({("*", U): L.Response(401, {})}, "WARN", reason="status 401")

    def test_403_warn(self):
        self.assertClass({("*", U): L.Response(403, {})}, "WARN", reason="status 403")

    def test_429_warn(self):
        self.assertClass({("*", U): L.Response(429, {})}, "WARN", reason="status 429")

    def test_head_405_then_get_206_pass(self):
        facts, stub = self.assertClass({("HEAD", U): L.Response(405, {}),
                                        ("GET", U): L.Response(206, hdrs(length="1", **{"Content-Range": "bytes 0-0/100"}), 1)}, "PASS")
        self.assertEqual(facts["content_length"], "100")  # the full size from Content-Range, not the 1-byte part
        self.assertEqual(facts["method"], "GET")

    def test_timeout_warn(self):
        facts, stub = self.assertClass({("*", U): L.NetError("timeout", "timed out")}, "WARN", reason="timeout: re-run")
        self.assertEqual(len(stub.calls), 1)  # no retry, no GET after an error

    def test_pdf_to_text_html_fail(self):
        self.assertClass({("HEAD", U): L.Response(200, hdrs(ctype="text/html; charset=utf-8"))}, "FAIL", reason="soft-404")

    def test_html_to_html_is_not_a_flip(self):
        page_url = "https://h.example/DisplayFile.aspx?itemId=1"
        (c, why), _, _ = check({("HEAD", page_url): L.Response(200, hdrs(ctype="text/html"))}, url=page_url,
                               base=row(url=page_url, ctype="text/html"))
        self.assertEqual(c, "PASS", why)

    def test_document_url_served_as_html_fails_without_a_baseline(self):
        """A .csv/.zip URL answered 200 text/html (a short landing page, no etag or last-modified) is a soft-404 on a first
        --write-baseline too, when there is no baseline content-type to compare with."""
        for url in ("https://h.example/ufb/download/employees22.csv", "https://h.example/cs/Certificated%20Staff%202021.zip",
                    "https://h.example/f.pdf#page=2"):
            (c, why), _, _ = check({("HEAD", url.split("#")[0]): L.Response(200, hdrs(ctype="text/html", length="212", lm="", etag=""))},
                                   url=url, base=None)
            self.assertEqual(c, "FAIL", url)
            self.assertIn("document URL served as text/html (soft-404", why[0])
        self.assertFalse(L.document_path("https://h.example/DisplayFile.aspx?itemId=1"))
        self.assertTrue(L.document_path("https://h.example/A.ZIP?x=1"))

    def test_etag_change_warn(self):
        self.assertClass({("HEAD", U): L.Response(200, hdrs(etag='"e2"'))}, "WARN", reason="source changed: re-hash per PLAN §4 (etag)")

    def test_content_length_change_warn(self):
        self.assertClass({("HEAD", U): L.Response(200, hdrs(length="101"))}, "WARN", reason="(content_length)")

    def test_last_modified_change_warn(self):
        self.assertClass({("HEAD", U): L.Response(200, hdrs(lm="Tue, 02 Jan 2024 00:00:00 GMT"))}, "WARN", reason="(last_modified)")

    def test_final_url_host_change_warn(self):
        other = "https://other.example/f.pdf"
        self.assertClass({("HEAD", U): L.Response(302, {"Location": other}), ("HEAD", other): L.Response(200, hdrs())}, "WARN",
                         reason="(final_url host)")

    def test_missing_etag_and_last_modified_in_both_is_no_warn(self):
        self.assertClass({("HEAD", U): L.Response(200, hdrs(lm="", etag=""))}, "PASS", base=row(lm="", etag=""))


# --- politeness and modes ----------------------------------------------------------------------------------------------------------
class Politeness(unittest.TestCase):
    def test_sequential_gaps_head_first_ranged_get_one_byte(self):
        a, b, c, c2 = "https://a.example/1.pdf", "https://b.example/2.csv", "https://c.example/3.zip", "https://c.example/3b.zip"
        clock = FakeClock()
        stub = Stub({("HEAD", a): L.Response(200, hdrs()), ("HEAD", b): L.Response(405, {}), ("GET", b): L.Response(206, hdrs(), 1),
                     ("HEAD", c): L.Response(301, {"Location": c2}), ("HEAD", c2): L.Response(403, {}),
                     ("GET", c): L.Response(301, {"Location": c2}), ("GET", c2): L.Response(200, hdrs(), 1)}, clock)
        log = io.StringIO()
        ch = L.Checker(stub, clock, log)
        for u in (a, b, c):
            ch.check(u)
        starts = [r[0] for r in ch.requests]
        self.assertEqual([round(y - x, 6) >= L.GAP_S for x, y in zip(starts, starts[1:])], [True] * (len(starts) - 1))
        self.assertGreaterEqual(L.GAP_S, 1.1)
        self.assertEqual([(m, u) for m, u, _, _ in stub.calls],
                         [("HEAD", a), ("HEAD", b), ("GET", b), ("HEAD", c), ("HEAD", c2), ("GET", c), ("GET", c2)])
        for m, u, h, t in stub.calls:
            self.assertEqual(h["User-Agent"], L.UA)
            self.assertRegex(L.UA, r"^k12comp-linkcheck/[\d.]+ \(\+https://k12comp\.com/about/\)$")
            self.assertEqual(t, 20)
            self.assertEqual(h.get("Range"), "bytes=0-0" if m == "GET" else None)
        self.assertTrue(all(r[5] <= 1 for r in ch.requests))
        self.assertLessEqual(len(ch.requests), 2 * 3 + 2)  # one HEAD + one GET per URL, plus the redirect hops
        lines = log.getvalue().splitlines()
        self.assertEqual(len(lines), len(stub.calls))
        self.assertRegex(lines[0], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z\tHEAD\thttps://a\.example/1\.pdf\t200\t0$")
        self.assertRegex(lines[2], r"\tGET\thttps://b\.example/2\.csv\t206\t1$")

    def test_the_real_transport_reads_at_most_one_byte(self):
        class Resp:
            status = 200

            def __init__(self):
                self.asked = []

            def read(self, n=None):
                self.asked.append(n)
                return b"x"[:n]

            def getheaders(self):
                return [("Content-Type", "application/pdf")]
        r = Resp()

        class Conn:
            def __init__(self, host, port, timeout):
                self.timeout = timeout

            def request(self, method, path, headers):
                self.sent = (method, path, headers)

            def getresponse(self):
                return r

            def close(self):
                pass
        import http.client
        with mock.patch.object(http.client, "HTTPSConnection", Conn):
            got = L.HttpTransport().request("GET", "https://h.example/a%20b.zip?x=1#frag", {"Range": "bytes=0-0"}, 20)
            head = L.HttpTransport().request("HEAD", "https://h.example/a.zip", {}, 20)
        self.assertEqual((got.status, got.body_bytes, head.body_bytes), (200, 1, 0))
        self.assertEqual(r.asked, [1])

    def test_fragment_is_stripped_for_checking_only(self):
        clock = FakeClock()
        stub = Stub({("HEAD", WITH_SPACE): L.Response(200, hdrs())}, clock)
        facts = L.Checker(stub, clock).check(WITH_SPACE + "#p2")
        self.assertEqual(stub.calls[0][1], WITH_SPACE)  # percent-encoding kept as published
        self.assertEqual(facts["url"], WITH_SPACE + "#p2")


class LiveModes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = os.path.join(self.tmp.name, "site")
        fixture(self.root)
        self.ok = {("HEAD", u.split("#")[0]): L.Response(200, hdrs(ctype="application/pdf", length="10", lm="", etag=""))
                   for u in (PDF, CSV, WITH_SPACE, QUERY)}

    def tearDown(self):
        self.tmp.cleanup()

    def live(self, table, *extra):
        clock = FakeClock()
        return run(["--root", self.root, *extra], transport=Stub(table, clock), clock=clock)

    def test_live_pass_writes_log_and_report(self):
        log, rep = os.path.join(self.tmp.name, "req.log"), os.path.join(self.tmp.name, "report.md")
        rc, out = self.live(self.ok, "--live", "--log", log, "--report", rep)
        self.assertEqual(rc, 0, out)
        self.assertIn("live: OK", out)
        with open(log, encoding="utf-8") as fh:
            self.assertEqual(len(fh.read().splitlines()), 4)
        with open(rep, encoding="utf-8") as fh:
            self.assertIn("PASS 4, WARN 0, FAIL 0", fh.read())

    def test_live_fails_naming_the_dead_url(self):
        dead = "https://short.example/2u0cp"
        with open(os.path.join(self.root, "nj", "index.html"), encoding="utf-8") as fh:
            t = fh.read()
        write(self.root, "nj/index.html", t.replace("</body>", f'<a href="{dead}">c</a></body>'))
        table = dict(self.ok)
        table[("*", dead)] = L.Response(301, {"Location": "https://hop.example/x"})
        table[("*", "https://hop.example/x")] = L.Response(404, {})
        rc, out = self.live(table, "--live")
        self.assertEqual(rc, 1)
        self.assertIn(f"FAIL {dead}: status 404 after redirects", out)
        self.assertIn(f"live: FAIL {dead}", out)

    def test_live_warn_exits_0_and_timeout_says_rerun(self):
        table = dict(self.ok)
        table[("HEAD", PDF)] = L.NetError("timeout", "timed out")
        table[("HEAD", CSV)] = L.Response(200, hdrs(length="11", lm="", etag=""))
        rc, out = self.live(table, "--live")
        self.assertEqual(rc, 0, out)
        self.assertIn(f"WARN {PDF}: timeout: re-run", out)
        self.assertIn(f"WARN {CSV}: source changed: re-hash per PLAN §4 (content_length)", out)
        self.assertIn("1 timeout(s): re-run", out)

    def test_write_baseline_writes_sorted_rows(self):
        os.remove(os.path.join(self.root, "docs", "nj-link-baseline.tsv"))
        rc, out = self.live(self.ok, "--write-baseline")
        self.assertEqual(rc, 0, out)
        rc2, out2 = run(["--offline", "--root", self.root])
        self.assertEqual(rc2, 0, out2)
        rows = L.read_baseline(os.path.join(self.root, "docs", "nj-link-baseline.tsv"))
        self.assertEqual(list(rows), sorted(rows))
        self.assertEqual(rows[QUERY]["pages"], "2")
        self.assertEqual(rows[WITH_SPACE + "#p2"]["final_url"], WITH_SPACE)
        self.assertRegex(rows[CSV]["checked_at_utc"], r"^2026-11-16T00:\d\d:\d\dZ$")  # the fake clock's UTC day

    def refuses(self, table):
        p = os.path.join(self.root, "docs", "nj-link-baseline.tsv")
        with open(p, encoding="utf-8") as fh:
            before = fh.read()
        rc, out = self.live(table, "--write-baseline")
        self.assertEqual(rc, 1, out)
        self.assertIn("refusing to write", out)
        with open(p, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), before)

    def test_write_baseline_refuses_on_fail(self):
        self.refuses({**self.ok, ("HEAD", CSV): L.Response(404, {}), ("GET", CSV): L.Response(404, {})})

    def test_write_baseline_refuses_on_timeout(self):
        self.refuses({**self.ok, ("HEAD", CSV): L.NetError("timeout", "timed out")})

    def test_first_write_baseline_refuses_a_document_served_as_html(self):
        os.remove(os.path.join(self.root, "docs", "nj-link-baseline.tsv"))
        rc, out = self.live({**self.ok, ("HEAD", CSV): L.Response(200, hdrs(ctype="text/html", length="212", lm="", etag=""))},
                            "--write-baseline")
        self.assertEqual(rc, 1, out)
        self.assertIn(f"FAIL {CSV}: document URL served as text/html", out)
        self.assertIn("refusing to write", out)
        self.assertFalse(os.path.exists(os.path.join(self.root, "docs", "nj-link-baseline.tsv")))

    def test_write_baseline_compares_with_the_old_baseline(self):
        p = os.path.join(self.root, "docs", "nj-link-baseline.tsv")
        with open(p, encoding="utf-8") as fh:
            before = fh.read()
        rc, out = self.live({**self.ok, ("HEAD", QUERY): L.Response(200, hdrs(ctype="text/html", length="10", lm="", etag=""))},
                            "--write-baseline")
        self.assertEqual(rc, 1, out)
        self.assertIn(f"FAIL {QUERY}: content-type flipped from application/pdf to text/html", out)
        with open(p, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), before)

    def test_write_baseline_refuses_on_403(self):
        self.refuses({**self.ok, ("HEAD", CSV): L.Response(403, {}), ("GET", CSV): L.Response(403, {})})


# --- chart3 mobile "districts" label (OQ-7) -----------------------------------------------------------------------------------------
class Chart3Label(unittest.TestCase):
    def read(self):
        with open(DIST, encoding="utf-8", newline="") as fh:
            return fh.read()

    def test_label_sits_at_x6(self):
        svg = self.read()
        self.assertEqual(svg.count('x="6" y="213.7856" transform="rotate(-90 6 213.7856)">districts</text>'), 1)
        self.assertNotIn('rotate(-90 4 213.7856)', svg)
        self.assertIn('<g id="axes_1" transform="translate(8 43.95)">', svg)
        self.assertEqual(F.rotated_text_problems(svg), [])

    def test_rule_fails_on_x4_and_check_exits_1_on_a_scratch_copy(self):
        old = self.read().replace(F.DIST_YLABEL, F.DIST_YLABEL_OLD)
        self.assertEqual(F.rotated_text_problems(old),
                         ["rotated text 'districts': baseline x 12 - 1.05 x 12 = -0.60, less than 1 unit inside the left edge"])
        self.assertEqual(len(F.rotated_text_problems(self.read().replace(F.DIST_YLABEL, F.DIST_YLABEL_OLD.replace('x="4"', 'x="5"').replace("-90 4 ", "-90 5 ")))), 1)  # 13 - 12.6
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, "chart3.svg")
            with open(p, "w", encoding="utf-8", newline="") as fh:
                fh.write(old)
            with mock.patch.object(F, "DISTRIBUTION", p), mock.patch.object(F, "files", lambda: []), \
                    contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(F.main(["--check"]), 1)
            self.assertIn("rotated text 'districts'", out.getvalue())
            with mock.patch.object(F, "DISTRIBUTION", p), mock.patch.object(F, "files", lambda: []), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(F.main(["--write"]), 0)
                with open(p, encoding="utf-8", newline="") as fh:
                    self.assertEqual(fh.read(), self.read())
        self.assertEqual(F.rotated_text_problems(self.read()), [])

    def test_fixup_is_idempotent_and_touches_one_node(self):
        svg = self.read()
        old = svg.replace(F.DIST_YLABEL, F.DIST_YLABEL_OLD)
        once = F.distribution(old)
        self.assertEqual(once, svg)
        self.assertEqual(F.distribution(once), once)
        diff = [(a, b) for a, b in zip(old.split("\n"), once.split("\n")) if a != b]
        self.assertEqual(len(diff), 1)
        self.assertEqual(re.sub(r'x="\d"|rotate\(-90 \d ', "", diff[0][0]), re.sub(r'x="\d"|rotate\(-90 \d ', "", diff[0][1]))

    def test_rule_reads_ancestor_translate_and_font_size(self):
        svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><g transform="translate(3 0)"><g transform="translate(2 5)">'
               '<text style="font-size: 10px" x="7" y="50" transform="rotate(-90 7 50)">a</text></g></g>'
               '<text style="font-size: 10px" x="2" y="50">flat text is not this rule</text></svg>')
        self.assertEqual(F.rotated_text_problems(svg), [])  # 12 - 10.5 = 1.5
        self.assertEqual(len(F.rotated_text_problems(svg.replace('x="7"', 'x="6"'))), 1)  # 11 - 10.5 = 0.5

    def test_the_repo_check_passes(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(F.main(["--check"]), 0)
        self.assertIn("0 still misfit", out.getvalue())


class ChartChain(unittest.TestCase):
    """The documented chart chain (docs/nj-history.md) run twice on a scratch copy changes nothing the second time, and the first run
    leaves chart3 mobile as committed."""

    def test_double_write_on_a_scratch_copy(self):
        tools = ["nj_api_index.py", "nj_guide_tables.py", "nj_fte_marks.py", "nj_mobile_chart_fit.py", "nj_chart_label_edge.py"]
        with tempfile.TemporaryDirectory() as tmp:
            dst = os.path.join(tmp, "web")
            files = subprocess.run(["git", "-C", ROOT, "ls-files", "-z"], capture_output=True, check=True).stdout.decode().split("\0")
            for f in files:
                if f and os.path.exists(os.path.join(ROOT, f)):
                    os.makedirs(os.path.dirname(os.path.join(dst, f)) or dst, exist_ok=True)
                    shutil.copy2(os.path.join(ROOT, f), os.path.join(dst, f))

            def snapshot():
                out = {}
                for f in files:
                    p = os.path.join(dst, f)
                    if f and os.path.exists(p):
                        with open(p, "rb") as fh:
                            out[f] = fh.read()
                return out
            before = snapshot()
            for _ in range(2):
                for t in tools:
                    r = subprocess.run([sys.executable, os.path.join(dst, "tools", t), "--write"], cwd=dst, capture_output=True, text=True)
                    self.assertEqual(r.returncode, 0, (t, r.stdout[-2000:], r.stderr[-2000:]))
            after = snapshot()
            self.assertEqual(sorted(f for f in before if before[f] != after.get(f)), [])


if __name__ == "__main__":
    unittest.main()
