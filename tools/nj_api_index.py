"""Leftover 10 (K12-SITE-NJ-HISTORY-001): an index at /api/v1/nj/, the contentUrl of the Dataset JSON-LD on /nj/.

/nj/index.html (a build output pinned to base 3b50ce10, so it is not edited here) names /api/v1/nj/ as its DataDownload, but only
/api/v1/nj/<leaid>.json existed, so that URL was a 404. This writes api/v1/nj/index.html: one link per JSON file, labelled with the
file's own "district" and "nces_leaid" values, plus a link to that district's page. Nothing else is read; no other file changes.
Same input -> byte-identical output.

    python3 tools/nj_api_index.py --check   # exit 1 if api/v1/nj/index.html is missing or stale
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
TITLE = "NJ district JSON files | K12 Comp"
DESC = "One JSON file per New Jersey district, with the same superintendent contract facts and salary-guide cells as its district page."
OG_ALT = "K12 Comp: what New Jersey school districts pay their superintendents. Sourced, checkable, no estimates."


def entries():
    pages = {m.group(1): d for d in os.listdir(os.path.join(ROOT, "nj")) if (m := re.fullmatch(r"[a-z0-9-]+-(\d{7})", d))}
    out = []
    for f in sorted(glob.glob(os.path.join(API, "*.json"))):
        leaid = os.path.basename(f)[:-5]
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
            'See <a href="/llms.txt">llms.txt</a> for the fields.</p>'
            f'<div class="table-wrap" tabindex="0" role="region" aria-label="NJ district JSON files"><table><caption>NJ district JSON files ({n})</caption>'
            '<thead><tr><th scope="col">File</th><th scope="col">District</th><th scope="col">Page</th></tr></thead>'
            f'<tbody>{rows}</tbody></table></div></main>'
            '<footer class="site-footer"><div class="inner"><ul><li><a href="/about/">Methodology</a></li><li><a href="/privacy/">Privacy</a></li>'
            '<li><a href="/terms/">Terms</a></li><li><a href="/llms.txt">JSON API</a></li></ul><p>CC BY 4.0. Attribution: NJDOE, NCES, district source documents. '
            'UFB source files are published by NJ.gov under NJ.gov terms.</p><p>Made by Fred Hazelton and his AI bots at HazeyData.</p></div></footer></body></html>\n')
    return head + body


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true")
    g.add_argument("--write", action="store_true")
    a = ap.parse_args(argv)
    new = render()
    if a.write:
        with open(OUT, "w", encoding="utf-8", newline="") as f:
            f.write(new)
        print(f"wrote {os.path.relpath(OUT, ROOT)} ({len(entries())} files)")
        return 0
    have = open(OUT, encoding="utf-8", newline="").read() if os.path.isfile(OUT) else None
    ok = have == new
    print(f"{os.path.relpath(OUT, ROOT)}: {'up to date' if ok else 'missing or stale'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
