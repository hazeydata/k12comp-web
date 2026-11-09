"""HTML, inline SVG, CSV and JSON-LD for the NJ history. Pure functions of the derived data (data.History)."""
import csv
import html
import io
import json
import re

from . import copy as C
from . import data as D

SITE = "https://k12comp.com"
LICENSE = "https://creativecommons.org/licenses/by/4.0/"
TEMPORAL = "2019-07-01/2026-06-30"
SLUG_RE = re.compile(r"^nj/([a-z0-9-]+-(\d{7}))/index\.html$")


def esc(s):
    return html.escape(str(s), quote=True)


# ---------- CSV ----------
def csv_text(cols, rows):
    buf = io.StringIO(newline="")
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(cols)
    for r in rows:
        w.writerow([r.get(c, "") for c in cols])
    return buf.getvalue()


# ---------- coverage ----------
def coverage_block(k, n, state_link=True):
    """The district coverage block (D2, AC 11, AC 13). n == 0: not-available text, no percent, no label."""
    link = f'<p><a href="{C.S_PATH}">{esc(C.D_STATE_LINK)}</a></p>' if state_link else ""
    if n == 0:
        return f'<div class="hist-cov" data-cov-n="0"><p class="cov-line">{esc(C.NO_ROWS_COV)}</p>{link}</div>'
    line = C.D_COV.format(k=k, n=n, p=D.pct_text(k, n))
    label = f'<p class="cov-partial"><span class="partial">{esc(C.D_PARTIAL)}</span></p>' if D.is_partial(k, n) else ""
    return (f'<div class="hist-cov" data-cov-k="{k}" data-cov-n="{n}"><p class="cov-line"><strong>{esc(line)}</strong></p>'
            f'{label}<p>{esc(C.D_COV_EXPLAIN.format(k=k, n=n))}</p>{link}</div>')


# ---------- staff cells ----------
def cell_state(row):
    if row is None:
        return "missing"
    if row["suppressed"] == "true":
        return "small" if row["suppression_reason"] == "n_lt_10" else "comp"
    return "published"


STATE_TEXT = {"small": C.STATUS_SMALL, "comp": C.STATUS_COMP, "missing": C.MISSING, "published": C.STATUS_PUBLISHED}


def group_cells(hist, leaid, group):
    return [(y, hist.by_leaid.get(leaid, {}).get(y, {}).get(group)) for y in D.WINDOW]


# ---------- SVG panel (dataviz design: time down, FTE across, dots joined only across consecutive published years) ----------
W, ROW, TOP, X0, PW = 300, 34, 6, 62, 148
LABEL_X = X0 + PW + 14  # value labels sit in a column right of every dot, so no connector can reach a label


def wrap(text, limit=34):
    words, lines, cur = text.split(" "), [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > limit:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}" if cur else w
    lines.append(cur)
    return lines


