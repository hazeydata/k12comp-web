#!/usr/bin/env python3
"""K12-INDEXING-001: county hubs, same-county peer links, breadcrumbs, unique titles and the sitemap (stdlib only). See docs/nj-indexing.md.

Run last, after the history build and every existing rewrite (nj_api_index -> nj_guide_tables -> nj_fte_marks -> nj_mobile_chart_fit ->
nj_chart_label_edge). It reads the site tree and writes, in place:
  - nj/county/<slug>/index.html, one hub per county in the /nj/ table (21): breadcrumb "New Jersey / <County>", one h1, one intro line whose only
    number is the county's district count, that county's /nj/ rows copied byte for byte and in /nj/ order (FTE badges included), a link back to
    /nj/, a self-canonical, its own title and description, BreadcrumbList JSON-LD. Slug = the county name without " County", lowercased,
    runs of anything but a-z0-9 -> "-" (ASCII only: "Cape May County" -> "cape-may");
  - every district page nj/<slug>-<leaid>/index.html: the breadcrumb "Districts / <District>" becomes "New Jersey / <County> / <District>"
    (links /nj/ and the hub) plus a BreadcrumbList JSON-LD block (id="ld-breadcrumb"; the Dataset blocks are not touched), and a peer block
    "Other districts in <County>" before </main> with 8 name-only links: the 4 alphabetically previous and the 4 next districts of the same
    county, wrapping around the county's list (sorted by display name, casefolded, then LEAID). A county with 9 or fewer districts would list
    all the others (none today);
  - the title (and og:title, which mirrors it) of every district page whose title is shared with another indexable page gets the county:
    "Franklin Twp (Somerset Co) superintendent salary, 2026-27", with " | K12 Comp" kept only while the title stays under 60 characters (the
    rule in tools/seo_postbuild.py). Every other title is unchanged;
  - / and /nj/: a "By county" list linking all hubs; the /nj/ h1 becomes "New Jersey superintendent salaries, <N> districts" (N = table rows).
    The County cells of the /nj/ table are not linked;
  - sitemap.xml, regenerated from the tree: every indexable HTML page (no robots noindex, exactly one canonical, pointing at itself) except
    api/ (OQ-9), sorted by file path with /nj/history/ last (where the history build appends it). lastmod: hubs RELEASE_DATE; pages this tool
    rewrites (districts, /, /nj/) max(the page's "Updated" date, RELEASE_DATE); every other page keeps its current lastmod.

Each file is first stripped of this tool's markup, then rewritten, so a second run changes no byte, and `--check` (exit 1) catches any file not in
its final form. Nothing else on a page changes: no salary, source, sha256 line, chart, api/ or data/ file is read for content or written.

    python3 tools/nj_indexing.py [site] --check   # exit 1 if any owned file is stale (site defaults to the repo root)
    python3 tools/nj_indexing.py [site] --write   # the default when neither flag is given
"""
import argparse
import html
import json
import os
import re
import sys

RELEASE_DATE = "2026-11-16"
SITE = "https://k12comp.com"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PEERS_EACH_SIDE = 4
TITLE_SUFFIX = " | K12 Comp"
TITLE_LIMIT = 60  # a title at or over this length drops TITLE_SUFFIX (tools/seo_postbuild.py)
SKIP_TOP = {"docs", "tests", "tools", "node_modules", "vendor"}  # Jekyll excludes (_config.yml); dot dirs are skipped too
HISTORY = "nj/history/index.html"

# --- copy: the one place the new visible strings live (writing review: Lindsay) -------------------------------------------------------
NJ_H1 = "New Jersey superintendent salaries, {n} districts"
NJ_H1_OLD = "New Jersey districts ({n})"  # what the build writes
BY_COUNTY_H2 = "By county"
PEERS_H2 = "Other districts in {county}"
CRUMB_ROOT = "New Jersey"
CRUMB_OLD = "Districts"  # the build's breadcrumb label
HUB_TITLE = "{county}, NJ superintendent salaries"
HUB_DESC = "Latest superintendent base salary for the {n} school districts in {county}, New Jersey, each linked to its source document."
HUB_H1 = "{county} superintendent salaries"
HUB_INTRO = "Latest superintendent base salary for the {n} districts in {county}, as reported to NJDOE."
HUB_CAPTION = "{county} districts"
HUB_BACK = "All New Jersey districts"
DUP_TITLE = "{name} ({short} Co) superintendent salary{year}"

