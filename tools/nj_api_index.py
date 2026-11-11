"""Leftover 10 (K12-SITE-NJ-HISTORY-001): make the Dataset JSON-LD on /nj/ truthful. Its DataDownload says application/json.

It named /api/v1/nj/ as contentUrl, but only /api/v1/nj/<leaid>.json existed, so that URL was a 404. This writes three things:

- api/v1/nj/index.json: the JSON the Dataset now points at. One entry per district JSON file (file URL, the file's own "district" and
  "nces_leaid" values, the district page), same serialisation as the district files (indent 1, sorted keys, final newline).
- api/v1/nj/index.html: the same list as a page for people (site header and footer). No metadata calls this page JSON.
- /nj/index.html: one scoped edit, the contentUrl "/api/v1/nj/" becomes "/api/v1/nj/index.json" (JSONLD_OLD -> JSONLD_NEW, exactly
  one occurrence, nothing else on the page). The history build still writes the old value from base 3b50ce10, so re-run --write
  after copying a fresh build in place; tests/test_nj_history_committed.py allows exactly this substitution and nothing more.

Only the district JSON files, the district page directory names and /nj/index.html are read. Same input -> byte-identical output.

    python3 tools/nj_api_index.py --check   # exit 1 if any of the three is missing or stale
    python3 tools/nj_api_index.py --write
"""
import argparse
import glob
import html
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = os.path.join(ROOT, "api", "v1", "nj")
OUT = os.path.join(API, "index.html")
OUT_JSON = os.path.join(API, "index.json")
NJ_PAGE = os.path.join(ROOT, "nj", "index.html")
JSONLD_OLD = '"contentUrl": "/api/v1/nj/"'  # what base 3b50ce10 and the history build write: a directory URL, never JSON
JSONLD_NEW = '"contentUrl": "/api/v1/nj/index.json"'
LICENSE = "https://creativecommons.org/licenses/by/4.0/"  # the license the /nj/ Dataset block states
JSON_DESC = "Index of the New Jersey district JSON files under /api/v1/nj/. One entry per district; each url is that district's file."
TITLE = "NJ district JSON files | K12 Comp"
DESC = "One JSON file per New Jersey district, with the same superintendent contract facts and salary-guide cells as its district page."
OG_ALT = "K12 Comp: what New Jersey school districts pay their superintendents. Sourced, checkable, no estimates."


def entries():
    pages = {m.group(1): d for d in os.listdir(os.path.join(ROOT, "nj")) if (m := re.fullmatch(r"[a-z0-9-]+-(\d{7})", d))}
    out = []
    for f in sorted(glob.glob(os.path.join(API, "*.json"))):
        if os.path.basename(f) == "index.json":  # this tool's own output, never an input
            continue
        leaid = os.path.basename(f)[:-5]
        if not re.fullmatch(r"\d{7}", leaid):
            raise SystemExit(f"{f}: not a district file (<7-digit NCES LEAID>.json) and not index.json")
        with open(f, encoding="utf-8") as fh:
            d = json.load(fh)
        if d.get("nces_leaid") != leaid:
            raise SystemExit(f"{f}: nces_leaid {d.get('nces_leaid')!r} does not match the file name")
        out.append((leaid, d.get("district") or leaid, pages.get(leaid)))
    return out