def panel_svg(uid, district, group, cells):
    label = C.GROUP_LABELS[group]
    vals = [float(r["fte_sum"]) for _, r in cells if r is not None and r["suppressed"] == "false"]
    m = max(vals) or 1.0
    height = TOP * 2 + ROW * len(cells)
    out = [f'<svg class="hist-svg" viewBox="0 0 {W} {height}" role="img" aria-labelledby="{uid}-t" focusable="false">',
           f'<title id="{uid}-t">{esc(label)}: published FTE by school year, {esc(district)}</title>',
           f'<line class="axis" x1="{X0}" y1="{TOP}" x2="{X0}" y2="{height - TOP}"/>']
    path, dots, texts = [], [], []
    prev = None
    for i, (y, r) in enumerate(cells):
        cy = TOP + ROW * i + ROW / 2
        st = cell_state(r)
        texts.append(f'<text class="yr num" x="0" y="{cy + 4:g}">{esc(y)}</text>')
        if st == "published":
            x = X0 + float(r["fte_sum"]) / m * PW
            dots.append(f'<circle class="dot" cx="{x:.1f}" cy="{cy:g}" r="4.5" data-year="{esc(y)}" data-group="{esc(group)}" '
                        f'data-fte="{esc(r["fte_sum"])}"/>')
            texts.append(f'<text class="val num" x="{LABEL_X}" y="{cy + 4:g}" data-year="{esc(y)}" data-group="{esc(group)}">'
                         f'{esc(D.fmt_fte(r["fte_sum"]))}</text>')
            path.append(("L" if prev == i - 1 else "M") + f"{x:.1f} {cy:g}")
            prev = i
        else:
            lines = wrap(STATE_TEXT[st])
            y0 = cy + 4 if len(lines) == 1 else cy - 3
            tsp = "".join(f'<tspan x="{X0 + 10}" y="{y0 + 14 * j:g}">{esc(t)}{" " if j < len(lines) - 1 else ""}</tspan>'
                          for j, t in enumerate(lines))
            texts.append(f'<text class="st {st}" data-year="{esc(y)}" data-group="{esc(group)}" data-status="{st}">{tsp}</text>')
    if path:
        out.append(f'<path class="ln" d="{" ".join(path)}"/>')
    out += dots + texts + ["</svg>"]
    return "".join(out)


def rowlist(group, cells):
    """Table-first list for a group with 2 or fewer published values (dataviz rule)."""
    li = []
    for y, r in cells:
        st = cell_state(r)
        val = f'<span class="num">{esc(D.fmt_fte(r["fte_sum"]))}</span>' if st == "published" else esc(STATE_TEXT[st])
        li.append(f'<li data-year="{esc(y)}" data-group="{esc(group)}" data-status="{st}"><span class="num">{esc(y)}</span> {val}</li>')
    return f'<ul class="rowlist">{"".join(li)}</ul>'


def staff_panels(hist, leaid, district):
    out = []
    for g in D.GROUPS:
        cells = group_cells(hist, leaid, g)
        n_pub = sum(1 for _, r in cells if cell_state(r) == "published")
        all_sup = all(cell_state(r) in ("small", "comp") for _, r in cells)
        uid = f"h{leaid}-{g}"
        if n_pub >= 3:
            body = panel_svg(uid, district, g, cells)
        else:
            body = (f'<p class="note">{esc(C.ALL_SUPPRESSED)}</p>' if all_sup else "") + rowlist(g, cells)
        out.append(f'<div class="hist-panel" data-group="{g}"><h4>{esc(C.GROUP_LABELS[g])}</h4>{body}</div>')
    return "".join(out)


def staff_alt(hist, leaid, district):
    sup, mis = [], []
    for g in D.GROUPS:
        cells = group_cells(hist, leaid, g)
        s = [y for y, r in cells if cell_state(r) in ("small", "comp")]
        m = [y for y, r in cells if r is None]
        if s:
            sup.append(f"{C.GROUP_LABELS[g]}, {', '.join(s)}")
        if m:
            mis.append(f"{C.GROUP_LABELS[g]}, {', '.join(m)}")
    sc = f"Suppressed values: {'; '.join(sup)}. " if sup else ""
    mc = f"{C.MISSING[0].upper()}{C.MISSING[1:]}: {'; '.join(mis)}. " if mis else ""
    return C.STAFF_ALT.format(district=district, first=D.WINDOW[0], last=D.WINDOW[-1], suppressed=sc, missing=mc)


def staff_table(hist, leaid, cap_id):
    rows = []
    for y in D.WINDOW:
        for g in D.GROUPS:
            r = hist.by_leaid.get(leaid, {}).get(y, {}).get(g)
            st = cell_state(r)
            val = esc(D.fmt_fte(r["fte_sum"])) if st == "published" else ""
            rows.append(f'<tr data-year="{y}" data-group="{g}" data-status="{st}"><th scope="row">{y}</th>'
                        f'<td>{esc(C.GROUP_LABELS[g])}</td><td class="num">{val}</td><td>{esc(STATE_TEXT[st])}</td></tr>')
    heads = "".join(f'<th scope="col"{" class=\"num\"" if i == 2 else ""}>{esc(h)}</th>' for i, h in enumerate(C.TABLE_HEADS))
    return (f'<details class="hist-table"><summary>{esc(C.TABLE_TOGGLE)}</summary>'
            f'<table class="hist-data" aria-labelledby="{cap_id}"><thead><tr>{heads}</tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></details>')


