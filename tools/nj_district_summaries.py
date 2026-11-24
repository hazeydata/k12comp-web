#!/usr/bin/env python3
"""K12-DISTRICT-SUMMARIES-001: one data-derived summary paragraph on every NJ district page (stdlib only). See docs/nj-district-summaries.md.

Each district page nj/<slug>-<leaid>/index.html gets exactly one <p class="district-summary" id="district-summary">...</p> in <main>, directly
after <p class="disclaimer">...</p>. The text is built from that district's committed data only: api/v1/nj/<leaid>.json, data/nj/history/<leaid>.csv
and the page itself (h1, breadcrumb county, the "Latest base salary" block, the "Starts at" note). All English strings live in
tools/nj_district_summaries_copy.json (one key per slot S0, S0b, S1, S2, S3, SH, S4, S5, S5_one); this file holds none.

Run after the history build and the existing rewrites, before tools/nj_indexing.py. Each page is first stripped of its own paragraph, then the
paragraph is inserted, so a second run changes no byte.

    python3 tools/nj_district_summaries.py [site] --check          # exit 1 if any district page is not in its final form
    python3 tools/nj_district_summaries.py [site] --write          # rewrite in place; the default
    python3 tools/nj_district_summaries.py [site] --trace out.json # also write a trace (outside the site): token -> source file + path + rendered string
"""
import argparse
import csv
import html
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COPY = os.path.join(ROOT, "tools", "nj_district_summaries_copy.json")
SLOTS = ("S0", "S0b", "S1", "S2", "S3", "SH", "S4", "S5", "S5_one")
DISTRICT = re.compile(r"nj/([a-z0-9-]+-(\d{7}))/index\.html")
PARA = re.compile(r'<p class="district-summary" id="district-summary">.*?</p>', re.S)
DISCLAIMER = re.compile(r'<p class="disclaimer">.*?</p>', re.S)
H1 = re.compile(r"<h1>(.*?)</h1>")
CRUMB_COUNTY = re.compile(r'<nav aria-label="Breadcrumb" class="crumbs"><a href="/nj/">[^<]*</a> / <a href="/nj/county/[a-z0-9-]+/">([^<]*)</a> / ')
NJ_ROW = re.compile(r'<tr><th scope="row"><a href="/nj/[a-z0-9-]+-(\d{7})/">[^<]*</a></th><td>([^<]*)</td>')
LATEST_LABEL = re.compile(r'<h2 id="latest" class="label">Latest base salary · ([^<]*)</h2>')
BIG = re.compile(r'<p class="big num">([^<]*)</p>')
SUMMARY_SOURCE = re.compile(r'<p class="source">.*?, row (\d+)</p>', re.S)
STARTS_AT = re.compile(r'Starts at <span class="num">([^<]*)</span> in (\d{4}-\d\d)')
NUMBER = re.compile(r"\d{4}-\d\d-\d\d|\d{4}-\d\d|\$?\d{1,3}(?:,\d{3})+(?:\.\d+)?|\$?\d+(?:\.\d+)?")


class SummaryError(ValueError):
    pass


def read(path):
    with open(path, encoding="utf-8", newline="") as fh:
        return fh.read()


def write(path, text):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def load_copy(path=None):
    copy = json.loads(read(path or COPY))
    missing = [k for k in SLOTS + ("max_words", "_status") if k not in copy]
    if missing or set(copy["_status"]) != set(SLOTS):
        raise SummaryError(f"copy-file keys {missing}")
    return copy


def money(s):
    """'263750' -> '$263,750' (the page's own format)."""
    return "${:,}".format(int(s))


def fmt_fte(s):
    """The FTE section's format (tools/nj_history/data.py fmt_fte): the CSV string, plus a thousands comma."""
    whole, dec = s.split(".")
    return f"{int(whole):,}.{dec}"


def strip(page):
    return PARA.sub("", page)


def district_files(site):
    out = []
    base = os.path.join(site, "nj")
    for name in sorted(os.listdir(base)):
        m = DISTRICT.fullmatch(f"nj/{name}/index.html")
        if m and os.path.isfile(os.path.join(base, name, "index.html")):
            out.append((f"nj/{name}/index.html", m.group(2)))
    return out


