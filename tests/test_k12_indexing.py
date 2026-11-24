"""K12-INDEXING-001: county hubs, same-county peer links, breadcrumbs, unique titles and the sitemap (tools/nj_indexing.py).

The checks are plain functions over a site tree (`*_problems(root)` -> list of problems), written here independently of the tool (own
regexes, own peer rule, own slug rule), run on the committed tree and on temp copies with one planted fault each (mutation checks).
Base comparisons use web main 7e99b60e (the tree before this ticket) via `git archive`. No network, no data repo.
"""
import collections
import contextlib
import hashlib
import html
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nj_indexing as I  # noqa: E402
import nj_district_summaries as DSTOOL  # noqa: E402
import k12_district_summaries_helpers as DS  # noqa: E402

BASE = "7e99b60ee83a606550ce9e353fef8fcb06047996"  # web main before this ticket
SITE = "https://k12comp.com"
# spec F7 / evidence local-audit-7e99b60e.json: the 11 duplicate-title groups, 24 pages
DUP_PAGES = {
    "nj/fairfield-twp-3405010/index.html", "nj/fairfield-twp-3405040/index.html",
    "nj/franklin-twp-3405430/index.html", "nj/franklin-twp-3405460/index.html", "nj/franklin-twp-3405490/index.html",
    "nj/franklin-twp-3405520/index.html", "nj/greenwich-twp-3406180/index.html", "nj/greenwich-twp-3406210/index.html",
    "nj/hamilton-twp-3406510/index.html", "nj/hamilton-twp-3406540/index.html", "nj/lawrence-twp-3408370/index.html",
    "nj/lawrence-twp-3408400/index.html", "nj/mansfield-twp-3409510/index.html", "nj/mansfield-twp-3409540/index.html",
    "nj/monroe-twp-3410470/index.html", "nj/monroe-twp-3410500/index.html", "nj/ocean-twp-3412060/index.html",
    "nj/ocean-twp-3412090/index.html", "nj/springfield-twp-3415630/index.html", "nj/springfield-twp-3415660/index.html",
    "nj/union-twp-3416440/index.html", "nj/union-twp-3416500/index.html", "nj/washington-twp-3417130/index.html",
    "nj/washington-twp-3417160/index.html"}
NOINDEX = {"404.html", "privacy/index.html", "terms/index.html"}
DISTRICT = re.compile(r"^nj/[a-z0-9-]+-\d{7}/index\.html$")
HUB = re.compile(r"^nj/county/([a-z0-9-]+)/index\.html$")
NJ_ROW = re.compile(r'<tr><th scope="row"><a href="(/nj/[a-z0-9-]+-(\d{7})/)">([^<]*)</a></th><td>([^<]*)</td>(.*?)</tr>', re.S)


# --- tree helpers -------------------------------------------------------------------------------------------------------------------
def rd(root, rel):
    with open(os.path.join(root, *rel.split("/")), encoding="utf-8", newline="") as f:
        return f.read()


def wr(root, rel, text):
    with open(os.path.join(root, *rel.split("/")), "w", encoding="utf-8", newline="") as f:
        f.write(text)


def pages_of(root):
    out = {}
    for dp, dns, fns in os.walk(root):
        rel_dir = os.path.relpath(dp, root).replace(os.sep, "/")
        if rel_dir == ".":
            dns[:] = [d for d in dns if d not in ("docs", "tests", "tools") and not d.startswith((".", "_"))]
        for f in fns:
            if f.endswith(".html"):
                rel = f if rel_dir == "." else f"{rel_dir}/{f}"
                out[rel] = rd(root, rel)
    return out


def url(rel):
    if rel == "index.html":
        return SITE + "/"
    return SITE + "/" + (rel[:-len("index.html")] if rel.endswith("/index.html") else rel)


def noindex(page):
    return any("noindex" in c for c in re.findall(r'<meta name="robots" content="([^"]*)"', page))


def indexable(rel, page):
    return not noindex(page) and re.findall(r'<link rel="canonical" href="([^"]*)"', page) == [url(rel)]


def title(page):
    m = re.findall(r"<title>([^<]*)</title>", page)
    return html.unescape(m[0]) if len(m) == 1 else None


def main_of(page):
    return page[page.index('<main id="main">'):page.index("</main>") + len("</main>")]


def nj_rows(page):
    """[(path, leaid, name_html, county, row_html)] from the /nj/ table, in table order."""
    body = page[page.index("<tbody>"):page.index("</tbody>")]
    return [(m.group(1), m.group(2), m.group(3), html.unescape(m.group(4)), m.group(0)) for m in NJ_ROW.finditer(body)]