def status_key():
    return ('<div class="hist-key"><ul class="key">'
            f'<li>{esc(C.STATUS_SMALL)}</li><li>{esc(C.STATUS_COMP)}</li><li>{esc(C.MISSING)}</li></ul>'
            f'<p>{esc(C.SUPPRESSED_EXPLAIN)}</p><p>{esc(C.MISSING_EXPLAIN)}</p></div>')


# ---------- credits ----------
def link(url, text=None):
    return f'<a href="{esc(url)}">{esc(text or url)}</a>'


def staff_credits(manifest):
    li = []
    for y in D.WINDOW:
        m = manifest[y]
        pre = C.CREDIT_NJDOE.format(year=y, date=D.local_date(m["retrieved_at"]), url="\0")
        a, b = pre.split("\0")
        li.append(f"<li>{esc(a)}{link(m['url'])}{esc(b)}</li>")
    return f'<ul class="credits">{"".join(li)}</ul>'


def guide_source_groups(hist, leaids):
    """[(leaid, sha, source dict, [years])] in district-name order; years are the counted guide years."""
    out = []
    for l in sorted(leaids, key=lambda x: (hist.district_names[x].lower(), x)):
        ys = hist.cov[l]["guide_years"]
        by = {}
        for y in ys:
            for s in hist.guide_sources[l][y]:
                by.setdefault(s["sha256"], [s, []])[1].append(y)
        for sha in sorted(by, key=lambda h: (by[h][1][0], h)):
            out.append((l, sha, by[sha][0], by[sha][1]))
    return out


def guide_credits(hist, leaids, page_paths, local):
    li = []
    for l, sha, s, years in guide_source_groups(hist, leaids):
        date = D.local_date(s["retrieved_at"])
        base = "" if local else page_paths[l]
        if s["source_type"] == "opra_response" and s.get("citation"):
            anchor = f"{base}#src-{sha[:12]}"
            li.append(f'<li><a href="{esc(anchor)}">{esc(s["citation"])}</a><br>'
                      f'{esc(C.CREDIT_DATA_YEARS.format(years=", ".join(years), date=date))}</li>')
        elif s.get("source_url", "") and s["source_url"].startswith("https://"):
            if D.is_perc_url(s["source_url"]):
                pre = C.CREDIT_PERC.format(year=", ".join(years), date=date, url="\0")
            else:
                pre = C.CREDIT_CONTRACT.format(years=", ".join(years), date=date, url="\0")
            a, b = pre.split("\0")
            li.append(f"<li>{esc(a)}{link(s['source_url'])}{esc(b)}</li>")
        else:
            raise D.BuildError(f"guide source for {l} {years} has no OPRA citation or public https url")
    return f'<ul class="credits">{"".join(li)}</ul>' if li else ""


# ---------- JSON-LD ----------
def dataset_jsonld(name, description, content_url, based_on):
    ds = {"@context": "https://schema.org", "@type": "Dataset", "name": name, "description": description,
          "license": LICENSE, "temporalCoverage": TEMPORAL,
          "creator": {"@type": "Organization", "name": "K12 Comp (hazeydata)"},
          "distribution": {"@type": "DataDownload", "contentUrl": content_url, "encodingFormat": "text/csv"},
          "isBasedOn": based_on}
    body = json.dumps(ds, sort_keys=True, ensure_ascii=True).replace("</", "<\\/")
    return f'<script type="application/ld+json" id="ld-nj-history">{body}</script>'