def county_table(site):
    """{leaid: county} from the /nj/ table; used only while a page's breadcrumb has no county yet (before nj_indexing runs)."""
    return {m.group(1): html.unescape(m.group(2)) for m in NJ_ROW.finditer(read(os.path.join(site, "nj", "index.html")))}


def history_rows(site, leaid):
    p = os.path.join(site, "data", "nj", "history", leaid + ".csv")
    if not os.path.isfile(p):
        return []
    with open(p, encoding="utf-8", newline="") as fh:
        return [(n, r) for n, r in enumerate(csv.DictReader(fh), 2)]


class Rec:
    """One traceable rendered value: its text, where it comes from."""

    def __init__(self, text, source, path):
        self.text, self.source, self.path = text, source, path


def pick(cands, what, leaid):
    if not cands:
        raise SummaryError(f"{leaid} {what} none")
    return cands[0]


def build(page, doc, hist, county_fallback, leaid):
    """page: the page without our paragraph. Returns [(slot, sentence text (unescaped), [Rec])] in slot order."""
    copy = load_copy()
    api = f"api/v1/nj/{leaid}.json"
    h1 = [html.unescape(x) for x in H1.findall(page)]
    if h1 != [doc["district"]] or doc["nces_leaid"] != leaid:
        raise SummaryError(f"{leaid} h1/district")
    m = CRUMB_COUNTY.search(page)
    county = html.unescape(m.group(1)) if m else county_fallback
    if not county:
        raise SummaryError(f"{leaid} county")
    name_rec = Rec(doc["district"], api, "district")
    county_rec = Rec(county, f"nj/{leaid}", "breadcrumb county")
    rows = doc["superintendent_contracts"]
    sal = [(i, r) for i, r in enumerate(rows) if not r["salary_not_reported"] and r["base_salary"] not in ("", None)]
    out = []

    def add(slot, **fields):
        # fields: name -> Rec
        text = copy[slot].format(**{k: v.text for k, v in fields.items()})
        out.append((slot, text, list(fields.values())))

    def rec(i, field, text=None):
        return Rec(rows[i][field] if text is None else text, api, f"superintendent_contracts[{i}].{field}")

    if sal:
        years = sorted({r["salary_year"] for _, r in sal})
        latest = [(i, r) for i, r in sal if r["salary_year"] == years[-1]]
        label, big = LATEST_LABEL.search(page), BIG.search(page)
        if not label or not big:
            raise SummaryError(f"{leaid} latest block")
        if big.group(1).startswith("$"):
            # the block shows a reported figure: it must be the latest reported year, and names the row on multi-row districts
            if label.group(1) != years[-1]:
                raise SummaryError(f"{leaid} latest label")
            cand = [(i, r) for i, r in latest if money(r["base_salary"]) == big.group(1)]
        else:
            cand = latest  # the block shows a newer "Not reported" row: S1 states the latest reported year, which History lists
        if len(cand) > 1:
            src = SUMMARY_SOURCE.search(page)
            cand = [(i, r) for i, r in cand if src and r["page_ref"] == "row " + src.group(1)] or cand
        li, lr = pick(cand, "latest row", leaid)
        add("S1", district=name_rec, county=county_rec, base_salary=rec(li, "base_salary", money(lr["base_salary"])),
            salary_year=rec(li, "salary_year"))
        if len(years) >= 2:
            first = [(i, r) for i, r in sal if r["salary_year"] == years[0]]
            note = STARTS_AT.search(page)
            if not note or note.group(2) != years[0]:
                raise SummaryError(f"{leaid} starts-at note")
            fi, fr = pick([(i, r) for i, r in first if money(r["base_salary"]) == note.group(1)], "earliest row", leaid)
            add("S2", base_salary=rec(fi, "base_salary", money(fr["base_salary"])), salary_year=rec(fi, "salary_year"))
        if (not lr["term_ends_before_year"] and lr["contract_start"] and lr["contract_end"]
                and lr["ufb_work_days"] not in ("", "0", None)):
            add("S3", contract_start=rec(li, "contract_start"), contract_end=rec(li, "contract_end"), ufb_work_days=rec(li, "ufb_work_days"))
        if any(r["ufb_shared"] == "Y" for _, r in latest):
            add("SH")
    else:
        add("S0", district=name_rec, county=county_rec)
    if hist:
        yrs = sorted({r["school_year"] for _, r in hist if r["school_year"] not in ("", "ALL")})
        t = [(n, r) for n, r in hist if yrs and r["school_year"] == yrs[-1] and r["staff_group"] == "teacher"]
        if len(t) > 1:
            raise SummaryError(f"{leaid} teacher rows")
        if t and t[0][1]["suppressed"] != "true" and t[0][1]["fte_sum"] not in ("", None) and float(t[0][1]["fte_sum"]) > 0:
            n, r = t[0]
            src = f"data/nj/history/{leaid}.csv"
            add("S4", fte_sum=Rec(fmt_fte(r["fte_sum"]), src, f"row {n} fte_sum"), school_year=Rec(r["school_year"], src, f"row {n} school_year"))
    if doc["salary_cells"]:
        n = len({c["school_year"] for c in doc["salary_cells"]})
        if n == 1:
            add("S5_one")
        else:
            add("S5", n_guide_years=Rec(str(n), api, "FORMULA count(distinct salary_cells[*].school_year)"))
    if not sal and not any(s == "S4" for s, _, _ in out):
        out.append(("S0b", copy["S0b"], []))
    order = {s: i for i, s in enumerate(("S0", "S1", "S2", "S3", "SH", "S4", "S0b", "S5", "S5_one"))}
    # the spec order: salary pages S1 S2 S3 SH S4 S5; no-salary pages S0, then S4, then S0b only when S4 is absent
    return sorted(out, key=lambda x: order[x[0]])


