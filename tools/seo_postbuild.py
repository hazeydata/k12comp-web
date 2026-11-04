"""Post-build step for the K12 Comp static site (run from the repo root).

Idempotent. Rebuilds from the data already in the site, never by hand:
- JSON-LD: Place for each district page (from /api/v1/nj/<leaid>.json and the
  page's county line), WebSite + Dataset on the home page.
- Revenue slots: empty, hidden placeholder blocks (no third-party scripts).
- sitemap.xml: every page without a noindex robots meta.
Usage: python3 tools/seo_postbuild.py [site_root]
"""
import glob, html, json, os, re, sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else "."
SITE = "https://k12comp.com"
DEFAULT_LASTMOD = "2026-10-30"


def ld(obj, marker):
    return f'<script type="application/ld+json" id="{marker}">{json.dumps(obj, sort_keys=True)}</script>'


def put_ld(s, marker, obj):
    s = re.sub(rf'<script type="application/ld\+json" id="{marker}">.*?</script>', "", s, flags=re.S)
    return s.replace("</head>", ld(obj, marker) + "</head>", 1)


def put_slot(s, name, where):
    if f'data-slot="{name}"' in s:
        return s
    block = f'<div class="slot" data-slot="{name}" hidden aria-hidden="true"></div>'
    return s.replace(where, block + where, 1) if where in s else s


def page_path(f):
    rel = os.path.relpath(f, ROOT).replace(os.sep, "/")
    return "/" + (rel[: -len("index.html")] if rel.endswith("index.html") else rel)


urls = []
for f in sorted(glob.glob(os.path.join(ROOT, "**", "*.html"), recursive=True)):
    if "/.git/" in f or "/tools/" in f:
        continue
    s = open(f, encoding="utf-8").read()
    path = page_path(f)
    m = re.match(r"^/nj/[a-z0-9-]+-(\d{7})/$", path)
    if m:
        leaid = m.group(1)
        api = os.path.join(ROOT, "api", "v1", "nj", f"{leaid}.json")
        d = json.load(open(api, encoding="utf-8"))
        meta = re.search(r'<p class="meta mono">NCES \d+(?: · ([^·<]+))? · UPDATED ([\d-]+)</p>', s)
        county = meta.group(1).strip().title() if meta and meta.group(1) else None
        place = {"@context": "https://schema.org", "@type": "Place", "name": d["district"],
                 "identifier": {"@type": "PropertyValue", "propertyID": "NCES LEAID", "value": d["nces_leaid"]},
                 "address": {"@type": "PostalAddress", "addressRegion": "NJ", "addressCountry": "US"},
                 "url": SITE + path}
        if county:
            place["containedInPlace"] = {"@type": "AdministrativeArea", "name": county + ", New Jersey"}
        s = put_ld(s, "ld-place", place)
        s = put_slot(s, "district-1", '<section aria-labelledby="dl">')
        lastmod = meta.group(2) if meta else DEFAULT_LASTMOD
    else:
        lastmod = DEFAULT_LASTMOD
    if path == "/":
        s = put_ld(s, "ld-site", {"@context": "https://schema.org", "@type": "WebSite", "name": "K12 Comp", "url": SITE + "/"})
        s = put_ld(s, "ld-dataset", {"@context": "https://schema.org", "@type": "Dataset",
            "name": "New Jersey K-12 superintendent contracts and salary guides",
            "description": re.search(r'<meta name="description" content="([^"]*)"', s).group(1),
            "license": "https://creativecommons.org/licenses/by/4.0/", "url": SITE + "/",
            "creator": {"@type": "Organization", "name": "K12 Comp (hazeydata)"}})
        s = put_slot(s, "home-1", '<p class="closing">')
    if path == "/nj/":
        s = put_slot(s, "state-1", '<h2 id="list">')
    open(f, "w", encoding="utf-8").write(s)
    if 'name="robots" content="noindex"' not in s:
        urls.append((path, lastmod))

with open(os.path.join(ROOT, "sitemap.xml"), "w", encoding="utf-8") as out:
    out.write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
    for p, lm in sorted(urls):
        out.write(f"<url><loc>{html.escape(SITE + p)}</loc><lastmod>{lm}</lastmod></url>\n")
    out.write("</urlset>\n")
print(f"pages in sitemap: {len(urls)}")