def based_on(hist, leaids):
    urls = [hist.manifest[y]["url"] for y in D.WINDOW]
    pub = sorted({s["source_url"] for l, _, s, _ in guide_source_groups(hist, leaids)
                  if (s.get("source_url") or "").startswith("https://")})
    return urls + pub


# ---------- district section ----------
DL = {"district": "/data/nj/history/{leaid}.csv", "all": "/data/nj/nj-district-staff-history.csv",
      "cov": "/data/nj/nj-history-coverage.csv"}


def downloads(leaid, with_district):
    li = []
    if with_district:
        li.append(f'<li><a href="{DL["district"].format(leaid=leaid)}">{esc(C.DL_DISTRICT)}</a></li>')
    li.append(f'<li><a href="{DL["all"]}">{esc(C.DL_ALL)}</a></li>')
    li.append(f'<li><a href="{DL["cov"]}">{esc(C.DL_COV)}</a></li>')
    return f'<ul class="hist-dl">{"".join(li)}</ul>'


def guide_slot(hist, leaid, district):
    ys = hist.cov[leaid]["guide_years"]
    if not ys:
        return ""
    links = "".join(f'<li><a href="#guide-teacher-{y}">{esc(C.GUIDE_YEAR_LINK.format(school_year=y))}</a></li>' for y in ys)
    alt = C.GUIDE_ALT.format(district=district, years=", ".join(ys))
    return (f'<div class="hist-guide" data-guide-years="{",".join(ys)}"><h3>{esc(C.GUIDE_LABEL)}</h3>'
            f'<p>{esc(C.GUIDE_EXPLAIN)}</p>'
            f'<figure role="group" aria-label="{esc(alt)}"><ul class="guide-years">{links}</ul>'
            f'<figcaption>{esc(C.GUIDE_CAPTION.format(district=district))}</figcaption></figure>'
            f'<h3>{esc(C.S_GUIDE_CREDITS)}</h3>{guide_credits(hist, [leaid], {}, True)}</div>')


def district_section(hist, leaid):
    district = hist.district_names[leaid]
    c = hist.cov[leaid]
    head = (f'<link rel="stylesheet" href="/history.css"><h2 id="{C.D_ANCHOR}">{esc(C.D_HEADING)}</h2>'
            f'<p>{esc(C.D_INTRO)}</p>')
    if c["n"] == 0:
        body = (f'<p class="hist-empty">{esc(C.NO_ROWS)}</p>{coverage_block(0, 0)}{downloads(leaid, False)}'
                f'<p class="note">{esc(C.AS_IS)}</p>')
        return f'<section class="nj-hist" data-nj-history="district" data-leaid="{leaid}" aria-labelledby="{C.D_ANCHOR}">{head}{body}</section>'
    cap_id = f"cap-{leaid}"
    cap = C.STAFF_CAPTION.format(district=district, first=D.WINDOW[0], last=D.WINDOW[-1])
    alt = staff_alt(hist, leaid, district)
    staff = (f'<div class="hist-staff"><h3>{esc(C.D_STAFF_HEAD)}</h3><p>{esc(C.D_FTE_DEF)}</p>'
             f'<figure class="hist-fig" role="group" aria-labelledby="{cap_id}" aria-describedby="alt-{leaid}">'
             f'<p id="alt-{leaid}" class="sr-only">{esc(alt)}</p>'
             f'<div class="hist-panels">{staff_panels(hist, leaid, district)}</div>'
             f'<p class="note">{esc(C.CHART_SCALE_NOTE)}</p>'
             f'<figcaption id="{cap_id}">{esc(cap)}</figcaption></figure>{status_key()}{staff_table(hist, leaid, cap_id)}</div>')
    credits = (f'<h3>{esc(C.S_STAFF_CREDITS)}</h3>{staff_credits(hist.manifest)}')
    body = (f'<div class="hist-main">{coverage_block(c["k"], c["n"])}<div class="hist-chart">{staff}</div></div>'
            f'{guide_slot(hist, leaid, district)}{credits}<p class="note">{esc(C.AS_IS)}</p>{downloads(leaid, True)}')
    return f'<section class="nj-hist" data-nj-history="district" data-leaid="{leaid}" aria-labelledby="{C.D_ANCHOR}">{head}{body}</section>'