# --- markup -------------------------------------------------------------------------------------------------------------------------
ROW = re.compile(r'<tr><th scope="row"><a href="/nj/(?P<slug>[a-z0-9-]+-(?P<leaid>\d{7}))/">(?P<name>[^<]*)</a></th>'
                 r'<td>(?P<county>[^<]*)</td>.*?</tr>', re.S)
CRUMB_NEW = re.compile(r'<nav aria-label="Breadcrumb" class="crumbs"><a href="/nj/">' + re.escape(CRUMB_ROOT)
                       + r'</a> / <a href="/nj/county/[a-z0-9-]+/">[^<]*</a> / <span aria-current="page">')
CRUMB_OLD_HTML = f'<nav aria-label="Breadcrumb" class="crumbs"><a href="/nj/">{CRUMB_OLD}</a> / <span aria-current="page">'
LD_CRUMB = re.compile(r'<script type="application/ld\+json" id="ld-breadcrumb">.*?</script>', re.S)
PEERS = re.compile(r'<section class="peers" aria-labelledby="peers">.*?</section>', re.S)
BY_COUNTY = re.compile(r'<section(?: class="section")? aria-labelledby="by-county">.*?</section>\n?', re.S)
TITLE = re.compile(r"<title>([^<]*)</title>")
OG_TITLE = re.compile(r'<meta property="og:title" content="([^"]*)">')


class IndexingError(ValueError):
    pass


def read(path):
    with open(path, encoding="utf-8", newline="") as fh:
        return fh.read()


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def esc(s):
    return html.escape(s, quote=True)


def county_slug(county):
    """'Cape May County' -> 'cape-may' (ASCII only)."""
    if not county.isascii():
        raise IndexingError(f"county name {county!r} is not ASCII; pick its slug by hand")
    base = county[:-len(" County")] if county.endswith(" County") else county
    slug = re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-")
    if not slug or not slug.isascii():
        raise IndexingError(f"no ASCII slug for county {county!r}")
    return slug


def county_short(county):
    return county[:-len(" County")] if county.endswith(" County") else county


def hub_path(county):
    return f"/nj/county/{county_slug(county)}/"


def hub_rel(county):
    return f"nj/county/{county_slug(county)}/index.html"


def url_of(rel):
    """Site URL of a file path: index.html -> /, a/index.html -> /a/, 404.html -> /404.html."""
    if rel == "index.html":
        return SITE + "/"
    if rel.endswith("/index.html"):
        return SITE + "/" + rel[:-len("index.html")]
    return SITE + "/" + rel


def jsonld(obj):
    return json.dumps(obj, sort_keys=True).replace("</", "<\\/")


def breadcrumb_ld(items):
    """items: [(name, absolute url)] in breadcrumb order."""
    return ('<script type="application/ld+json" id="ld-breadcrumb">'
            + jsonld({"@context": "https://schema.org", "@type": "BreadcrumbList",
                      "itemListElement": [{"@type": "ListItem", "item": u, "name": n, "position": i}
                                          for i, (n, u) in enumerate(items, 1)]})
            + "</script>")


# --- titles -------------------------------------------------------------------------------------------------------------------------
def with_suffix(title):
    return title + TITLE_SUFFIX if len(title + TITLE_SUFFIX) < TITLE_LIMIT else title


def base_title(title):
    """The build's title for a title this tool may have disambiguated (unescaped text in, unescaped text out)."""
    m = re.fullmatch(r"(?P<name>.+) \((?P<short>[A-Za-z][A-Za-z .'-]*) Co\) superintendent salary(?P<year>, \d{4}-\d\d)?(?: \| K12 Comp)?", title)
    if not m:
        return title
    return with_suffix(f"{m.group('name')} superintendent salary{m.group('year') or ''}")


def dup_title(title, name, county):
    """The disambiguated title for a district page whose build title is `title`."""
    m = re.fullmatch(r"(?P<name>.+?) superintendent salary(?P<year>, \d{4}-\d\d)?(?: \| K12 Comp)?", title)
    if not m or m.group("name") != name:
        raise IndexingError(f"unexpected district title {title!r} for {name!r}")
    return with_suffix(DUP_TITLE.format(name=name, short=county_short(county), year=m.group("year") or ""))


