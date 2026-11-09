"""Add-on post-build step (OQ-1): copies the site tree to an output directory and adds the NJ history.

Existing pages are only ever added to (section, Dataset block, links, guide-table ids); no generator runs.
Output is deterministic: two runs from the same pin and tree are byte-identical.
"""
import json
import os
import re
import shutil

from . import copy as C
from . import data as D
from . import render as R

SKIP_DIRS = {".git", "__pycache__", "node_modules", ".pytest_cache", ".venv"}
NEWSLETTER_RE = re.compile(r'<section class="newsletter" data-slot="newsletter".*?</section>', re.S)


def read_text(path):
    with open(path, "rb") as f:
        return f.read().decode("utf-8")


def write_text(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(text.encode("utf-8"))


def discover_pages(site_root):
    pages = {}
    nj = os.path.join(site_root, "nj")
    for slug in sorted(os.listdir(nj)):
        m = re.fullmatch(r"([a-z0-9-]+)-(\d{7})", slug)
        if m and os.path.exists(os.path.join(nj, slug, "index.html")):
            pages[m.group(2)] = f"/nj/{slug}/"
    return pages


def copy_tree(site_root, out_dir):
    site_root, out_dir = os.path.abspath(site_root), os.path.abspath(out_dir)

    def ignore(d, names):
        skip = {n for n in names if n in SKIP_DIRS}
        skip |= {n for n in names if os.path.abspath(os.path.join(d, n)) == out_dir}
        return skip
    shutil.copytree(site_root, out_dir, ignore=ignore, copy_function=shutil.copyfile)


def add_guide_anchors(page, leaid, years):
    for y in years:
        old = f'<section class="grid teacher"><h3>Teacher salary guide, {y}'
        if old not in page:
            raise D.BuildError(f"{leaid}: no teacher guide table for {y} to link to")
        page = page.replace(old, f'<section class="grid teacher" id="guide-teacher-{y}"><h3>Teacher salary guide, {y}', 1)
    return page


def edit_district(page, hist, leaid):
    if f'id="{C.D_ANCHOR}"' in page or 'id="ld-nj-history"' in page:
        raise D.BuildError(f"{leaid}: page already carries the history section (not a fresh tree)")
    sec = R.district_section(hist, leaid)
    for marker in ('<section class="newsletter" data-slot="newsletter"', '<section aria-labelledby="dl">'):
        if marker in page:
            page = page.replace(marker, sec + marker, 1)
            break
    else:
        raise D.BuildError(f"{leaid}: no insertion point for the history section")
    page = add_guide_anchors(page, leaid, hist.cov[leaid]["guide_years"])
    if hist.cov[leaid]["n"]:
        if "</head>" not in page:
            raise D.BuildError(f"{leaid}: no </head>")
        page = page.replace("</head>", R.district_jsonld(hist, leaid) + "</head>", 1)
    return page


def statewide_page(nj_index, newsletter, hist, page_paths):
    cut = nj_index.index('<main id="main">')
    head, tail = nj_index[:cut], nj_index[nj_index.index("</main>"):]
    head = re.sub(r'<script type="application/ld\+json">.*?</script>', "", head, count=1, flags=re.S)
    e = R.esc
    for pat, val in ((r"<title>.*?</title>", f"<title>{e(C.S_TITLE)}</title>"),
                     (r'<meta name="description" content="[^"]*">', f'<meta name="description" content="{e(C.S_DESC)}">'),
                     (r'<meta property="og:title" content="[^"]*">', f'<meta property="og:title" content="{e(C.S_TITLE)}">'),
                     (r'<meta property="og:description" content="[^"]*">', f'<meta property="og:description" content="{e(C.S_DESC)}">'),
                     (r'<link rel="canonical" href="[^"]*">', f'<link rel="canonical" href="{R.SITE}{C.S_PATH}">'),
                     (r'<meta property="og:url" content="[^"]*">', f'<meta property="og:url" content="{R.SITE}{C.S_PATH}">')):
        head, n = re.subn(pat, lambda _m, v=val: v, head, count=1)
        if n != 1:
            raise D.BuildError(f"/nj/ head lacks {pat[:30]}")
    head = head.replace("</head>", R.statewide_jsonld(hist) + "</head>", 1)
    # head and body prefix are taken from /nj/ so parity (GoatCounter, fonts, favicon, og, header) holds by construction
    return head + '<main id="main">' + R.statewide_main(hist, page_paths) + newsletter + tail


def build(site_root, out_dir, hist, page_paths, nj_index_path=None):
    """hist: a data.History. Returns a small report dict."""
    if os.path.exists(out_dir) and os.listdir(out_dir):
        raise D.BuildError("output directory is not empty")
    copy_tree(site_root, out_dir)
    rep = {"district_pages": 0, "district_pages_with_rows": 0}
    newsletter = None
    for leaid, path in page_paths.items():
        f = os.path.join(out_dir, *path.strip("/").split("/"), "index.html")
        page = read_text(f)
        if newsletter is None:
            m = NEWSLETTER_RE.search(page)
            newsletter = m.group(0) if m else None
        page = edit_district(page, hist, leaid)
        write_text(f, page)
        rep["district_pages"] += 1
        rep["district_pages_with_rows"] += 1 if hist.cov[leaid]["n"] else 0
    if newsletter is None:
        raise D.BuildError("no newsletter section found on any district page")
    # /nj/ (link), /about/ (methodology section)
    nj_f = os.path.join(out_dir, "nj", "index.html")
    nj = read_text(nj_f)
    nj, n = re.subn(r'(<p class="disclaimer">.*?</p>)', lambda m: m.group(1) + R.nj_link(), nj, count=1, flags=re.S)
    if n != 1:
        raise D.BuildError("/nj/ has no disclaimer paragraph to anchor the history link")
    write_text(nj_f, nj)
    ab_f = os.path.join(out_dir, "about", "index.html")
    ab = read_text(ab_f)
    if "</main>" not in ab or f'id="{C.A_ANCHOR}"' in ab:
        raise D.BuildError("/about/ is not a fresh page")
    write_text(ab_f, ab.replace("</main>", R.about_section() + "</main>", 1))
    # statewide page
    sw_dir = os.path.join(out_dir, "nj", "history")
    if os.path.exists(sw_dir):
        raise D.BuildError("/nj/history/ already exists in the tree")
    nj_orig = read_text(nj_index_path or os.path.join(site_root, "nj", "index.html"))
    write_text(os.path.join(sw_dir, "index.html"), statewide_page(nj_orig, newsletter, hist, page_paths))
    # css
    with open(os.path.join(D.HERE, "history.css"), "rb") as f:
        css = f.read()
    with open(os.path.join(out_dir, "history.css"), "wb") as f:
        f.write(css)
    # CSVs
    dd = os.path.join(out_dir, "data", "nj")
    write_text(os.path.join(dd, "nj-district-staff-history.csv"), R.csv_text(D.STAFF_PUB_COLS, hist.rows))
    write_text(os.path.join(dd, "nj-history-coverage.csv"), R.csv_text(D.COVERAGE_COLS, hist.state_rows))
    n_csv = 0
    for leaid in page_paths:
        rows = hist.district_rows(leaid)
        if not hist.cov[leaid]["n"]:
            continue
        write_text(os.path.join(dd, "history", f"{leaid}.csv"),
                   R.csv_text(D.DISTRICT_FILE_COLS, rows + [hist.district_coverage_row(leaid)]))
        n_csv += 1
    rep["district_csvs"] = n_csv
    # sitemap, llms.txt
    sm_f = os.path.join(out_dir, "sitemap.xml")
    sm = read_text(sm_f)
    entry = f'<url><loc>{R.SITE}{C.S_PATH}</loc><lastmod>{hist.lock["snapshot_date"]}</lastmod></url>\n'
    if "</urlset>" not in sm or C.S_PATH in sm:
        raise D.BuildError("sitemap is not a fresh sitemap")
    write_text(sm_f, sm.replace("</urlset>", entry + "</urlset>", 1))
    ll_f = os.path.join(out_dir, "llms.txt")
    ll = read_text(ll_f)
    if ll and not ll.endswith("\n"):
        ll += "\n"
    write_text(ll_f, ll + "".join(line + "\n" for line in C.LLMS_LINES))
    rep["coverage_state"] = hist.state_rows
    rep["crosscheck"] = hist.crosscheck
    rep["staff_rows"] = len(hist.rows)
    return rep


def run(site_root, out_dir, data_repo=None, fixture_dir=None, names_dir=None, lock_path=None, report_path=None):
    lock = D.load_lock(lock_path)
    inputs = D.Inputs(lock, repo=data_repo, fixture_dir=fixture_dir)
    verify_names = names_dir is None or fixture_dir is None
    district_names, staff_names = D.load_names(names_dir or D.HERE, lock, verify=verify_names)
    page_paths = discover_pages(site_root)
    missing = [l for l in page_paths if l not in district_names]
    if missing:
        raise D.BuildError(f"no display name for district pages: {missing[:5]}")
    hist = D.History(inputs, site_root, district_names, staff_names, page_paths, lock)
    rep = build(site_root, out_dir, hist, page_paths)
    rep["inputs_read"] = sorted(set(inputs.reads))
    if report_path:
        write_text(report_path, json.dumps(rep, indent=2, sort_keys=True) + "\n")
    return rep