def district_jsonld(hist, leaid):
    d = hist.district_names[leaid]
    return dataset_jsonld(
        f"{d}: NJ staff FTE history and salary-guide years, {D.WINDOW[0]} to {D.WINDOW[-1]}",
        f"NJDOE published certificated-staff FTE by staff group for {d}, {D.WINDOW[0]} to {D.WINDOW[-1]}, with suppressed "
        "values left empty, and salary-guide coverage. Values as published; no estimates.",
        f"{SITE}/data/nj/history/{leaid}.csv", based_on(hist, [leaid] if leaid in hist.guide_sources else []))


# ---------- statewide page ----------
def state_coverage_snapshot(hist):
    a = hist.state_rows[-1]
    w, t = int(a["with_salary_guide"]), int(a["district_years"])
    tail = f": {C.D_PARTIAL}." if D.is_partial(w, t) else "."
    return C.S_COV_SNAP.format(date=hist.lock["snapshot_date"], w=f"{w:,}", t=f"{t:,}", p=D.pct_text(w, t), tail=tail)


def state_cov_table(hist):
    heads = "".join(f'<th role="columnheader" scope="col">{esc(h)}</th>' for h in C.S_COV_HEADS)
    rows = []
    for r in hist.state_rows:
        w, t = int(r["with_salary_guide"]), int(r["district_years"])
        name = C.S_ALL_LABEL if r["school_year"] == "ALL" else r["school_year"]
        note = C.D_PARTIAL if D.is_partial(w, t) else ""
        rows.append(f'<tr role="row" data-year="{r["school_year"]}"><th role="rowheader" scope="row" data-label="{esc(C.S_COV_HEADS[0])}">{esc(name)}</th>'
                    f'<td role="cell" class="num" data-label="{esc(C.S_COV_HEADS[1])}">{t:,}</td>'
                    f'<td role="cell" class="num" data-label="{esc(C.S_COV_HEADS[2])}">{w:,}</td>'
                    f'<td role="cell" class="num" data-label="{esc(C.S_COV_HEADS[3])}">{D.pct_text(w, t)}%</td>'
                    f'<td role="cell" data-label="{esc(C.S_COV_HEADS[4])}">{esc(note)}</td></tr>')
    return (f'<table class="hist-data stack" id="coverage-table" role="table"><caption>{esc(C.S_COV_CAPTION)}</caption>'
            f'<thead role="rowgroup"><tr role="row">{heads}</tr></thead><tbody role="rowgroup">{"".join(rows)}</tbody></table>')


def state_rows_table(hist):
    heads = "".join(f'<th scope="col"{" class=\"num\"" if i >= 2 else ""}>{esc(h)}</th>' for i, h in enumerate(C.S_ROWS_HEADS))
    rows = []
    for y in D.WINDOW:
        for g in D.GROUPS:
            p, s = hist.group_counts[(y, g)]
            rows.append(f'<tr data-year="{y}" data-group="{g}"><th scope="row">{y}</th><td>{esc(C.GROUP_LABELS[g])}</td>'
                        f'<td class="num">{p:,}</td><td class="num">{s:,}</td></tr>')
    return (f'<table class="hist-data" id="row-count-table"><caption>{esc(C.S_ROWS_CAPTION)}</caption>'
            f'<thead><tr>{heads}</tr></thead><tbody>{"".join(rows)}</tbody></table>')


