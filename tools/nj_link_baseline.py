#!/usr/bin/env python3
"""K12-NJ-UPKEEP-001: /nj/ link baseline check (stdlib only). See docs/nj-link-baseline.md.

Every external source and district link on the k12comp.com /nj/ pages is listed, checked politely and compared with a committed baseline
(docs/nj-link-baseline.tsv, one row per unique URL). Three modes:

    python3 tools/nj_link_baseline.py --offline          # default; no network. Exit 1 on an unbaselined URL, a stale baseline row,
                                                         # a non-2xx baseline row or an unresolved local ref
    python3 tools/nj_link_baseline.py --live --log L --report R   # polite network check of every URL against the baseline; exit 1 on a FAIL
    python3 tools/nj_link_baseline.py --write-baseline --log L    # the same live check (against the old baseline when there is one),
                                                                  # then rewrite it; refuses on any FAIL, non-2xx row or timeout

Scope (offline). Pages: tracked `nj/**/*.html` (`git ls-files` in a git tree, else a walk of --root). External URLs: absolute http(s) values of
`href`, `src`, `content` and `action` attributes and every URL in a JSON-LD block on those pages, plus every URL in `api/v1/nj/*.json` and
`data/nj/**` (any file). Self and infrastructure hosts are not source links and are excluded: k12comp.com (internal, resolved as a local
ref instead), schema.org, creativecommons.org (licence), gc.zgo.at and k12comp.goatcounter.com (GoatCounter), hazeydata.ai (subscribe form).
URLs are deduplicated on the exact published string (no percent-decoding; query strings kept); the fragment is stripped only when the URL is
requested. Local refs: every relative, root-relative or https://k12comp.com/ `href`/`src` (and k12comp.com `content`, `action` and JSON-LD
URL) on the pages must resolve to a file in the tree (the path itself or its index.html).

Classification (live, OQ-3), per URL, on the final response after redirects:
  FAIL  final status 404, 410 or any other 4xx except 401/403/429; any 5xx; a redirect chain ending in a FAIL status (or not ending: a 3xx
        with no Location, or more than MAX_HOPS hops); DNS failure; TLS failure; connection refused/reset; a final content-type that flips from
        a document type in the baseline (pdf, csv, text/plain, zip, xlsx/xls) to text/html (soft-404 landing page); text/html for a URL whose
        path ends in a document extension (.pdf .csv .zip .xlsx .xls .txt), with or without a baseline row (the same soft-404, caught on a
        first --write-baseline too).
  WARN  401, 403, 429; timeout ("re-run"); an etag, content-length, last-modified or final_url host that differs from the baseline
        ("source changed: re-hash per PLAN §4"). A header missing in both the baseline and the live response is not a change.
  PASS  2xx after redirects with none of the above.

Politeness (OQ-5): strictly sequential; at least GAP_S (1.1 s) between any two request starts (every redirect hop is a request);
HEAD following redirects first (final_url recorded); a ranged GET (`Range: bytes=0-0`, following redirects) only when the HEAD's final status
is not 2xx; at most 1 body byte read, never a body download; TIMEOUT_S (20 s) per request; User-Agent UA; no other retries.
The network layer is `HttpTransport`; tests pass a stub transport and a fake clock (no sockets).
"""
import argparse
import csv
import datetime
import html.parser
import io
import json
import os
import posixpath
import re
import socket
import ssl
import subprocess
import sys
import time
import urllib.parse

VERSION = "1.0"
UA = f"k12comp-linkcheck/{VERSION} (+https://k12comp.com/about/)"
GAP_S = 1.1
TIMEOUT_S = 20
MAX_HOPS = 10
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASELINE = os.path.join("docs", "nj-link-baseline.tsv")
COLUMNS = ("url", "pages", "example_page", "status", "final_url", "content_type", "content_length", "last_modified", "etag", "checked_at_utc")
SELF_HOSTS = {"k12comp.com", "www.k12comp.com"}
EXCLUDED_HOSTS = {"schema.org", "creativecommons.org", "gc.zgo.at", "k12comp.goatcounter.com", "hazeydata.ai"}
URL_ATTRS = ("href", "src", "content", "action")
LOCAL_ATTRS = ("href", "src")
SKIP_SCHEMES = ("mailto:", "tel:", "#", "data:", "javascript:")
URL_IN_TEXT = re.compile(r"https?://[^\s\"'<>\\]+")
DOCUMENT_TYPES = ("pdf", "csv", "text/plain", "zip", "spreadsheetml", "ms-excel")
DOCUMENT_EXTS = (".pdf", ".csv", ".zip", ".xlsx", ".xls", ".txt")
REDIRECTS = (301, 302, 303, 307, 308)


