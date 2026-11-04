"""Post-build step for the K12 Comp static site (run from the repo root).

Idempotent; everything comes from data already on each page (design.md,
"SEO, upkeep and revenue"):
- title, meta description, og:title, og:description per the templates;
- district pages: Dataset JSON-LD with name, licence and source URLs only;
- source lines: collapse a doubled "Source: Source:" label;
- revenue slots: newsletter signup (inert preview) and an empty, hidden
  sponsor/licence slot.
Sitemap regeneration is out of scope this cycle.
Usage: python3 tools/seo_postbuild.py [site_root]
"""
import glob, html, json, os, re, sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else "."
LIC = "https://creativecommons.org/licenses/by/4.0/"

NEWSLETTER = (
    '<section class="newsletter" data-slot="newsletter" aria-labelledby="nl-h">'
    '<h2 id="nl-h">Know when the numbers change.</h2>'
    '<p>An email when we add new contracts, salary guides or corrections. Nothing else.</p>'
    '<!-- form action: {{PLACEHOLDER: newsletter provider form action, Fred to pick provider}} -->'
    '<form class="nl-form" novalidate data-inert="true">'
    '<label><span class="sr-only">Email address</span><input type="email" name="email" placeholder="you@district.org" autocomplete="email"></label>'
    '<button class="btn ghost" type="submit">Get updates</button></form>'
    '<p class="nl-status" role="status" aria-live="polite"></p>'
    '<p class="note">Unsubscribe anytime. See our <a href="/privacy/">Privacy page</a>.</p>'
    '<script>(function(){var s=document.currentScript.parentNode,f=s.querySelector("form"),i=f.querySelector("input"),o=s.querySelector(".nl-status");'
    'f.addEventListener("submit",function(e){e.preventDefault();var v=i.value.trim();'
    'if(!/^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$/.test(v)){o.className="nl-status err";o.textContent="That email doesn\'t look right. Try again.";i.focus();return;}'
    'i.value="";o.className="nl-status ok";o.textContent="Coming soon. Signups aren\'t open yet, so nothing was sent or saved.";});})();</script>'
    '</section>')
SPONSOR = '<section class="slot sponsor" data-slot="sponsor" hidden aria-label="Bulk data and licensing"></section>'


def meta(s, title, desc):
    e = html.escape
    s = re.sub(r"<title>.*?</title>", f"<title>{e(title)}</title>", s, count=1)
    for pat, val in ((r'<meta name="description" content="[^"]*">', f'<meta name="description" content="{e(desc)}">'),
                     (r'<meta property="og:title" content="[^"]*">', f'<meta property="og:title" content="{e(title)}">'),
                     (r'<meta property="og:description" content="[^"]*">', f'<meta property="og:description" content="{e(desc)}">')):
        s = re.sub(pat, val, s, count=1)
    return s


def insert_once(s, marker, block, before):
    if f'data-slot="{marker}"' in s or before not in s:
        return s
    return s.replace(before, block + before, 1)


over = []
for f in sorted(glob.glob(os.path.join(ROOT, "**", "*.html"), recursive=True)):
    if "/.git/" in f or "/tools/" in f:
        continue
    s = open(f, encoding="utf-8").read()
    rel = "/" + os.path.relpath(f, ROOT).replace(os.sep, "/").replace("index.html", "")
    if rel == "/":
        desc = re.search(r'<meta name="description" content="([^"]*)"', s).group(1)
        s = meta(s, "K12 Comp: NJ superintendent pay, sourced", html.unescape(desc))
        s = insert_once(s, "newsletter", NEWSLETTER, '<section class="section" aria-labelledby="guides">')
        s = insert_once(s, "sponsor", SPONSOR, '<footer class="site-footer">')
    elif rel == "/nj/":
        n = len(re.findall(r'<tr><th scope="row">', s))
        s = meta(s, "New Jersey superintendent salaries by district | K12 Comp",
                 f"Base salary and contract terms for {n} New Jersey districts, each linked to its source document.")
        s = insert_once(s, "sponsor", SPONSOR, '<footer class="site-footer">')
    elif rel == "/terms/":
        s = meta(s, "Terms | K12 Comp", "How you can use K12 Comp data, and what it does and doesn't promise.")
    elif re.match(r"^/nj/[a-z0-9-]+-\d{7}/$", rel):
        name = html.unescape(re.search(r"<h1>(.*?)</h1>", s).group(1))
        m = re.search(r'Latest base salary · ([^<]+)</h2><p class="big num">([^<]+)</p>', s)
        c = re.search(r'<dt>Contract</dt><dd class="num">([\d-]+) – ([\d-]+)</dd>', s)
        year = m.group(1) if m else None
        sal = m.group(2) if m and m.group(2).startswith("$") else None
        title = f"{name} superintendent salary, {year} | K12 Comp" if year else f"{name} superintendent salary | K12 Comp"
        if len(title) >= 60:
            title = title.replace(" | K12 Comp", "")
        clauses = []
        if sal and year:
            clauses.append(f"base salary {sal} in {year}")
        if c:
            clauses.append(f"contract {c.group(1)} to {c.group(2)}")
        desc = f"{name}, NJ: " + ", ".join(clauses) + ". Source linked." if clauses else f"{name}, NJ. Source linked."
        if len(desc) >= 155 and len(clauses) > 1:
            desc = f"{name}, NJ: {clauses[0]}. Source linked."
        s = meta(s, title, desc)
        srcs = sorted(set(u for u in re.findall(r'<p class="source"[^>]*>.*?</p>', s, re.S) for u in re.findall(r'href="(https?://[^"]+)"', u)))
        ds = {"@context": "https://schema.org", "@type": "Dataset", "name": name, "license": LIC, "isBasedOn": srcs}
        s = re.sub(r'<script type="application/ld\+json"[^>]*>.*?</script>',
                   f'<script type="application/ld+json">{json.dumps(ds, sort_keys=True)}</script>', s, count=1, flags=re.S)
        s = insert_once(s, "newsletter", NEWSLETTER, '<section aria-labelledby="dl">')
        if len(title) >= 60 or len(desc) >= 155:
            over.append(rel)
    s = s.replace('<p class="source">Source: Source: ', '<p class="source">Source: ')
    s = re.sub(r'<div class="slot" data-slot="[a-z0-9-]+" hidden aria-hidden="true"></div>', "", s)
    s = re.sub(r'<script type="application/ld\+json" id="ld-(?:place|site|dataset)">.*?</script>', "", s, flags=re.S)
    open(f, "w", encoding="utf-8").write(s)
print("pages over length limits:", len(over), over[:5])
