"""Check that the files named by JSON-LD on this site are what the JSON-LD says they are (K12-SITE-NJ-HISTORY-001 leftover 10).

Walks every published .html file under the site root and parses every <script type="application/ld+json"> block. For each object,
at any depth, that has a contentUrl and an encodingFormat of application/json (or text/csv), it resolves the URL to the file GitHub
Pages would serve and reads that file: it must exist, be published, carry the matching extension (Pages sets Content-Type from the
extension, so /dir/ is index.html and text/html) and parse as JSON (or CSV).

No network request is ever made. Site URLs (root-relative, page-relative, or absolute on the CNAME host) are read from disk. A URL
on any other host cannot be verified offline, so it is reported as a problem rather than passed.

    python3 tools/jsonld_content_urls.py [--site .]     # one line per problem; exit 1 if there is any
"""
import argparse
import csv
import io
import json
import os
import posixpath
import re
import sys
from urllib.parse import unquote, urlsplit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT_RE = re.compile(r"""<script\b[^>]*\btype\s*=\s*["']?application/ld\+json["']?[^>]*>(.*?)</script>""", re.S | re.I)
SKIP_DIRS = {".git", "node_modules", "__pycache__"}
EXT = {"application/json": ".json", "text/csv": ".csv"}  # format -> the extension Pages serves with that Content-Type


def _not_json_constant(name):
    raise ValueError(f"{name} is not JSON")


def parse_json(raw):
    """Strict JSON: UTF-8, no NaN/Infinity, not empty. Raises ValueError."""
    return json.loads(raw.decode("utf-8"), parse_constant=_not_json_constant)


def parse_csv(raw):
    rows = list(csv.reader(io.StringIO(raw.decode("utf-8"), newline=""), strict=True))
    if not rows or not any(c.strip() for c in rows[0]):
        raise ValueError("no header row")
    return rows


PARSE = {"application/json": parse_json, "text/csv": parse_csv}