def page_title(page):
    m = TITLE.search(page)
    return html.unescape(m.group(1)) if m else None


def set_title(page, title):
    t, og = TITLE.findall(page), OG_TITLE.findall(page)
    if len(t) != 1 or len(og) != 1 or t[0] != og[0]:
        raise IndexingError("a district page needs one <title> and one og:title that mirrors it")
    page = TITLE.sub(lambda _m: f"<title>{esc(title)}</title>", page, count=1)
    return OG_TITLE.sub(lambda _m: f'<meta property="og:title" content="{esc(title)}">', page, count=1)


# --- indexability -------------------------------------------------------------------------------------------------------------------
def is_indexable(rel, page):
    robots = re.findall(r'<meta name="robots" content="([^"]*)"', page)
    if any("noindex" in r.lower() for r in robots):
        return False
    canon = re.findall(r'<link rel="canonical" href="([^"]*)"', page)
    return canon == [url_of(rel)]


def html_files(root):
    """Relative paths of every published HTML file under root (Jekyll excludes and dot dirs skipped), sorted."""
    out = []
    for dp, dns, fns in os.walk(root):
        rel_dir = os.path.relpath(dp, root).replace(os.sep, "/")
        if rel_dir == ".":
            dns[:] = [d for d in dns if d not in SKIP_TOP and not d.startswith((".", "_"))]
            rel_dir = ""
        else:
            dns[:] = [d for d in dns if not d.startswith(".")]
        out += [(rel_dir + "/" if rel_dir else "") + f for f in fns if f.endswith(".html")]
    return sorted(out)


def is_hub(rel):
    return re.fullmatch(r"nj/county/[a-z0-9-]+/index\.html", rel) is not None


def is_district(rel):
    return re.fullmatch(r"nj/[a-z0-9-]+-\d{7}/index\.html", rel) is not None


# --- the model: everything comes from the /nj/ table and the pages' own titles ---------------------------------------------------
class Row:
    def __init__(self, m):
        self.html = m.group(0)
        self.slug, self.leaid = m.group("slug"), m.group("leaid")
        self.name_html, self.name = m.group("name"), html.unescape(m.group("name"))
        self.county = html.unescape(m.group("county"))
        self.path = f"/nj/{self.slug}/"
        self.rel = f"nj/{self.slug}/index.html"


def peer_order_key(row):
    return (row.name.casefold(), row.name, row.leaid)


def peers_of(ordered, i):
    """The 8 peers of ordered[i] (one county, in peer order): 4 previous and 4 next, wrapping; all the others when the county is small."""
    n = len(ordered)
    if n - 1 <= 2 * PEERS_EACH_SIDE:
        return [ordered[(i + k) % n] for k in range(1, n)]
    return [ordered[(i + k) % n] for k in list(range(-PEERS_EACH_SIDE, 0)) + list(range(1, PEERS_EACH_SIDE + 1))]


class Model:
    def __init__(self, nj_page, titles):
        """nj_page: the /nj/ page text (any state). titles: {rel: <title> text, unescaped} of the tree's indexable pages (hubs ignored)."""
        self.nj_page = nj_page
        body = nj_page[nj_page.index("<tbody>"):nj_page.index("</tbody>")]
        self.rows = [Row(m) for m in ROW.finditer(body)]
        if not self.rows or len(self.rows) != body.count("<tr>"):
            raise IndexingError("could not read every /nj/ table row")
        if len({r.leaid for r in self.rows}) != len(self.rows):
            raise IndexingError("duplicate LEAID in the /nj/ table")
        self.by_leaid = {r.leaid: r for r in self.rows}
        self.counties = sorted({r.county for r in self.rows})
        slugs = [county_slug(c) for c in self.counties]
        if len(set(slugs)) != len(slugs):
            raise IndexingError("two counties share a slug")
        self.table_order = {c: [r for r in self.rows if r.county == c] for c in self.counties}
        self.peer_order = {c: sorted(rs, key=peer_order_key) for c, rs in self.table_order.items()}
        self.peers = {}
        for c, rs in self.peer_order.items():
            for i, r in enumerate(rs):
                self.peers[r.leaid] = peers_of(rs, i)
        # duplicate titles among indexable pages, compared on the build's titles
        groups = {}
        for rel, t in titles.items():
            if not is_hub(rel):
                groups.setdefault(base_title(t), []).append(rel)
        self.dup_rels = set()
        for t, rels in groups.items():
            if len(rels) > 1:
                bad = [r for r in rels if not is_district(r)]
                if bad:
                    raise IndexingError(f"duplicate title {t!r} on pages this tool does not own: {bad}")
                self.dup_rels.update(rels)
        known = {r.rel for r in self.rows}
        if not self.dup_rels <= known:
            raise IndexingError(f"duplicate-title pages missing from the /nj/ table: {sorted(self.dup_rels - known)}")