def statewide_main(hist, page_paths):
    guide_l = sorted((l for l, c in hist.cov.items() if c["k"]), key=lambda l: (hist.district_names[l].lower(), l))
    li = "".join(f'<li><a href="{page_paths[l]}">{esc(hist.district_names[l])}</a> · {esc(", ".join(hist.cov[l]["guide_years"]))}</li>'
                 for l in guide_l)
    a = hist.state_rows[-1]
    return (
        f'<link rel="stylesheet" href="/history.css">'
        f'<nav aria-label="Breadcrumb" class="crumbs"><a href="/nj/">Districts</a> / <span aria-current="page">{esc(C.S_H1)}</span></nav>'
        f'<div class="nj-hist" data-nj-history="statewide">'
        f'<h1 id="{C.S_H1_ANCHOR}">{esc(C.S_H1)}</h1><p>{esc(C.S_INTRO)}</p>'
        f'<p><a class="browse" href="/nj/">{esc(C.S_BROWSE)}</a></p>'
        f'<section aria-labelledby="{C.S_COV_ANCHOR}"><h2 id="{C.S_COV_ANCHOR}">{esc(C.S_COV_HEAD)}</h2>'
        f'<p class="cov-line" data-cov-k="{a["with_salary_guide"]}" data-cov-n="{a["district_years"]}"><strong>{esc(state_coverage_snapshot(hist))}</strong></p>'
        f'<p>{esc(C.S_COV_DEF)}</p>{state_cov_table(hist)}</section>'
        f'<section aria-labelledby="{C.S_ROWS_ANCHOR}"><h2 id="{C.S_ROWS_ANCHOR}">{esc(C.S_ROWS_HEAD)}</h2>'
        f'<p>{esc(C.S_ROWS_INTRO)}</p>{state_rows_table(hist)}</section>'
        f'<section aria-labelledby="{C.S_GUIDES_ANCHOR}"><h2 id="{C.S_GUIDES_ANCHOR}">{esc(C.S_GUIDES_HEAD)}</h2>'
        f'<p>{esc(C.S_GUIDES_INTRO)}</p><ul class="guide-districts">{li}</ul></section>'
        f'<section aria-labelledby="{C.S_DL_ANCHOR}"><h2 id="{C.S_DL_ANCHOR}">{esc(C.S_DL_HEAD)}</h2>'
        f'<ul class="hist-dl"><li><a href="{DL["all"]}">{esc(C.DL_ALL)}</a></li>'
        f'<li><a href="{DL["cov"]}">{esc(C.DL_COV)}</a></li></ul></section>'
        f'<section aria-labelledby="{C.S_CREDITS_ANCHOR}"><h2 id="{C.S_CREDITS_ANCHOR}">{esc(C.S_CREDITS_HEAD)}</h2>'
        f'<h3>{esc(C.S_STAFF_CREDITS)}</h3>{staff_credits(hist.manifest)}'
        f'<h3>{esc(C.S_GUIDE_CREDITS)}</h3>{guide_credits(hist, guide_l, page_paths, False)}'
        f'<p class="note">{esc(C.AS_IS)}</p></section></div>')


def statewide_jsonld(hist):
    guide_l = [l for l, c in hist.cov.items() if c["k"]]
    return dataset_jsonld(
        f"New Jersey staff FTE history and salary-guide coverage, {D.WINDOW[0]} to {D.WINDOW[-1]}",
        "NJDOE published certificated-staff FTE by district, school year and staff group, with suppressed values left "
        "empty, and statewide teacher salary-guide coverage. Values as published; no estimates.",
        f"{SITE}/data/nj/nj-district-staff-history.csv", based_on(hist, guide_l))


# ---------- about / llms ----------
def about_section():
    paras = "".join(f"<p>{esc(p)}</p>" for p in C.A_PARAS)
    return (f'<h2 id="{C.A_ANCHOR}">{esc(C.A_HEAD)}</h2>{paras}'
            f'<p><a href="{C.S_PATH}">{esc(C.A_LINK)}</a></p>'
            f'<p><a href="{C.S_PATH}">{esc(C.LINK_LABEL)}</a></p><p class="note">{esc(C.AS_IS)}</p>')


def nj_link():
    return f'<p class="hist-link"><a href="{C.S_PATH}">{esc(C.LINK_LABEL)}</a></p>'