def trace_of(parts):
    toks = []
    for slot, text, recs in parts:
        used = set()
        for m in NUMBER.finditer(text):
            tok = m.group(0)
            for j, r in enumerate(recs):
                if j not in used and tok in NUMBER.findall(r.text):
                    used.add(j)
                    toks.append({"token": tok, "slot": slot, "source": r.source, "path": r.path, "rendered": r.text})
                    break
            else:
                raise SummaryError(f"untraced {slot} {tok}")
    return toks


def paragraph(parts):
    text = " ".join(t for _, t, _ in parts)
    return text, '<p class="district-summary" id="district-summary">' + html.escape(text, quote=True) + "</p>"


def rewrite(page, doc, hist, county_fallback, leaid):
    """The page with exactly one summary paragraph after the disclaimer. Returns (page, summary text, trace tokens)."""
    page = strip(page)
    parts = build(page, doc, hist, county_fallback, leaid)
    text, para = paragraph(parts)
    main = page.index('<main id="main">')
    ds = list(DISCLAIMER.finditer(page, main))
    if len(ds) != 1 or page.count("</main>") != 1:
        raise SummaryError(f"{leaid} disclaimer")
    end = ds[0].end()
    return page[:end] + para + page[end:], text, trace_of(parts)


def check_text(copy, leaid, text):
    if len(text.split()) > copy["max_words"]:
        raise SummaryError(f"{leaid} words")


def run(site, write_files, trace_path=None):
    copy = load_copy()
    counties = county_table(site)
    stale, trace = [], {}
    pages = district_files(site)
    for rel, leaid in pages:
        path = os.path.join(site, *rel.split("/"))
        cur = read(path)
        doc = json.loads(read(os.path.join(site, "api", "v1", "nj", leaid + ".json")))
        new, text, toks = rewrite(cur, doc, history_rows(site, leaid), counties.get(leaid), leaid)
        check_text(copy, leaid, text)
        trace[leaid] = {"page": rel, "summary": text, "tokens": toks}
        if new != cur:
            stale.append(rel)
            if write_files:
                write(path, new)
    if trace_path:
        real = os.path.realpath(trace_path)
        if real.startswith(os.path.realpath(site) + os.sep):
            raise SummaryError("trace-in-site")
        write(trace_path, json.dumps(trace, indent=1, sort_keys=True) + "\n")
    return pages, stale


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("site", nargs="?", default=ROOT)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--check", action="store_true")
    g.add_argument("--write", action="store_true")
    ap.add_argument("--trace")
    a = ap.parse_args(argv)
    try:
        pages, stale = run(a.site, not a.check, a.trace)
    except SummaryError as e:
        print("nj_district_summaries:", e, file=sys.stderr)
        return 2
    print(f"{len(pages)} district pages, {len(stale)} {'stale' if a.check else 'rewritten'}" + "".join(f"\n  {s}" for s in stale[:30]))
    return 1 if a.check and stale else 0


if __name__ == "__main__":
    sys.exit(main())