def titles_of(pages):
    """{rel: title} of the indexable pages in {rel: text}."""
    return {rel: page_title(p) for rel, p in pages.items() if is_indexable(rel, p) and page_title(p) is not None}


def model_from_tree(root, nj_page=None):
    pages = {rel: read(os.path.join(root, *rel.split("/"))) for rel in html_files(root) if not is_hub(rel)}
    return Model(nj_page if nj_page is not None else pages["nj/index.html"], titles_of(pages))


# --- shared blocks ------------------------------------------------------------------------------------------------------------------
def link_list(links):
    return '<ul class="guides">' + "".join(f'<li><a href="{h}">{t}</a></li>' for h, t in links) + "</ul>"


def by_county_section(model, cls):
    attr = ' class="section"' if cls else ""
    return (f'<section{attr} aria-labelledby="by-county"><h2 id="by-county">{esc(BY_COUNTY_H2)}</h2>'
            + link_list([(hub_path(c), esc(c)) for c in model.counties]) + "</section>")


# --- district pages -----------------------------------------------------------------------------------------------------------------
def strip_district(page):
    page = LD_CRUMB.sub("", page)
    page = CRUMB_NEW.sub(lambda _m: CRUMB_OLD_HTML, page)
    page = PEERS.sub("", page)
    t = page_title(page)
    if t is not None and base_title(t) != t:
        page = set_title(page, base_title(t))
    return page


def rewrite_district(page, model, leaid):
    page = strip_district(page)
    row = model.by_leaid.get(leaid)
    if row is None:
        raise IndexingError(f"{leaid}: not in the /nj/ table")
    h1 = re.findall(r"<h1>(.*?)</h1>", page)
    if h1 != [row.name_html] and [html.unescape(h) for h in h1] != [row.name]:
        raise IndexingError(f"{leaid}: h1 {h1} is not the /nj/ name {row.name!r}")
    meta = re.search(r'<p class="meta mono">NCES (\d{7}) · ([^·<]+) · ', page)
    if not meta or meta.group(1) != leaid or html.unescape(meta.group(2)).strip() != row.county.upper():
        raise IndexingError(f"{leaid}: the page's county line does not match the /nj/ County cell {row.county!r}")
    old = CRUMB_OLD_HTML + h1[0] + "</span></nav>"
    if page.count(old) != 1 or page.count("</main>") != 1 or page.count("</head>") != 1:
        raise IndexingError(f"{leaid}: not the expected breadcrumb / </main> / </head> structure")
    hub = hub_path(row.county)
    page = page.replace(old, f'<nav aria-label="Breadcrumb" class="crumbs"><a href="/nj/">{esc(CRUMB_ROOT)}</a> / '
                             f'<a href="{hub}">{esc(row.county)}</a> / <span aria-current="page">{h1[0]}</span></nav>', 1)
    ld = breadcrumb_ld([(CRUMB_ROOT, SITE + "/nj/"), (row.county, SITE + hub), (row.name, SITE + row.path)])
    page = page.replace("</head>", ld + "</head>", 1)
    peers = ('<section class="peers" aria-labelledby="peers">'
             f'<h2 id="peers">{esc(PEERS_H2.format(county=row.county))}</h2>'
             + link_list([(p.path, p.name_html) for p in model.peers[leaid]]) + "</section>")
    page = page.replace("</main>", peers + "</main>", 1)
    if row.rel in model.dup_rels:
        page = set_title(page, dup_title(page_title(page), row.name, row.county))
    return page


# --- /nj/ and / ---------------------------------------------------------------------------------------------------------------------
def strip_nj(page):
    page = BY_COUNTY.sub("", page)
    return re.sub(r"<h1>New Jersey superintendent salaries, (\d+) districts</h1>",
                  lambda m: f"<h1>{NJ_H1_OLD.format(n=m.group(1))}</h1>", page)