def jekyll_excludes(site_root):
    """The exclude list in _config.yml (top-level names Pages does not publish)."""
    f = os.path.join(site_root, "_config.yml")
    if not os.path.isfile(f):
        return []
    with open(f, encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    out, on = [], False
    for ln in lines:
        if ln.startswith("exclude:"):
            on = True
        elif on and ln.strip().startswith("- "):
            out.append(ln.strip()[2:].strip().strip("/"))
        elif on and ln.strip() and not ln.strip().startswith("#"):
            on = False
    return out


def published(rel, excludes):
    """True if Pages (Jekyll) publishes this site-relative path: no dot or underscore segment, not under an excluded name."""
    parts = rel.split("/")
    if any(p.startswith((".", "_")) for p in parts):
        return False
    return not any(rel == e or rel.startswith(e + "/") for e in excludes)


def site_hosts(site_root):
    f = os.path.join(site_root, "CNAME")
    if not os.path.isfile(f):
        return set()
    with open(f, encoding="utf-8") as fh:
        host = fh.read().strip().lower()
    return {host, "www." + host} if host else set()


def html_pages(site_root, excludes):
    out = []
    for dp, dns, fns in os.walk(site_root):
        dns[:] = sorted(d for d in dns if d not in SKIP_DIRS)
        for fn in sorted(fns):
            rel = os.path.relpath(os.path.join(dp, fn), site_root).replace(os.sep, "/")
            if fn.endswith(".html") and published(rel, excludes):
                out.append(rel)
    return out


def formats(obj):
    """The normalised media types an object's encodingFormat names ('Application/JSON; charset=utf-8' -> 'application/json')."""
    v = obj.get("encodingFormat")
    vals = v if isinstance(v, list) else [v]
    return [x.split(";")[0].strip().lower() for x in vals if isinstance(x, str)]


def claims(node):
    """Yield (contentUrl, format) for every object at any depth with a contentUrl and a checked encodingFormat."""
    if isinstance(node, dict):
        if "contentUrl" in node:
            urls = node["contentUrl"] if isinstance(node["contentUrl"], list) else [node["contentUrl"]]
            for fmt in formats(node):
                if fmt in EXT:
                    for u in urls:
                        yield u, fmt
        for v in node.values():
            yield from claims(v)
    elif isinstance(node, list):
        for v in node:
            yield from claims(v)


def resolve(site_root, page_rel, url, hosts, excludes):
    """Map a contentUrl to the site-relative file Pages would serve. Returns (rel, None) or (None, reason). Never touches the network."""
    if not isinstance(url, str) or not url.strip():
        return None, "contentUrl is not a non-empty string"
    u = urlsplit(url.strip())
    if u.scheme not in ("", "http", "https"):
        return None, f"scheme {u.scheme!r} is not a web URL"
    if u.netloc:
        if (u.hostname or "").lower() not in hosts:
            return None, "is on another host; it cannot be verified without a network request, so it is not accepted"
        path = u.path or "/"
    elif u.path.startswith("/"):
        path = u.path
    else:
        path = posixpath.join(posixpath.dirname("/" + page_rel), u.path)  # page-relative
    path = unquote(path)
    if "\\" in path or "\x00" in path:
        return None, "path has a backslash or NUL"
    norm = posixpath.normpath(path)
    segs = [s for s in path.split("/") if s not in ("", ".")]
    depth = 0
    for s in segs:
        depth += -1 if s == ".." else 1
        if depth < 0:
            return None, "path climbs above the site root"
    rel = norm.lstrip("/")
    full = os.path.join(site_root, *rel.split("/")) if rel else site_root
    if path.endswith("/") or rel == "" or os.path.isdir(full):
        return None, "is a directory URL; Pages serves its index.html (text/html) there, or a 404"
    if not published(rel, excludes):
        return None, f"{rel} is not published by Pages (excluded, or a dot or underscore path)"
    if not os.path.isfile(full):
        return None, f"no such file: {rel} (a 404)"
    return rel, None


def check(site_root=ROOT):
    """Returns (checked, problems, blocks). checked: [(page, contentUrl, format, file)]; problems: one line each; blocks: JSON-LD blocks seen."""
    site_root = os.path.abspath(site_root)
    hosts, excludes = site_hosts(site_root), jekyll_excludes(site_root)
    checked, problems, blocks = [], [], 0
    for page in html_pages(site_root, excludes):
        with open(os.path.join(site_root, *page.split("/")), "rb") as f:
            text = f.read().decode("utf-8", errors="replace")
        for i, m in enumerate(SCRIPT_RE.finditer(text), 1):
            blocks += 1
            try:
                doc = json.loads(m.group(1))
            except ValueError as e:
                problems.append(f"{page}: JSON-LD block {i} does not parse ({e}); its claims cannot be checked")
                continue
            for url, fmt in claims(doc):
                rel, why = resolve(site_root, page, url, hosts, excludes)
                if why:
                    problems.append(f"{page}: contentUrl {url!r} ({fmt}): {why}")
                    continue
                if not rel.lower().endswith(EXT[fmt]):
                    problems.append(f"{page}: contentUrl {url!r} ({fmt}): {rel} is not a {EXT[fmt]} file, so Pages does not serve it as {fmt}")
                    continue
                try:
                    with open(os.path.join(site_root, *rel.split("/")), "rb") as f:
                        PARSE[fmt](f.read())
                except (ValueError, csv.Error) as e:
                    problems.append(f"{page}: contentUrl {url!r} ({fmt}): {rel} is not valid {fmt} ({str(e)[:120]})")
                    continue
                checked.append((page, url, fmt, rel))
    return checked, problems, blocks


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--site", default=ROOT, help="site tree to check (default: this repo)")
    a = ap.parse_args(argv)
    checked, problems, blocks = check(a.site)
    for p in problems:
        print("PROBLEM", p)
    n = {fmt: sum(1 for c in checked if c[2] == fmt) for fmt in EXT}
    print(f"{blocks} JSON-LD blocks; contentUrl checked and good: {n['application/json']} application/json, {n['text/csv']} text/csv; {len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