# --- offline scan ---------------------------------------------------------------------------------------------------------------------
def host_of(url):
    return (urllib.parse.urlsplit(url).hostname or "").lower()


def tree_files(root):
    """Repo-relative paths of the files in the tree: `git ls-files` when root is the top of a git work tree, else a walk."""
    try:
        top = subprocess.run(["git", "-C", root, "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        top = None
    if top and os.path.realpath(top) == os.path.realpath(root):
        out = subprocess.run(["git", "-C", root, "ls-files", "-z"], capture_output=True, check=True).stdout.decode("utf-8")
        return sorted(p for p in out.split("\0") if p)
    files = []
    for d, dirs, names in os.walk(root):
        dirs[:] = sorted(x for x in dirs if x != ".git")
        files += [os.path.relpath(os.path.join(d, n), root).replace(os.sep, "/") for n in names]
    return sorted(files)


def urls_in_text(text):
    return [u.rstrip(".,;:)]}") for u in URL_IN_TEXT.findall(text)]


def urls_in_csv(text):
    """Every URL in every cell of a CSV file (a comma ends a cell, not a URL)."""
    return [u for row in csv.reader(io.StringIO(text, newline="")) for cell in row for u in urls_in_text(cell)]


def urls_in_json(text):
    """Every URL in every string of a JSON document (regex over the raw text if it does not parse)."""
    try:
        doc = json.loads(text)
    except ValueError:
        return urls_in_text(text)
    out = []

    def walk(v):
        if isinstance(v, str):
            out.extend(urls_in_text(v))
        elif isinstance(v, dict):
            for k, x in v.items():
                walk(k)
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)
    walk(doc)
    return out


class PageParser(html.parser.HTMLParser):
    """Collects (attribute, value) pairs of URL attributes and the text of JSON-LD blocks."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.attrs, self.jsonld, self._in_ld = [], [], False

    def handle_starttag(self, tag, attrs):
        for k, v in attrs:
            if k in URL_ATTRS and v:
                self.attrs.append((k, v.strip()))
        if tag == "script" and (dict(attrs).get("type") or "").strip().lower() == "application/ld+json":
            self._in_ld = True
            self.jsonld.append("")

    def handle_endtag(self, tag):
        if tag == "script":
            self._in_ld = False

    def handle_data(self, data):
        if self._in_ld:
            self.jsonld[-1] += data


def local_target(page, ref):
    """Repo-relative target of a local ref on page, or None when the ref is external / not a file ref."""
    if ref.startswith(SKIP_SCHEMES) or not ref:
        return None
    parts = urllib.parse.urlsplit(ref)
    if parts.scheme in ("http", "https") or ref.startswith("//"):
        if (parts.hostname or "").lower() not in SELF_HOSTS:
            return None
        path = parts.path or "/"
    elif parts.scheme:
        return None
    else:
        path = parts.path
        if not path:
            return None  # "?x" or "#x" only: the page itself
    path = urllib.parse.unquote(path)
    t = posixpath.normpath(path.lstrip("/") if path.startswith("/") else posixpath.join(posixpath.dirname(page), path))
    return "" if t == "." else t


def resolves(target, tree):
    return target in tree or ((target + "/") if target else "") + "index.html" in tree


def scan(root):
    """Offline scan of the tree. Returns a dict: pages, urls {url: {"pages": set, "files": set}}, local_refs, local_targets, unresolved."""
    files = tree_files(root)
    tree = set(files)
    pages = [f for f in files if f.startswith("nj/") and f.endswith(".html")]
    data = [f for f in files if (f.startswith("api/v1/nj/") and f.endswith(".json") and "/" not in f[len("api/v1/nj/"):])
            or f.startswith("data/nj/")]
    urls, local_refs, targets, unresolved = {}, 0, set(), []

    def add(url, page=None, file=None):
        h = host_of(url)
        if h in EXCLUDED_HOSTS or h in SELF_HOSTS:
            return
        e = urls.setdefault(url, {"pages": set(), "files": set()})
        (e["pages"].add(page) if page else e["files"].add(file))

    for page in pages:
        with open(os.path.join(root, page), encoding="utf-8") as fh:
            p = PageParser()
            p.feed(fh.read())
            p.close()
        found = [(k, v) for k, v in p.attrs]
        for block in p.jsonld:
            found += [("jsonld", u) for u in urls_in_json(block)]
        for k, v in found:
            absolute = re.match(r"https?://", v, re.I)
            if absolute and host_of(v) not in SELF_HOSTS:
                add(v, page=page)
                continue
            if not absolute and k not in LOCAL_ATTRS:
                continue  # a relative content= value (e.g. a description) is not a link
            t = local_target(page, v)
            if t is None:
                continue
            local_refs += 1
            targets.add(t)
            if not resolves(t, tree):
                unresolved.append((page, v))
    for f in data:
        with open(os.path.join(root, f), encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        for u in (urls_in_json(text) if f.endswith(".json") else urls_in_csv(text) if f.endswith(".csv") else urls_in_text(text)):
            add(u, file=f)
    return {"pages": pages, "data_files": data, "urls": urls, "local_refs": local_refs, "local_targets": targets, "unresolved": unresolved}


def read_baseline(path):
    """{url: row dict} from the TSV, or None when the file does not exist."""
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8", newline="") as fh:
        lines = fh.read().split("\n")
    header = lines[0].split("\t")
    if tuple(header) != COLUMNS:
        raise ValueError(f"{path}: header is not {COLUMNS}")
    rows = {}
    for ln in lines[1:]:
        if not ln:
            continue
        cells = ln.split("\t")
        if len(cells) != len(COLUMNS):
            raise ValueError(f"{path}: row has {len(cells)} cells, not {len(COLUMNS)}: {ln[:120]}")
        row = dict(zip(COLUMNS, cells))
        if row["url"] in rows:
            raise ValueError(f"{path}: duplicate row {row['url']}")
        rows[row["url"]] = row
    return rows


def offline_problems(s, baseline):
    """Offline FAIL lines: unbaselined URLs, stale baseline rows, non-2xx baseline rows, unresolved local refs."""
    out = []
    base = baseline or {}
    if baseline is None:
        out.append("FAIL no baseline file")
    for u in sorted(set(s["urls"]) - set(base)):
        e = s["urls"][u]
        where = sorted(e["pages"])[:1] or sorted(e["files"])[:1]
        out.append(f"FAIL no baseline row: {u} (on {len(e['pages'])} pages, {len(e['files'])} api/data files, e.g. {where[0]})")
    for u in sorted(set(base) - set(s["urls"])):
        out.append(f"FAIL stale baseline row (on no page, JSON or data file): {u}")
    for u in sorted(set(base) & set(s["urls"])):
        if not re.fullmatch(r"2\d\d", base[u]["status"]):
            out.append(f"FAIL baseline row is not 2xx ({base[u]['status']}): {u}")
    for page, ref in s["unresolved"]:
        out.append(f"FAIL unresolved local ref: {ref} on {page}")
    return out


def summary_lines(s, baseline, path):
    occ = sum(len(e["pages"]) for e in s["urls"].values())
    return [f"pages scanned: {len(s['pages'])}",
            f"api/data files scanned: {len(s['data_files'])}",
            f"unique external URLs: {len(s['urls'])} ({sum(1 for e in s['urls'].values() if e['pages'])} on pages, page-URL pairs {occ})",
            f"local refs: {s['local_refs']} ({len(s['local_targets'])} unique targets)",
            f"unresolved local refs: {len(s['unresolved'])}",
            f"baseline: {path}: {'missing' if baseline is None else str(len(baseline)) + ' rows'}"]


# --- network layer ----------------------------------------------------------------------------------------------------------------------
class Response:
    def __init__(self, status, headers=None, body_bytes=0):
        self.status = status
        self.headers = {k.lower(): v for k, v in (headers or {}).items()}
        self.body_bytes = body_bytes


class NetError(Exception):
    """kind: dns | tls | timeout | conn"""

    def __init__(self, kind, detail=""):
        super().__init__(f"{kind}: {detail}")
        self.kind, self.detail = kind, detail


class HttpTransport:
    """One request per call, no retries, no redirects (the checker follows them), at most 1 body byte read (GET only)."""

    def request(self, method, url, headers, timeout):
        import http.client
        parts = urllib.parse.urlsplit(url)
        path = urllib.parse.urlunsplit(("", "", parts.path or "/", parts.query, ""))
        cls = http.client.HTTPSConnection if parts.scheme == "https" else http.client.HTTPConnection
        conn = cls(parts.hostname, parts.port, timeout=timeout)
        try:
            conn.request(method, path, headers=headers)
            r = conn.getresponse()
            n = len(r.read(1)) if method == "GET" and r.status not in REDIRECTS else 0
            return Response(r.status, dict(r.getheaders()), n)
        except socket.gaierror as e:
            raise NetError("dns", str(e))
        except (ssl.SSLError, ssl.CertificateError) as e:
            raise NetError("tls", str(e))
        except (socket.timeout, TimeoutError) as e:
            raise NetError("timeout", str(e) or "timed out")
        except (OSError, http.client.HTTPException) as e:
            raise NetError("conn", f"{type(e).__name__}: {e}")
        finally:
            conn.close()


class Clock:
    monotonic = staticmethod(time.monotonic)
    sleep = staticmethod(time.sleep)

    @staticmethod
    def utcnow():
        return datetime.datetime.now(datetime.timezone.utc)


def iso_ms(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


class Checker:
    """Sequential polite checker: every request start is at least GAP_S after the previous one."""

    def __init__(self, transport=None, clock=None, log=None):
        self.transport = transport or HttpTransport()
        self.clock = clock or Clock()
        self.log = log  # a text file or None
        self.last = None
        self.requests = []  # (monotonic start, wall start, method, url, status, body bytes, headers sent)

    def _request(self, method, url, extra=None):
        if self.last is not None:
            wait = self.last + GAP_S - self.clock.monotonic()
            if wait > 0:
                self.clock.sleep(wait)
        start, wall = self.clock.monotonic(), self.clock.utcnow()
        self.last = start
        headers = {"User-Agent": UA, "Accept": "*/*"}
        headers.update(extra or {})
        try:
            r = self.transport.request(method, url, headers, TIMEOUT_S)
            status, n = str(r.status), r.body_bytes
        except NetError as e:
            r, status, n = e, f"ERR-{e.kind}", 0
        self.requests.append((start, wall, method, url, status, n, headers))
        if self.log:
            self.log.write(f"{iso_ms(wall)}\t{method}\t{url}\t{status}\t{n}\n")
            self.log.flush()
        return r

    def follow(self, method, url, extra=None):
        """(final Response or NetError, final url, chain of (url, status)) following redirects, one request per hop."""
        cur, chain = url.split("#", 1)[0], []
        for _ in range(MAX_HOPS + 1):
            r = self._request(method, cur, extra)
            if isinstance(r, NetError):
                chain.append((cur, f"ERR-{r.kind}"))
                return r, cur, chain
            chain.append((cur, r.status))
            loc = r.headers.get("location")
            if r.status in REDIRECTS and loc:
                cur = urllib.parse.urljoin(cur, urllib.parse.quote(loc.strip(), safe="%/:=&?~#+!$,;'@()*[]")).split("#", 1)[0]
                continue
            return r, cur, chain
        return NetError("redirects", f"more than {MAX_HOPS} redirects"), cur, chain

    def check(self, url):
        """Live facts of one URL: HEAD with redirects; a ranged GET with redirects only when the HEAD's final status is not 2xx."""
        t0 = self.clock.utcnow()
        r, final, chain = self.follow("HEAD", url)
        method = "HEAD"
        if not isinstance(r, NetError) and not 200 <= r.status < 300:
            r, final, chain2 = self.follow("GET", url, {"Range": "bytes=0-0"})
            chain += chain2
            method = "GET"
        facts = {"url": url, "method": method, "final_url": final, "chain": chain, "checked_at_utc": t0.strftime("%Y-%m-%dT%H:%M:%SZ")}
        if isinstance(r, NetError):
            facts.update(error=r.kind, detail=r.detail, status="")
            return facts
        h = r.headers
        length = h.get("content-length", "")
        m = re.match(r"bytes \d+-\d+/(\d+)", h.get("content-range", ""))
        if m:
            length = m.group(1)  # a 206: the full size, not the 1 byte
        facts.update(error=None, status=str(r.status), content_type=h.get("content-type", ""), content_length=length,
                     last_modified=h.get("last-modified", ""), etag=h.get("etag", ""))
        return facts


def is_document(ctype):
    c = (ctype or "").lower()
    return any(d in c for d in DOCUMENT_TYPES) and "html" not in c


def document_path(url):
    """True when the URL's path names a document file (DOCUMENT_EXTS): such a URL must never be served as text/html, baseline or not."""
    return urllib.parse.urlsplit(url.split("#", 1)[0]).path.lower().endswith(DOCUMENT_EXTS)


def classify(facts, base=None):
    """(PASS | WARN | FAIL, [reasons]) for one URL's live facts against its baseline row (or None)."""
    chain = " -> ".join(f"{s}" for _, s in facts["chain"])
    if facts["error"] == "timeout":
        return "WARN", ["timeout: re-run"]
    if facts["error"] in ("dns", "tls", "conn"):
        name = {"dns": "DNS failure", "tls": "TLS failure", "conn": "connection failure"}[facts["error"]]
        return "FAIL", [f"{name}: {facts['detail']}"]
    if facts["error"]:
        return "FAIL", [f"{facts['error']}: {facts['detail']} (chain {chain})"]
    st = int(facts["status"])
    if st in (401, 403, 429):
        return "WARN", [f"status {st} (chain {chain})"]
    if not 200 <= st < 300:
        return "FAIL", [f"status {st}" + (f" after redirects (chain {chain})" if len(facts["chain"]) > 1 else "")]
    html = "text/html" in facts["content_type"].lower()
    if html and document_path(facts["url"]):
        return "FAIL", [f"document URL served as {facts['content_type']} (soft-404 landing page; final {facts['final_url']})"]
    if base is None:
        return "PASS", []
    if is_document(base["content_type"]) and html:
        return "FAIL", [f"content-type flipped from {base['content_type']} to {facts['content_type']} (soft-404 landing page; final {facts['final_url']})"]
    changed = [k for k in ("etag", "content_length", "last_modified") if (base[k] or facts[k]) and base[k] != facts[k]]
    if host_of(base["final_url"] or base["url"]) != host_of(facts["final_url"]):
        changed.append("final_url host")
    if changed:
        return "WARN", [f"source changed: re-hash per PLAN §4 ({', '.join(changed)})"]
    return "PASS", []


# --- modes ------------------------------------------------------------------------------------------------------------------------------
def tsv_cell(v):
    return str(v).replace("\t", " ").replace("\n", " ")


def write_baseline(path, s, results):
    rows = []
    for facts in sorted(results, key=lambda f: f["url"]):
        e = s["urls"][facts["url"]]
        example = (sorted(e["pages"]) or sorted(e["files"]))[0]
        rows.append([facts["url"], len(e["pages"]), example, facts["status"], facts["final_url"], facts["content_type"],
                     facts["content_length"], facts["last_modified"], facts["etag"], facts["checked_at_utc"]])
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write("\t".join(COLUMNS) + "\n")
        for r in rows:
            fh.write("\t".join(tsv_cell(c) for c in r) + "\n")


def report_text(results, verdicts, checker, offline):
    gaps = [b[0] - a[0] for a, b in zip(checker.requests, checker.requests[1:])]
    counts = {k: sum(1 for v in verdicts.values() if v[0] == k) for k in ("PASS", "WARN", "FAIL")}
    lines = ["# /nj/ link check (tools/nj_link_baseline.py)", "",
             f"- URLs checked: {len(results)}; PASS {counts['PASS']}, WARN {counts['WARN']}, FAIL {counts['FAIL']}",
             f"- requests: {len(checker.requests)} (HEAD {sum(1 for r in checker.requests if r[2] == 'HEAD')}, "
             f"GET {sum(1 for r in checker.requests if r[2] == 'GET')}); min gap between request starts: "
             f"{min(gaps):.3f} s" if gaps else f"- requests: {len(checker.requests)}",
             f"- offline problems: {len(offline)}", ""]
    lines += [f"  - {p}" for p in offline]
    lines += ["| class | status | url | final_url | reasons |", "|---|---|---|---|---|"]
    for f in results:
        c, why = verdicts[f["url"]]
        lines.append(f"| {c} | {f['status'] or 'ERR-' + f['error']} | {f['url']} | {f['final_url']} | {'; '.join(why)} |")
    return "\n".join(lines) + "\n"


def main(argv=None, transport=None, clock=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--offline", action="store_true", help="default: scan and compare with the baseline, no network")
    g.add_argument("--live", action="store_true", help="check every URL on the network against the baseline")
    g.add_argument("--write-baseline", action="store_true", help="live check, then rewrite the baseline (refuses on FAIL, non-2xx, timeout)")
    ap.add_argument("--root", default=ROOT, help="site tree to scan (default: this repo)")
    ap.add_argument("--baseline", help=f"baseline TSV (default: ROOT/{BASELINE})")
    ap.add_argument("--log", help="request log file (live modes): one line per request")
    ap.add_argument("--report", help="report file (live modes): markdown")
    a = ap.parse_args(argv)
    root = os.path.abspath(a.root)
    path = a.baseline or os.path.join(root, BASELINE)
    s = scan(root)
    baseline = read_baseline(path)
    shown = os.path.relpath(path, root) if path.startswith(root + os.sep) else path
    for ln in summary_lines(s, baseline, shown):
        print(ln)
    offline = offline_problems(s, baseline)
    if not (a.live or a.write_baseline):
        for p in offline:
            print(p)
        print("offline: FAIL" if offline else "offline: OK")
        return 1 if offline else 0

    urls = sorted(set(s["urls"]) | (set() if a.write_baseline else set(baseline or {})))
    log = open(a.log, "w", encoding="utf-8") if a.log else None
    try:
        checker = Checker(transport, clock, log)
        results = [checker.check(u) for u in urls]
    finally:
        if log:
            log.close()
    verdicts = {f["url"]: classify(f, (baseline or {}).get(f["url"])) for f in results}
    text = report_text(results, verdicts, checker, [] if a.write_baseline else offline)
    if a.report:
        with open(a.report, "w", encoding="utf-8") as fh:
            fh.write(text)
    print("\n".join(text.splitlines()[2:5]))
    for f in results:
        c, why = verdicts[f["url"]]
        if c != "PASS":
            print(f"{c} {f['url']}: {'; '.join(why)}")
    fails = [u for u, v in verdicts.items() if v[0] == "FAIL"]
    timeouts = [f["url"] for f in results if f["error"] == "timeout"]
    if timeouts:
        print(f"{len(timeouts)} timeout(s): re-run")
    if a.write_baseline:
        not2xx = [f["url"] for f in results if not re.fullmatch(r"2\d\d", f["status"] or "")]
        if fails or timeouts or not2xx:
            print(f"refusing to write {shown}: {len(fails)} FAIL, {len(timeouts)} timeout, {len(not2xx)} not 2xx (never baseline a dead link)")
            return 1
        write_baseline(path, s, results)
        print(f"wrote {shown}: {len(results)} rows")
        return 0
    for p in offline:
        print(p)
    if fails:
        print("live: FAIL " + " ".join(fails))
    elif offline:
        print("live: FAIL (offline problems above)")
    else:
        print("live: OK")
    return 1 if fails or offline else 0


if __name__ == "__main__":
    sys.exit(main())