def rewrite_nj(page, model):
    page = strip_nj(page)
    old = f"<h1>{NJ_H1_OLD.format(n=len(model.rows))}</h1>"
    if page.count(old) != 1 or page.count("</main>") != 1:
        raise IndexingError(f"/nj/: expected one {old} and one </main>")
    page = page.replace(old, f"<h1>{esc(NJ_H1.format(n=len(model.rows)))}</h1>", 1)
    return page.replace("</main>", by_county_section(model, cls=False) + "\n</main>", 1)


def strip_home(page):
    return BY_COUNTY.sub("", page)


def rewrite_home(page, model):
    page = strip_home(page)
    anchor = '<p class="closing">'
    if page.count(anchor) != 1:
        raise IndexingError("/: no single closing paragraph to anchor the county list")
    return page.replace(anchor, by_county_section(model, cls=True) + "\n" + anchor, 1)


# --- hubs ---------------------------------------------------------------------------------------------------------------------------
def render_hub(model, county):
    nj = model.nj_page
    rows = model.table_order[county]
    n = len(rows)
    url = SITE + hub_path(county)
    title = with_suffix(HUB_TITLE.format(county=county))
    desc = HUB_DESC.format(n=n, county=county)
    head = nj[:nj.index("</head>")]
    head, k = re.subn(r'<script type="application/ld\+json">.*?</script>', "", head, count=1, flags=re.S)
    if k != 1:
        raise IndexingError("/nj/ head has no Dataset block")
    for pat, val in ((r"<title>[^<]*</title>", f"<title>{esc(title)}</title>"),
                     (r'<meta name="description" content="[^"]*">', f'<meta name="description" content="{esc(desc)}">'),
                     (r'<link rel="canonical" href="[^"]*">', f'<link rel="canonical" href="{url}">'),
                     (r'<meta property="og:title" content="[^"]*">', f'<meta property="og:title" content="{esc(title)}">'),
                     (r'<meta property="og:description" content="[^"]*">', f'<meta property="og:description" content="{esc(desc)}">'),
                     (r'<meta property="og:url" content="[^"]*">', f'<meta property="og:url" content="{url}">')):
        head, k = re.subn(pat, lambda _m, v=val: v, head, count=1)
        if k != 1:
            raise IndexingError(f"/nj/ head lacks {pat[:30]}")
    head += breadcrumb_ld([(CRUMB_ROOT, SITE + "/nj/"), (county, url)]) + "</head>"
    body = nj[nj.index("</head>") + len("</head>"):nj.index('<main id="main">')]
    foot = nj[nj.index('<footer class="site-footer">'):]
    disclaimer = re.search(r'<p class="disclaimer">.*?</p>', nj[nj.index('<main id="main">'):], re.S).group(0)
    thead = re.search(r"<thead>.*?</thead>", nj, re.S).group(0)
    c = esc(county)
    main = ('<main id="main">'
            f'<nav aria-label="Breadcrumb" class="crumbs"><a href="/nj/">{esc(CRUMB_ROOT)}</a> / <span aria-current="page">{c}</span></nav>'
            f"<h1>{esc(HUB_H1.format(county=county))}</h1><p class=\"sub\">{esc(HUB_INTRO.format(n=n, county=county))}</p>\n"
            f"{disclaimer}\n"
            f'<div class="table-wrap" tabindex="0" role="region" aria-label="{esc(HUB_CAPTION.format(county=county))}"><table id="districts">'
            f"<caption>{esc(HUB_CAPTION.format(county=county))}</caption>{thead}<tbody>" + "".join(r.html for r in rows) + "</tbody></table></div>\n"
            f'<p><a href="/nj/">{esc(HUB_BACK)}</a></p>\n</main>')
    return head + body + main + foot


# --- sitemap ------------------------------------------------------------------------------------------------------------------------
SM_HEAD = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
SM_URL = re.compile(r"<url><loc>([^<]+)</loc><lastmod>(\d{4}-\d\d-\d\d)</lastmod></url>\n")


def updated_date(page):
    m = re.search(r'<main id="main">', page)
    u = re.search(r"(?i)\bupdated (\d{4}-\d\d-\d\d)\b", page[m.end():] if m else page)
    return u.group(1) if u else ""


def owned(rel):
    return rel in ("index.html", "nj/index.html") or is_district(rel)