def slug(county):
    """Independent slug rule: drop " County", lowercase, spaces -> "-"."""
    s = county[:-7].lower().replace(" ", "-")
    assert re.fullmatch(r"[a-z0-9-]+", s), s
    return s


def hrefs(page):
    return re.findall(r'<a\b[^>]*\bhref="([^"]*)"', page)


def internal(href):
    if href.startswith(SITE + "/"):
        href = href[len(SITE):]
    if not href.startswith("/") or href.startswith("//"):
        return None
    href = href.split("#")[0].split("?")[0]
    if href.endswith("/index.html"):
        href = href[:-len("index.html")]
    return SITE + href


def ld_blocks(page):
    return re.findall(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', page, re.S)


def base_tree(dest, paths=("*.html", "sitemap.xml", "robots.txt")):
    tar = subprocess.run(["git", "-C", ROOT, "archive", BASE, "--", *paths], capture_output=True, check=True).stdout
    subprocess.run(["tar", "-x", "-C", dest], input=tar, check=True)


def copy_site(dest):
    """The parts of the committed tree the tool reads and writes: every published HTML page, sitemap.xml, robots.txt."""
    for rel in pages_of(ROOT):
        os.makedirs(os.path.dirname(os.path.join(dest, *rel.split("/"))), exist_ok=True)
        shutil.copyfile(os.path.join(ROOT, *rel.split("/")), os.path.join(dest, *rel.split("/")))
    for f in ("sitemap.xml", "robots.txt"):
        shutil.copyfile(os.path.join(ROOT, f), os.path.join(dest, f))


def run_tool(*argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        rc = I.main(list(argv))
    return rc, out.getvalue()


def sha_tree(root):
    out = {}
    for dp, _, fns in os.walk(root):
        for f in fns:
            p = os.path.join(dp, f)
            with open(p, "rb") as fh:
                out[os.path.relpath(p, root)] = hashlib.sha256(fh.read()).hexdigest()
    return out


# --- independent checks (each returns a list of problems) -----------------------------------------------------------------------
def hub_problems(root):
    """ACs 3-5: the hub set, rows cell for cell, links to every district, no new numbers, no text beyond the template."""
    pages = pages_of(root)
    nj = pages["nj/index.html"]
    rows = nj_rows(nj)
    by_county = collections.defaultdict(list)
    for r in rows:
        by_county[r[3]].append(r)
    want = {slug(c): c for c in by_county}
    have = {HUB.match(r).group(1) for r in pages if HUB.match(r)}
    bad = []
    if have != set(want):
        bad.append(("hub set", sorted(have ^ set(want))))
    disclaimer = re.search(r'<p class="disclaimer">.*?</p>', main_of(nj)).group(0)
    for s, county in sorted(want.items()):
        rel = f"nj/county/{s}/index.html"
        if rel not in pages:
            continue
        p, n = pages[rel], len(by_county[county])
        m = main_of(p)
        hub_rows = nj_rows(m)
        if [r[4] for r in hub_rows] != [r[4] for r in by_county[county]]:
            bad.append((rel, "rows differ from /nj/"))
        linked = {internal(h) for h in hrefs(m)}
        if not {SITE + r[0] for r in by_county[county]} <= linked:
            bad.append((rel, "a district is not linked"))
        # no new numbers: every digit run outside the table is the district count
        table = re.search(r"<table.*?</table>", m, re.S)
        rest = m[:table.start()] + m[table.end():] if table else m
        if re.findall(r"\d[\d,]*", re.sub(r"<[^>]+>", " ", rest)) != [str(n)]:
            bad.append((rel, "a number other than the district count outside the table"))
        tokens = set(re.findall(r"\$?\d[\d.,-]*", re.sub(r"<[^>]+>", " ", table.group(0)))) if table else set()
        allowed = set(re.findall(r"\$?\d[\d.,-]*", re.sub(r"<[^>]+>", " ", "".join(r[4] for r in by_county[county]))))
        if not tokens <= allowed:
            bad.append((rel, "a number in the table that is not in the county's /nj/ rows", sorted(tokens - allowed)[:3]))
        # the whole text outside the table is the template: breadcrumb, h1, intro, disclaimer, back link (so no name can be there)
        c = html.escape(county)
        skeleton = (f'<main id="main"><nav aria-label="Breadcrumb" class="crumbs"><a href="/nj/">New Jersey</a> / <span aria-current="page">{c}</span></nav>'
                    f'<h1>{c} superintendent salaries</h1><p class="sub">Latest superintendent base salary for the {n} districts in {c}, as reported to NJDOE.</p>\n'
                    f'{disclaimer}\n<div class="table-wrap" tabindex="0" role="region" aria-label="{c} districts"><table id="districts">'
                    f'<caption>{c} districts</caption>')
        if not m.startswith(skeleton) or not m.endswith('</tbody></table></div>\n<p><a href="/nj/">All New Jersey districts</a></p>\n</main>'):
            bad.append((rel, "hub main is not the template"))
        if not 11 <= n <= 76:
            bad.append((rel, "county size out of the measured range", n))
    if sum(len(v) for v in by_county.values()) != 586 or len(want) != 21:
        bad.append(("counts", len(want), sum(len(v) for v in by_county.values())))
    return bad


def expected_peers(rows):
    """Independent ±4 wrap rule: {leaid: [peer paths]} (sort by display name, casefolded, then LEAID)."""
    out = {}
    by_county = collections.defaultdict(list)
    for r in rows:
        by_county[r[3]].append(r)
    for rs in by_county.values():
        rs = sorted(rs, key=lambda r: (html.unescape(r[2]).casefold(), html.unescape(r[2]), r[1]))
        n = len(rs)
        for i, r in enumerate(rs):
            if n <= 9:
                out[r[1]] = [x[0] for x in rs if x is not r]
            else:
                out[r[1]] = [rs[(i + k) % n][0] for k in (-4, -3, -2, -1, 1, 2, 3, 4)]
    return out


def peer_problems(root):
    """AC 6: each district links its hub and exactly the 8 peers of the rule, names only, no salary."""
    nj = rd(root, "nj/index.html")
    rows = nj_rows(nj)
    peers = expected_peers(rows)
    bad = []
    for path, leaid, name_html, county, _ in rows:
        p = rd(root, path.strip("/") + "/index.html")
        sec = re.findall(r'<section class="peers" aria-labelledby="peers"><h2 id="peers">([^<]*)</h2><ul class="guides">(.*?)</ul></section>', p)
        if len(sec) != 1:
            bad.append((path, "no single peer block"))
            continue
        h2, ul = sec[0]
        links = re.findall(r'<li><a href="([^"]*)">([^<]*)</a></li>', ul)
        if html.unescape(h2) != f"Other districts in {county}":
            bad.append((path, "peer heading", h2))
        if [h for h, _ in links] != peers[leaid] or len(set(h for h, _ in links)) != 8 or "".join(
                f'<li><a href="{h}">{t}</a></li>' for h, t in links) != ul:
            bad.append((path, "peers differ from the rule"))
        names = {r[0]: r[2] for r in rows}
        if any(names.get(h) != t for h, t in links) or "$" in ul:
            bad.append((path, "peer link text is not the district name"))
        if f'<a href="/nj/county/{slug(county)}/">' not in p:
            bad.append((path, "no hub link"))
    return bad


def graph(pages):
    """{target url: set of linking page urls (self excluded)} and the BFS depth from / of every reachable page. As in a crawl from /, only
    pages reachable from / count as linking pages (the unlinked /api/v1/nj/ index does not)."""
    inl = collections.defaultdict(set)
    out = {}
    for rel, p in pages.items():
        if indexable(rel, p):
            out[url(rel)] = {t for t in (internal(h) for h in hrefs(p)) if t and t != url(rel)}
    depth, frontier = {SITE + "/": 0}, [SITE + "/"]
    while frontier:
        nxt = []
        for u in frontier:
            for t in sorted(out.get(u, ())):
                if t not in depth:
                    depth[t] = depth[u] + 1
                    nxt.append(t)
        frontier = nxt
    for u in depth:
        for t in out.get(u, ()):
            inl[t].add(u)
    return inl, depth


def sitemap_urls(root):
    tree = ET.parse(os.path.join(root, "sitemap.xml"))
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    return [(u.find("s:loc", ns).text, u.find("s:lastmod", ns).text) for u in tree.getroot().findall("s:url", ns)]


def graph_problems(root):
    """ACs 7-9: >= 10 linking pages per district, >= 2 per hub, depth <= 2 for every sitemap URL (hubs at 1), / and /nj/ link all hubs."""
    pages = pages_of(root)
    inl, depth = graph(pages)
    bad = []
    hubs = {url(r) for r in pages if HUB.match(r)}
    for rel in pages:
        if DISTRICT.match(rel) and len(inl[url(rel)]) < 10:
            bad.append((rel, "inlinks", len(inl[url(rel)])))
    for h in hubs:
        if len(inl[h]) < 2:
            bad.append((h, "hub inlinks", len(inl[h])))
        if depth.get(h) != 1:
            bad.append((h, "hub depth", depth.get(h)))
    for u, _ in sitemap_urls(root):
        if depth.get(u, 99) > 2:
            bad.append((u, "depth", depth.get(u)))
    for rel in ("index.html", "nj/index.html"):
        linked = {internal(h) for h in hrefs(pages[rel])}
        if not hubs <= linked or len(hubs) != 21:
            bad.append((rel, "does not link all 21 hubs"))
    return bad


def breadcrumb_problems(root):
    """AC 10 (BreadcrumbList part): valid JSON, a BreadcrumbList whose items equal the visible breadcrumb (links + the current page)."""
    bad = []
    for rel, p in pages_of(root).items():
        if not (DISTRICT.match(rel) or HUB.match(rel)):
            continue
        lds = [json.loads(b) for b in ld_blocks(p)]
        crumbs = [d for d in lds if d.get("@type") == "BreadcrumbList"]
        nav = re.findall(r'<nav aria-label="Breadcrumb" class="crumbs">(.*?)</nav>', p)
        if len(crumbs) != 1 or len(nav) != 1:
            bad.append((rel, "breadcrumb count"))
            continue
        visible = [(html.unescape(t), SITE + h) for h, t in re.findall(r'<a href="([^"]*)">([^<]*)</a>', nav[0])]
        cur = re.findall(r'<span aria-current="page">([^<]*)</span>', nav[0])
        visible.append((html.unescape(cur[0]) if cur else None, url(rel)))
        items = crumbs[0].get("itemListElement", [])
        got = [(i.get("name"), i.get("item")) for i in items]
        if got != visible or [i.get("position") for i in items] != list(range(1, len(items) + 1)) or crumbs[0].get("@context") != "https://schema.org":
            bad.append((rel, "BreadcrumbList != visible breadcrumb", got, visible))
        if visible[0] != ("New Jersey", SITE + "/nj/") or len(visible) != (3 if DISTRICT.match(rel) else 2):
            bad.append((rel, "breadcrumb shape", visible))
        if DISTRICT.match(rel) and not re.fullmatch(r"https://k12comp\.com/nj/county/[a-z0-9-]+/", visible[1][1]):
            bad.append((rel, "middle crumb is not a hub"))
    return bad


def title_problems(root):
    """ACs 11-13: unique titles and descriptions on indexable pages, one self-canonical each."""
    bad = []
    pages = {r: p for r, p in pages_of(root).items()}
    idx = {r: p for r, p in pages.items() if r not in NOINDEX}
    for r, p in idx.items():
        if not indexable(r, p):
            bad.append((r, "not one self-canonical"))
    ts = collections.Counter(title(p) for r, p in idx.items())
    bad += [("duplicate title", t) for t, n in ts.items() if n > 1 or not t]
    ds = collections.Counter((re.findall(r'<meta name="description" content="([^"]*)">', p) or [""])[0] for p in idx.values())
    bad += [("duplicate or empty description", d) for d, n in ds.items() if n > 1 or not d.strip()]
    return bad


def sitemap_problems(root):
    """AC 14: the sitemap is exactly the indexable HTML pages (api/ excluded, OQ-9), valid XML, with /nj/history/."""
    pages = pages_of(root)
    want = {url(r) for r, p in pages.items() if indexable(r, p) and not r.startswith("api/")}
    got = sitemap_urls(root)
    bad = []
    if len(got) != len({u for u, _ in got}):
        bad.append("duplicate URL")
    if {u for u, _ in got} != want:
        bad.append(("sitemap != indexable set", sorted({u for u, _ in got} ^ want)[:5]))
    if SITE + "/nj/history/" not in {u for u, _ in got}:
        bad.append("no /nj/history/")
    if not all(re.fullmatch(r"\d{4}-\d\d-\d\d", d or "") for _, d in got):
        bad.append("lastmod format")
    return bad


class Committed(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._base = tempfile.TemporaryDirectory(prefix="k12idx-base-")
        cls.addClassCleanup(cls._base.cleanup)
        cls.base = cls._base.name
        base_tree(cls.base)
        cls.pages = pages_of(ROOT)
        cls.base_pages = pages_of(cls.base)

    # AC 2 (on the committed tree) and the tool's own check
    def test_tool_check_passes_on_the_committed_tree(self):
        rc, out = run_tool(ROOT, "--check")
        self.assertEqual(rc, 0, out)
        self.assertIn("21 county hubs, 586 districts, 24 disambiguated titles, 611 sitemap URLs; 0 files stale", out)
        self.assertEqual(I.RELEASE_DATE, "2026-11-24")

    # AC 3-5
    def test_hubs(self):
        self.assertEqual(hub_problems(ROOT), [])
        hubs = sorted(r for r in self.pages if HUB.match(r))
        self.assertEqual(len(hubs), 21)
        self.assertIn("nj/county/cape-may/index.html", hubs)
        rows = nj_rows(self.pages["nj/index.html"])
        sizes = collections.Counter(r[3] for r in rows)
        self.assertEqual((min(sizes.values()), max(sizes.values()), sum(sizes.values())), (11, 76, 586))
        self.assertEqual((sizes["Mercer County"], sizes["Bergen County"]), (11, 76))
        # FTE badges copy into hub rows unchanged
        fte = sum(len(re.findall(r'<td class="num">\$[\d,]+ <span class="badge">', r[4])) for r in rows)
        self.assertGreater(fte, 0)
        self.assertEqual(sum(len(re.findall(r'<td class="num">\$[\d,]+ <span class="badge">', p)) for r, p in self.pages.items() if HUB.match(r)), fte)

    def test_hubs_carry_no_person_or_ufb_field_text(self):
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from test_nj_history_privacy import FORBIDDEN  # the existing no-names / no-UFB guard
        # the role word "superintendent" is the hub's subject (h1, title), as on /nj/; every other forbidden token still applies
        guard = re.compile(FORBIDDEN.pattern.replace("|superintendent", ""), re.I)
        self.assertNotEqual(guard.pattern, FORBIDDEN.pattern)
        for r, p in self.pages.items():
            if HUB.match(r):
                self.assertIsNone(guard.search(p), r)
                self.assertNotIn("Plantedname", p)

    def test_planted_name_in_the_api_json_never_reaches_a_hub(self):
        with tempfile.TemporaryDirectory(prefix="k12idx-canary-") as d:
            copy_site(d)
            shutil.copytree(os.path.join(ROOT, "api"), os.path.join(d, "api"), dirs_exist_ok=True)
            for f in os.listdir(os.path.join(d, "api", "v1", "nj")):
                if f.endswith(".json") and f[0].isdigit():
                    p = os.path.join(d, "api", "v1", "nj", f)
                    with open(p, encoding="utf-8") as fh:
                        doc = json.load(fh)
                    for c in doc["superintendent_contracts"]:
                        c["person_name"] = "Jane Plantedname"
                    with open(p, "w", encoding="utf-8") as fh:
                        json.dump(doc, fh)
            self.assertEqual(run_tool(d, "--write")[0], 0)
            for rel, p in pages_of(d).items():
                if not rel.startswith("api/"):
                    self.assertNotIn("Plantedname", p, rel)

    # AC 6
    def test_peers(self):
        self.assertEqual(peer_problems(ROOT), [])
        rows = nj_rows(self.pages["nj/index.html"])
        peers = expected_peers(rows)
        self.assertEqual(len(peers), 586)
        self.assertTrue(all(len(v) == 8 and len(set(v)) == 8 for v in peers.values()))
        # Mercer (11 districts) still gives 8 distinct peers; no county has 9 or fewer
        self.assertGreater(min(collections.Counter(r[3] for r in rows).values()), 9)

    # AC 7-9
    def test_link_graph(self):
        self.assertEqual(graph_problems(ROOT), [])
        inl, depth = graph(self.pages)
        d = [len(inl[url(r)]) for r in self.pages if DISTRICT.match(r)]
        h = [len(inl[url(r)]) for r in self.pages if HUB.match(r)]
        self.assertEqual((len(d), len(h)), (586, 21))
        self.assertGreaterEqual(min(d), 10)
        self.assertGreaterEqual(min(h), 2)
        self.assertLessEqual(max(depth[u] for u, _ in sitemap_urls(ROOT)), 2)

    # AC 10
    def test_breadcrumbs_and_dataset_blocks(self):
        self.assertEqual(breadcrumb_problems(ROOT), [])
        for rel, p in self.pages.items():
            if DISTRICT.match(rel):
                b = self.base_pages[rel]
                self.assertNotIn("BreadcrumbList", b)
                self.assertEqual([x for x in ld_blocks(p) if '"BreadcrumbList"' not in x], ld_blocks(b), rel)
                self.assertEqual(len(ld_blocks(p)), len(ld_blocks(b)) + 1, rel)

    # AC 11-13
    def test_titles_descriptions_canonicals(self):
        self.assertEqual(title_problems(ROOT), [])
        # the base's duplicate groups are exactly the 24 pages of the evidence
        bidx = {r: p for r, p in self.base_pages.items() if indexable(r, p)}
        c = collections.Counter(title(p) for p in bidx.values())
        self.assertEqual({r for r, p in bidx.items() if c[title(p)] > 1}, DUP_PAGES)
        self.assertEqual(len({title(self.base_pages[r]) for r in DUP_PAGES}), 11)
        changed = {r for r in self.base_pages if r in self.pages and title(self.pages[r]) != title(self.base_pages[r])}
        self.assertEqual(changed, DUP_PAGES)
        rows = {r[0].strip("/") + "/index.html": r for r in nj_rows(self.pages["nj/index.html"])}
        for r in DUP_PAGES:
            t, county = title(self.pages[r]), rows[r][3]
            self.assertIn(f"({county[:-7]} Co) superintendent salary", t)
            self.assertTrue(t.startswith(html.unescape(rows[r][2]) + " ("), t)
            self.assertLess(len(t), 60 + len(" | K12 Comp"))
            if t.endswith(" | K12 Comp"):
                self.assertLess(len(t), 60)
            else:
                self.assertGreaterEqual(len(t + " | K12 Comp"), 60)
            self.assertEqual(re.findall(r'<meta property="og:title" content="([^"]*)">', self.pages[r]), [html.escape(t)])
        self.assertEqual(title(self.pages["nj/franklin-twp-3405490/index.html"]), "Franklin Twp (Somerset Co) superintendent salary, 2026-27")
        # noindex pages unchanged
        for r in NOINDEX:
            self.assertEqual(self.pages[r], self.base_pages[r], r)
        self.assertEqual({r for r, p in self.pages.items() if noindex(p)}, NOINDEX)

    # AC 14-15
    def test_sitemap_and_robots(self):
        self.assertEqual(sitemap_problems(ROOT), [])
        got = sitemap_urls(ROOT)
        self.assertEqual(len(got), 611)
        old = dict(sitemap_urls(self.base))
        self.assertEqual(len(old), 590)
        self.assertEqual(set(old) | {url(r) for r in self.pages if HUB.match(r)}, {u for u, _ in got})
        # lastmod (OQ-6): hubs, districts, / and /nj/ RELEASE_DATE (no on-page Updated date is later); every other page keeps its value
        for u, d in got:
            rel = (u[len(SITE) + 1:] or "") + "index.html"
            if HUB.match(rel) or DISTRICT.match(rel) or rel in ("index.html", "nj/index.html"):
                self.assertEqual(d, "2026-11-24", u)
            else:
                self.assertEqual(d, old[u], u)
        self.assertEqual([u for u, _ in got][-1], SITE + "/nj/history/")
        with open(os.path.join(ROOT, "robots.txt"), "rb") as a, open(os.path.join(self.base, "robots.txt"), "rb") as b:
            self.assertEqual(a.read(), b.read())
        import nj_history_release_guard as RG
        from nj_history import data as D
        RG.check_output(ROOT, D.load_lock())
        self.assertFalse(any(re.search(r"x-robots-tag", p, re.I) for p in self.pages.values()))

    # AC 16
    def test_district_main_is_unchanged_apart_from_breadcrumb_and_peers(self):
        n = 0
        for rel, p in self.pages.items():
            if not DISTRICT.match(rel):
                continue
            m = main_of(p)
            m = re.sub(r'<section class="peers" aria-labelledby="peers">.*?</section>', "", m)
            m = DS.strip(m)  # K12-DISTRICT-SUMMARIES-001's paragraph (tests/test_k12_district_summaries.py checks it)
            m = re.sub(r'<a href="/nj/">New Jersey</a> / <a href="/nj/county/[a-z0-9-]+/">[^<]*</a> / ', '<a href="/nj/">Districts</a> / ', m)
            self.assertEqual(m, main_of(self.base_pages[rel]), rel)
            # and everything outside <main> except the head's title/og:title/BreadcrumbList
            out = lambda s: re.sub(r'<script type="application/ld\+json" id="ld-breadcrumb">.*?</script>|<title>[^<]*</title>|<meta property="og:title" content="[^"]*">',  # noqa: E731
                                   "", s.replace(main_of(s), ""))
            self.assertEqual(out(p), out(self.base_pages[rel]), rel)
            n += 1
        self.assertEqual(n, 586)
        # / and /nj/: only the "By county" list and the /nj/ h1
        for rel in ("index.html", "nj/index.html"):
            s = re.sub(r'<section(?: class="section")? aria-labelledby="by-county">.*?</section>\n', "", self.pages[rel])
            s = s.replace("<h1>New Jersey superintendent salaries, 586 districts</h1>", "<h1>New Jersey districts (586)</h1>")
            self.assertEqual(s, self.base_pages[rel], rel)

    def test_no_data_chart_api_or_config_file_changes(self):
        out = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", BASE, "--", "charts", "api", "data", "robots.txt", ".github",
                              "_config.yml", "llms.txt"], capture_output=True, check=True, text=True).stdout
        self.assertEqual(out, "")
        # K12-DISTRICT-SUMMARIES-001: style.css gains exactly the one summary rule (pinned in tests/test_k12_district_summaries.py), nothing else
        css = subprocess.run(["git", "-C", ROOT, "diff", "-U0", BASE, "--", "style.css"], capture_output=True, check=True, text=True).stdout
        body = [ln for ln in css.splitlines() if ln[:1] in "+-" and not ln.startswith(("+++", "---"))]
        self.assertEqual(body, ["+.district-summary{max-width:60ch;text-wrap:pretty}.district-summary .nw{white-space:nowrap}"])

    # AC 22
    def test_docs_name_the_tool_and_the_rules(self):
        with open(os.path.join(ROOT, "docs", "nj-indexing.md"), encoding="utf-8") as f:
            doc = f.read()
        for s in ("tools/nj_indexing.py", "8", "4 alphabetically previous", "4 next", "wrap", "RELEASE_DATE", "nj_fte_marks",
                  "sitemap", "cape-may", "(Somerset Co)"):
            self.assertIn(s, doc)
        with open(os.path.join(ROOT, "docs", "nj-history.md"), encoding="utf-8") as f:
            self.assertIn("nj_indexing", f.read())


class ScratchTree(unittest.TestCase):
    """AC 2 and the mutation checks, on temp copies of the committed tree."""

    def setUp(self):
        self._d = tempfile.TemporaryDirectory(prefix="k12idx-")
        self.addCleanup(self._d.cleanup)
        self.d = self._d.name
        copy_site(self.d)

    def test_idempotent_double_write(self):
        first = sha_tree(self.d)
        self.assertEqual(run_tool(self.d, "--write")[0], 0)
        self.assertEqual(sha_tree(self.d), first)  # the committed tree is already the final form
        self.assertEqual(run_tool(self.d)[0], 0)  # the default mode writes
        self.assertEqual(sha_tree(self.d), first)

    def test_rebuild_from_base_pages_twice(self):
        """From the pre-ticket pages (7e99b60e) the tool writes the committed bytes, and a second run changes nothing."""
        with tempfile.TemporaryDirectory(prefix="k12idx-b-") as b:
            base_tree(b)
            # K12-DISTRICT-SUMMARIES-001 runs before this tool: the committed pages carry its paragraph (built here from the committed api/ and data/)
            shutil.copytree(os.path.join(ROOT, "api", "v1", "nj"), os.path.join(b, "api", "v1", "nj"), dirs_exist_ok=True)
            shutil.copytree(os.path.join(ROOT, "data", "nj", "history"), os.path.join(b, "data", "nj", "history"), dirs_exist_ok=True)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(DSTOOL.main([b, "--write"]), 0)
            self.assertEqual(run_tool(b, "--check")[0], 1)
            self.assertEqual(run_tool(b, "--write")[0], 0)
            once = {k: v for k, v in sha_tree(b).items() if k in sha_tree(self.d)}  # minus the api/ and data/ files only the summaries step read
            self.assertEqual(run_tool(b, "--write")[0], 0)
            self.assertEqual({k: v for k, v in sha_tree(b).items() if k in once}, once)
            self.assertEqual(once, sha_tree(self.d))

    def mutate(self, rel, old, new):
        p = rd(self.d, rel)
        self.assertIn(old, p)
        wr(self.d, rel, p.replace(old, new, 1))

    def test_mutation_dropped_peer_link(self):
        rel = "nj/vineland-city-3416800/index.html"
        li = re.search(r'<section class="peers".*?(<li>.*?</li>)', rd(self.d, rel)).group(1)
        self.mutate(rel, li, "")
        self.assertTrue(peer_problems(self.d))
        self.assertEqual(run_tool(self.d, "--check")[0], 1)

    def test_mutation_hub_row_changed(self):
        rel = "nj/county/cumberland/index.html"
        self.mutate(rel, "$263,750", "$263,751")
        self.assertTrue(hub_problems(self.d))
        self.assertEqual(run_tool(self.d, "--check")[0], 1)
        self.mutate(rel, "$263,751", "$263,750")
        self.assertEqual(hub_problems(self.d), [])
        # a dropped hub
        os.remove(os.path.join(self.d, "nj", "county", "cumberland", "index.html"))
        self.assertTrue(hub_problems(self.d))
        self.assertTrue(graph_problems(self.d))
        self.assertEqual(run_tool(self.d, "--check")[0], 1)

    def test_mutation_title_collision(self):
        rel = "nj/franklin-twp-3405520/index.html"
        p = rd(self.d, rel)
        other = title(rd(self.d, "nj/franklin-twp-3405430/index.html"))
        p = re.sub(r"<title>[^<]*</title>", f"<title>{html.escape(other)}</title>", p, count=1)
        wr(self.d, rel, re.sub(r'<meta property="og:title" content="[^"]*">', f'<meta property="og:title" content="{html.escape(other)}">', p, count=1))
        self.assertTrue(title_problems(self.d))
        self.assertEqual(run_tool(self.d, "--check")[0], 1)

    def test_mutation_sitemap_url_removed(self):
        line = "<url><loc>https://k12comp.com/nj/county/salem/</loc><lastmod>2026-11-24</lastmod></url>\n"
        self.mutate("sitemap.xml", line, "")
        self.assertTrue(sitemap_problems(self.d))
        self.assertEqual(run_tool(self.d, "--check")[0], 1)

    def test_mutation_breadcrumb_and_depth(self):
        rel = "nj/vineland-city-3416800/index.html"
        self.mutate(rel, '"name": "Cumberland County"', '"name": "Salem County"')
        self.assertTrue(breadcrumb_problems(self.d))
        self.mutate(rel, '"name": "Salem County"', '"name": "Cumberland County"')
        self.assertEqual(breadcrumb_problems(self.d), [])
        # take the county list off the home page: hubs fall to depth 2 and / no longer links them
        p = rd(self.d, "index.html")
        wr(self.d, "index.html", re.sub(r'<section class="section" aria-labelledby="by-county">.*?</section>\n', "", p))
        self.assertTrue(graph_problems(self.d))
        self.assertEqual(run_tool(self.d, "--check")[0], 1)

    def test_mutation_noindex_page_leaves_the_sitemap(self):
        rel = "about/index.html"
        self.mutate(rel, "<head>", '<head><meta name="robots" content="noindex">')
        self.assertTrue(sitemap_problems(self.d))  # still listed
        self.assertEqual(run_tool(self.d, "--write")[0], 0)
        self.assertEqual(sitemap_problems(self.d), [])
        self.assertNotIn(SITE + "/about/", dict(sitemap_urls(self.d)))


class Rules(unittest.TestCase):
    def test_slug_rule(self):
        self.assertEqual(I.county_slug("Cape May County"), "cape-may")
        self.assertEqual(I.county_slug("Atlantic County"), "atlantic")
        with self.assertRaises(I.IndexingError):
            I.county_slug("Cañon County")

    def test_peer_rule_small_county_and_wrap(self):
        rows = list(range(11))
        self.assertEqual(I.peers_of(rows, 0), [7, 8, 9, 10, 1, 2, 3, 4])
        self.assertEqual(I.peers_of(rows, 10), [6, 7, 8, 9, 0, 1, 2, 3])
        self.assertEqual(I.peers_of(list(range(5)), 2), [3, 4, 0, 1])

    def test_title_rule(self):
        self.assertEqual(I.dup_title("Franklin Twp superintendent salary, 2026-27 | K12 Comp", "Franklin Twp", "Somerset County"),
                         "Franklin Twp (Somerset Co) superintendent salary, 2026-27")
        # under 60 characters the suffix stays (no district title is that short today; the rule is seo_postbuild's)
        self.assertEqual(I.dup_title("Ada Twp superintendent salary | K12 Comp", "Ada Twp", "Ocean County"),
                         "Ada Twp (Ocean Co) superintendent salary | K12 Comp")
        self.assertEqual(I.base_title("Ada Twp (Ocean Co) superintendent salary"), "Ada Twp superintendent salary | K12 Comp")
        for t in ("Franklin Twp (Somerset Co) superintendent salary, 2026-27", "Ocean Twp (Ocean Co) superintendent salary, 2026-27"):
            self.assertNotIn(" Co)", I.base_title(t))
            self.assertTrue(I.base_title(t).endswith(" | K12 Comp"))

    def test_escaping(self):
        self.assertEqual(I.by_county_section.__name__, "by_county_section")
        page = ('<html><head><title>x</title></head><body><main id="main"><table><tbody>'
                '<tr><th scope="row"><a href="/nj/a-b-1234567/">A &amp; B&#x27;s</a></th><td>Cape May County</td><td>1</td></tr></tbody></table></main></body></html>')
        m = I.Model(page, {})
        self.assertEqual(m.rows[0].name, "A & B's")
        self.assertEqual(I.breadcrumb_ld([("A & B's", "https://k12comp.com/x/")]).count("A & B's"), 1)


if __name__ == "__main__":
    unittest.main()