def render():
    e = html.escape
    rows = "".join(
        f'<tr><td><a href="/api/v1/nj/{lea}.json">{lea}.json</a></td><td>{e(name)}</td>'
        f'<td>{f"<a href={chr(34)}/nj/{page}/{chr(34)}>District page</a>" if page else ""}</td></tr>'
        for lea, name, page in entries())
    n = len(entries())
    head = (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>{e(TITLE)}</title><meta name="description" content="{e(DESC)}"><link rel="canonical" href="https://k12comp.com/api/v1/nj/">'
            f'<meta property="og:title" content="{e(TITLE)}"><meta property="og:description" content="{e(DESC)}">'
            f'<meta property="og:url" content="https://k12comp.com/api/v1/nj/"><meta property="og:type" content="website">'
            f'<meta property="og:image" content="https://k12comp.com/og-image.png"><meta property="og:image:width" content="1200">'
            f'<meta property="og:image:height" content="630"><meta property="og:image:alt" content="{e(OG_ALT)}"><meta name="twitter:card" content="summary_large_image">'
            f'<link rel="icon" href="/favicon.svg" type="image/svg+xml"><link rel="icon" href="/favicon-32.png" sizes="32x32" type="image/png">'
            f'<link rel="apple-touch-icon" href="/apple-touch-icon.png"><link rel="stylesheet" href="/style.css">'
            '<script data-goatcounter="https://k12comp.goatcounter.com/count" async src="https://gc.zgo.at/count.js"></script></head>')  # same as every page
    body = ('<body><a class="skip" href="#main">Skip to content</a><header class="site-header"><nav aria-label="Main"><a class="brand" href="/">'
            '<span class="k" aria-hidden="true">K</span>K12 Comp</a><ul><li><a href="/nj/">Districts</a></li><li><a href="/about/">Methodology</a></li></ul></nav></header>'
            f'<main id="main"><h1>NJ district JSON files</h1><p>{n} files, one per district, at <code>/api/v1/nj/&lt;NCES LEAID&gt;.json</code>. '
            'Each holds the same superintendent contract facts and salary-guide cells as its district page, with their sources. '
            'See <a href="/llms.txt">llms.txt</a> for the fields. The same list as JSON: <a href="/api/v1/nj/index.json">index.json</a>.</p>'
            f'<div class="table-wrap" tabindex="0" role="region" aria-label="NJ district JSON files"><table><caption>NJ district JSON files ({n})</caption>'
            '<thead><tr><th scope="col">File</th><th scope="col">District</th><th scope="col">Page</th></tr></thead>'
            f'<tbody>{rows}</tbody></table></div></main>'
            '<footer class="site-footer"><div class="inner"><ul><li><a href="/about/">Methodology</a></li><li><a href="/privacy/">Privacy</a></li>'
            '<li><a href="/terms/">Terms</a></li><li><a href="/llms.txt">JSON API</a></li></ul><p>CC BY 4.0. Attribution: NJDOE, NCES, district source documents. '
            'UFB source files are published by NJ.gov under NJ.gov terms.</p><p>Made by Fred Hazelton and his AI bots at HazeyData.</p></div></footer></body></html>\n')
    return head + body


def render_json():
    files = [{"district": name, "nces_leaid": lea, "page": f"/nj/{page}/" if page else None, "url": f"/api/v1/nj/{lea}.json"}
             for lea, name, page in entries()]
    doc = {"count": len(files), "description": JSON_DESC, "files": files, "license": LICENSE, "state": "NJ"}
    return json.dumps(doc, indent=1, sort_keys=True) + "\n"


def nj_page(page):
    """/nj/index.html bytes with the Dataset contentUrl pointing at index.json. Exactly one contentUrl, old or new, or it is an error."""
    old, new = page.count(JSONLD_OLD.encode()), page.count(JSONLD_NEW.encode())
    if (old, new) == (1, 0):
        return page.replace(JSONLD_OLD.encode(), JSONLD_NEW.encode(), 1)
    if (old, new) == (0, 1):
        return page
    raise SystemExit(f"nj/index.html: expected exactly one Dataset contentUrl for /api/v1/nj/ (found {old} old, {new} new); not edited")


def targets():
    """[(path, wanted bytes)] for the three files this tool owns."""
    with open(NJ_PAGE, "rb") as f:
        nj = f.read()
    return [(OUT, render().encode("utf-8")), (OUT_JSON, render_json().encode("utf-8")), (NJ_PAGE, nj_page(nj))]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true")
    g.add_argument("--write", action="store_true")
    a = ap.parse_args(argv)
    rc = 0
    for path, want in targets():
        rel = os.path.relpath(path, ROOT)
        have = None
        if os.path.isfile(path):
            with open(path, "rb") as f:
                have = f.read()
        if a.write:
            if have != want:
                with open(path, "wb") as f:
                    f.write(want)
            print(f"{rel}: {'already up to date' if have == want else 'written'}")
        else:
            print(f"{rel}: {'up to date' if have == want else 'missing or stale'}")
            rc = rc or (0 if have == want else 1)
    return rc


if __name__ == "__main__":
    sys.exit(main())