def sitemap_rels(pages):
    rels = [r for r, p in pages.items() if not r.startswith("api/") and is_indexable(r, p)]
    return sorted(rels, key=lambda r: (r == HISTORY, r))


def render_sitemap(old, pages):
    """old: the current sitemap text; pages: {rel: final text} of every HTML page of the tree (hubs included)."""
    if not old.startswith(SM_HEAD) or not old.endswith("</urlset>\n"):
        raise IndexingError("sitemap.xml is not in the expected format")
    body = old[len(SM_HEAD):-len("</urlset>\n")]
    entries = SM_URL.findall(body)
    if "".join(f"<url><loc>{u}</loc><lastmod>{d}</lastmod></url>\n" for u, d in entries) != body:
        raise IndexingError("sitemap.xml has an entry in an unexpected format")
    lastmod = dict(entries)
    out = []
    for rel in sitemap_rels(pages):
        url = url_of(rel)
        if is_hub(rel):
            d = RELEASE_DATE
        elif owned(rel):
            d = max(updated_date(pages[rel]), RELEASE_DATE)
        elif url in lastmod:
            d = lastmod[url]
        else:
            raise IndexingError(f"{url}: indexable, not rewritten by this tool and has no lastmod in the current sitemap")
        out.append(f"<url><loc>{url}</loc><lastmod>{d}</lastmod></url>\n")
    return SM_HEAD + "".join(out) + "</urlset>\n"


# --- the tree -----------------------------------------------------------------------------------------------------------------------
def final_tree(root):
    """(model, {rel: (current text or None, final text or None)}) for every file this tool owns. None final = remove (a stale hub)."""
    files = html_files(root)
    current = {rel: read(os.path.join(root, *rel.split("/"))) for rel in files}
    model = Model(current["nj/index.html"], titles_of({r: t for r, t in current.items() if not is_hub(r)}))
    final = {}
    for row in model.rows:
        if row.rel not in current:
            raise IndexingError(f"{row.rel}: in the /nj/ table but missing")
        final[row.rel] = rewrite_district(current[row.rel], model, row.leaid)
    extra = [r for r in files if is_district(r) and r not in final]
    if extra:
        raise IndexingError(f"district pages not in the /nj/ table: {extra[:5]}")
    final["nj/index.html"] = rewrite_nj(current["nj/index.html"], model)
    final["index.html"] = rewrite_home(current["index.html"], model)
    hubs = {hub_rel(c): render_hub(model, c) for c in model.counties}
    final.update(hubs)
    for rel in files:
        if is_hub(rel) and rel not in hubs:
            final[rel] = None
    pages = {rel: final[rel] if rel in final else current[rel] for rel in set(current) | set(final)}
    pages = {r: t for r, t in pages.items() if t is not None}
    sm = os.path.join(root, "sitemap.xml")
    cur_sm = read(sm)
    out = {rel: (current.get(rel), text) for rel, text in final.items()}
    out["sitemap.xml"] = (cur_sm, render_sitemap(cur_sm, pages))
    return model, out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("site", nargs="?", default=ROOT, help="site tree (default: the repo root)")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--check", action="store_true", help="exit 1 if any owned file is not in its final form")
    g.add_argument("--write", action="store_true", help="rewrite in place (the default)")
    a = ap.parse_args(argv)
    try:
        model, files = final_tree(a.site)
    except IndexingError as e:
        print("nj_indexing:", e, file=sys.stderr)
        return 2
    stale = sorted(rel for rel, (cur, want) in files.items() if cur != want)
    if not a.check:
        for rel in stale:
            p = os.path.join(a.site, *rel.split("/"))
            if files[rel][1] is None:
                os.remove(p)
                if not os.listdir(os.path.dirname(p)):
                    os.rmdir(os.path.dirname(p))
            else:
                write(p, files[rel][1])
    n_sm = files["sitemap.xml"][1].count("<url>")
    verb = "stale" if a.check else "rewritten"
    print(f"{len(model.counties)} county hubs, {len(model.rows)} districts, {len(model.dup_rels)} disambiguated titles, "
          f"{n_sm} sitemap URLs; {len(stale)} files {verb}" + "".join(f"\n  {s}" for s in stale[:30])
          + (f"\n  ... and {len(stale) - 30} more" if len(stale) > 30 else ""))
    return 1 if a.check and stale else 0


if __name__ == "__main__":
    sys.exit(main())
