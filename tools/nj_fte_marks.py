"""Part-time superintendent salaries (K12-FTE-PRESENTATION-001): the marker, the badges and the notes, written from the committed JSON.

A row of api/v1/nj/<leaid>.json is marked when float(ufb_fte) < 1 and its salary is reported (not "Not reported ($0 in source)"). `{fte}` is
always the `ufb_fte` string as published ("0.2", "0", "0.0"); a row at FTE 0 or 0.0 uses the "reported as" wording, every other marked row the
"part-time" wording. Salaries are never scaled, imputed or recomputed, and no value is derived from them: every number that was on a page or
chart stays byte for byte, and the only new number is the FTE as published. Names, the shared-service partner and the free-text UFB fields
are never read. Rows below 1 FTE with no reported salary draw no dot and get nothing.

It edits the committed tree in place (the history build still writes the old pages, so re-run `--write` after copying a fresh build over it;
tests/test_nj_history_committed.py allows exactly this rewrite, `rewrite_*`, on these files and nothing wider):
  - charts/d/<leaid>-desktop.svg, the 44 districts with a marked dot: hollow dots (`class="pt" data-fte`), polylines re-cut so a segment joins
    only two full-time dots or two part-time dots at the same numeric FTE, and the key (`Part-time`, or `Under 1.0 FTE` when a marked dot is FTE
    0 or 0.0). The rule and the key placement are the ones in tools/nj_mobile_chart_fit.py, whose `--write` carries them to the mobile twin.
    The <style> block, grid, labels, dot positions and value labels are unchanged;
  - nj/<slug>-<leaid>/index.html of those 44 districts: the figcaption and the img alt (kept identical) get the per-value suffix and the closing
    sentence, `#fte-chart-note` follows the chart, a #latest note follows p.big when the latest row is marked, each marked #history row gets a
    badge paragraph after p.hmeta (merged into the "Term ended" paragraph when it has one), and `#fte-note` follows `#term-note`, else ol.history;
  - nj/index.html: a badge in each marked "Latest reported base salary" cell, `#fte-nj-note` after the histogram figure, and the suffix on the
    histogram's alt and figcaption for the lowest value it names. The histogram SVGs are not touched;
  - about/index.html: the `#part-time` subsection after `#term-quirk`; llms.txt: one appended line.
Each file is first stripped of this tool's own markup, then rewritten, so a second `--write` changes nothing and `--check` (exit 1) catches
any missing, extra or wrong marker, badge, note, caption suffix or key, on any of the 573 charts and 586 pages. The strings below are the
approved copy (Lindsay, copy packet sha abd37602); tests/test_k12_fte_presentation.py pins each one.

    python3 tools/nj_fte_marks.py --check   # exit 1 if any file is not in the final form
    python3 tools/nj_fte_marks.py --write
"""
import argparse
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nj_mobile_chart_fit as M  # noqa: E402  (the shared marker rule, line rule and key placement)

ROOT = M.ROOT

# --- approved copy: the one place the strings live ---------------------------------------------------------------------------------
BADGE_PART_TIME = "Part-time · {fte} FTE"
BADGE_REPORTED = "Reported as {fte} FTE"
SUFFIX_PART_TIME = " (part-time, {fte} FTE)"
SUFFIX_REPORTED = " (reported as {fte} FTE)"
CAPTION_CLOSE = "Hollow dots mark years reported at less than one full-time position."
SUMMARY_NOTE = '<p class="note"><span class="badge">{badge}</span> Salary as published by the district to NJDOE. <a href="/about/#part-time">Why</a></p>'
HISTORY_NOTE = '<p class="note"><span class="badge">{badge}</span> See the note below.</p>'
TERM_ENDED_NOTE = '<p class="note"><span class="badge">Term ended</span> See the note below.</p>'  # already on the page; merged, never added
TERM_ENDED_PART_TIME_NOTE = '<p class="note"><span class="badge">Term ended</span> <span class="badge">{badge}</span> See the notes below.</p>'
FTE_NOTE = ('<p class="note" id="fte-note">Part-time: the district reported the superintendent at less than one full-time position. The FTE in the '
            'badge is that share of one full-time position, not a staff total. Salaries are as published by the district to NJDOE. '
            '<a href="/about/#part-time">Why</a></p>')
CHART_NOTE = ('<p class="note" id="fte-chart-note">Hollow dots are years the district reported at less than one full-time position, usually '
              "part-time. Salaries are as published by the district to NJDOE, so these years don't compare directly with full-time years. "
              '<a href="/about/#part-time">Why</a></p>')
NJ_NOTE = ('<p class="note" id="fte-nj-note">Some values, including the lowest, are for part-time positions: the district reported its '
           'superintendent at less than one full-time position. They are shown as published to NJDOE and marked in the table below. '
           '<a href="/about/#part-time">Why</a></p>')
NJ_CELL_BADGE = ' <span class="badge">{badge}</span>'  # after the value inside <td class="num">
ABOUT_BLOCK = ('<h3 id="part-time">Part-time superintendents</h3><p>Some districts report their superintendent at less than one full-time '
               'position. The budget file records this as FTE: 0.2 FTE is 0.2 of a full-time position, not a staff total. We show each salary '
               "as the district published it to NJDOE and mark part-time years, which don't compare directly with full-time years. Part-time "
               'is not the same as shared service. A salary reported at 0 or 0.0 FTE is shown as reported. The JSON download names this '
               'field ufb_fte.</p>')
LLMS_LINE = ('Partial FTE: superintendent rows with ufb_fte below 1 (string as published, such as "0.2", "0" or "0.0") are the district\'s '
             'reported share of one full-time position, not a staff FTE total. Pages mark them "Part-time · {fte} FTE", or "Reported as '
             '{fte} FTE" for 0 and 0.0. Salaries are values as published, never scaled.')
NJ_TABLE_YEAR = "2026-27"  # only this year's values get a table badge (the 10 in the histogram's year; ruling: spec AC 11); older latest values stay plain
LOW_TAIL = ("3406630", "Hampton Twp")  # the /nj/ histogram's alt text names this district's value as the low tail

FTE_PAT = r"0(?:\.\d+)?"
BADGE_ANY = rf"(?:Part-time · {FTE_PAT} FTE|Reported as {FTE_PAT} FTE)"


def badge(fte):
    """The badge text for a marked row: the reported-as form at FTE 0 or 0.0, else the part-time form."""
    return (BADGE_REPORTED if float(fte) == 0 else BADGE_PART_TIME).format(fte=fte)


def suffix(fte):
    return (SUFFIX_REPORTED if float(fte) == 0 else SUFFIX_PART_TIME).format(fte=fte)


def money(row):
    return f"${int(row['base_salary']):,}"


def pattern(template):
    """Regex for a copy template with its `{badge}` placeholder open to either badge form."""
    return re.escape(template).replace(re.escape("{badge}"), BADGE_ANY)


marked_fte = M.marked_fte


def marked_rows(rows):
    return [r for r in rows if marked_fte(r) is not None]


# --- desktop charts ---------------------------------------------------------------------------------------------------------------------
TAIL = re.compile(
    r'(?P<lines>(?:<polyline fill="none" stroke="#458699" stroke-width="3" points="[^"]*"/>)*)'
    r'(?P<dots>(?:<circle cx="[\d.]+" cy="[\d.]+" r="4" (?:' + M.FT_ATTRS + "|" + M.PT_ATTRS + r')/>)*)'
    r'(?P<values>(?:<text class="v" x="[\d.]+" y="[\d.]+"(?: text-anchor="end")?>[^<]*</text>)*)'
    r'(?P<key>(?:' + M.KEY_RE + r')?)</svg>\Z')


def render_chart(svg, rows):
    """The desktop chart in its final form for these JSON rows: hollow dots, re-cut lines and the key on a chart with a marked dot, the
    plain chart otherwise. Raises ValueError on a chart that is not the expected structure or does not match the rows."""
    cut = min(i for i in (svg.find("<polyline"), svg.find("<circle")) if i >= 0)
    m = TAIL.match(svg, cut)
    if not m:
        raise ValueError("unexpected desktop SVG structure")
    ftes = M.expected_ftes(svg, rows)
    dots = M.DOT_FTE.findall(m.group("dots"))
    if len(dots) != len(ftes):
        raise ValueError("dot count differs from the reported rows")
    index = {}
    for i, (x, y, _) in reversed(list(enumerate(dots))):
        index[f"{x},{y}"] = i
    lines, _ = M.cut_lines(M.POLYLINE.findall(m.group("lines")), index, ftes)
    out = [svg[:cut]]
    out += [f'<polyline fill="none" stroke="#458699" stroke-width="3" points="{p}"/>' for p in lines]
    out += [(M.PT_DOT if f is not None else M.FT_DOT).format(x=x, y=y, f=f) for (x, y, _), f in zip(dots, ftes)]
    out.append(m.group("values"))
    if any(f is not None for f in ftes):
        label = M.key_label(ftes)
        pts = [(float(x), float(y)) for x, y, _ in dots]
        boxes = [M.value_box(float(v.group(1)), bool(v.group(3)), float(v.group(2)), v.group(4)) for v in M.VALUE.finditer(m.group("values"))]
        _, dx, dy = M.place_key("desktop", label, pts, M.segment_list(lines), boxes, [])
        out.append(M.key_svg(dx, dy, label))
    return "".join(out) + "</svg>"


# --- district pages ---------------------------------------------------------------------------------------------------------------------
LI = re.compile(r'<li class="hrow">.*?</li>')
CAPTION = re.compile(r"(?P<pre>Line chart of .*? school year, \d{4}-\d\d to \d{4}-\d\d: )"
                     r"(?P<list>\d{4}-\d\d \$[\d,]+(?:; \d{4}-\d\d \$[\d,]+)*)(?P<post>\.[^<\"]*)")
SUFFIX_ANY = re.compile(rf" \((?:part-time,|reported as) {FTE_PAT} FTE\)")
STRIP_DISTRICT = [
    (re.compile(pattern(TERM_ENDED_PART_TIME_NOTE)), TERM_ENDED_NOTE),
    (re.compile(pattern(HISTORY_NOTE)), ""),
    (re.compile(pattern(SUMMARY_NOTE)), ""),
    (re.compile(re.escape(FTE_NOTE)), ""),
    (re.compile(re.escape(CHART_NOTE)), ""),
    (re.compile(re.escape(" " + CAPTION_CLOSE)), ""),
    (SUFFIX_ANY, ""),
]


def strip_district(page):
    """The page without this tool's markup (the build's page)."""
    for pat, new in STRIP_DISTRICT:
        page = pat.sub(new, page)
    return page


def rewrite_district(page, rows):
    """The district page in its final form for these JSON rows (stripped first, so any state of the page gives the same answer). A page
    with no marked, reported row comes back as the stripped page."""
    page = strip_district(page)
    if not marked_rows(rows):
        return page
    section = re.search(r'<ol class="history">(.*?)</ol>', page, re.S)
    if not section:
        raise ValueError("no history list")
    lis = LI.findall(section.group(1))
    if len(lis) != len(rows):
        raise ValueError(f"{len(lis)} history rows but {len(rows)} JSON rows")
    for li, row in zip(lis, rows):  # the list is the JSON's rows in file order; check it before trusting the pairing
        shown = re.search(r'<span class="hy num">([^<]*)</span><span class="hs num">([^<]*)</span>', li)
        want = "Not reported ($0 in source)" if row["salary_not_reported"] else money(row)
        if not shown or shown.groups() != (row["school_year"], want):
            raise ValueError(f"history row {shown.groups() if shown else li[:60]} does not match the JSON row {row['school_year']} {want}")

    it = iter(rows)

    def history_row(m):
        row = next(it)
        fte = marked_fte(row)
        if fte is None:
            return m.group(0)
        li = m.group(0)
        meta = re.search(r'<p class="hmeta">.*?</p>', li)
        rest = li[meta.end():]
        if rest.startswith(TERM_ENDED_NOTE):
            return li[:meta.end()] + TERM_ENDED_PART_TIME_NOTE.format(badge=badge(fte)) + rest[len(TERM_ENDED_NOTE):]
        return li[:meta.end()] + HISTORY_NOTE.format(badge=badge(fte)) + rest

    page = page[:section.start(1)] + LI.sub(history_row, section.group(1)) + page[section.end(1):]

    big = re.search(r'<p class="big num">([^<]*)</p>', page)
    first = rows[0]
    if not big or big.group(1) != ("Not reported ($0 in source)" if first["salary_not_reported"] else money(first)):
        raise ValueError("the latest summary is not the first JSON row")
    if marked_fte(first) is not None:
        page = page[:big.end()] + SUMMARY_NOTE.format(badge=badge(marked_fte(first))) + page[big.end():]

    reported = sorted((r for r in rows if not r["salary_not_reported"]), key=lambda r: r["school_year"])  # stable: file order within a year

    def caption(m):
        entries = m.group("list").split("; ")
        if entries != [f"{r['school_year']} {money(r)}" for r in reported]:
            raise ValueError("the chart caption does not list the reported rows")
        shown = "; ".join(e + (suffix(marked_fte(r)) if marked_fte(r) is not None else "") for e, r in zip(entries, reported))
        return m.group("pre") + shown + m.group("post") + " " + CAPTION_CLOSE

    page, n = CAPTION.subn(caption, page)
    if n != 2:
        raise ValueError(f"expected the chart alt and figcaption, found {n} captions")

    trend = page.index('<h2 id="trend">')
    fig = page.index("</figure>", trend) + len("</figure>")
    page = page[:fig] + CHART_NOTE + page[fig:]

    end = page.index("</ol>", page.index('<h2 id="history">')) + len("</ol>")
    term = re.compile(r'<p class="note" id="term-note">.*?</p>').match(page, end)
    at = term.end() if term else end
    return page[:at] + FTE_NOTE + page[at:]


# --- /nj/ -------------------------------------------------------------------------------------------------------------------------------
NJ_ROW = re.compile(r'(<tr><th scope="row"><a href="/nj/[^"]*?-(\d+)/">[^<]*</a></th><td>[^<]*</td><td class="num">)(\$[\d,]+)(</td>'
                    r'<td><span class="muted">)(\d{4}-\d\d)(</span></td>)')
NJ_CELL_STRIP = re.compile(r'(<td class="num">\$[\d,]+)' + pattern(NJ_CELL_BADGE) + "(</td>)")


def low_tail(rows_of):
    """(old, new) alt phrase for the value the histogram names, or None when that row is not part-time."""
    leaid, name = LOW_TAIL
    for r in rows_of(leaid):
        if r["school_year"] == "2026-27" and marked_fte(r) is not None:
            return f"{name} at {money(r)}", f"{name} at {money(r)}{suffix(marked_fte(r))}"
    return None


def strip_nj(page):
    page = NJ_CELL_STRIP.sub(r"\1\2", page)
    page = page.replace(NJ_NOTE, "")
    return re.sub(re.escape(LOW_TAIL[1] + " at ") + r"(\$[\d,]+)" + SUFFIX_ANY.pattern, LOW_TAIL[1] + r" at \1", page)


def rewrite_nj(page, rows_of):
    """/nj/ in its final form: badges in the table, the note under the histogram, the suffix in its alt text and figcaption. `rows_of(leaid)`
    gives a district's JSON rows."""
    page = strip_nj(page)

    def row(m):
        for r in rows_of(m.group(2)):
            if r["school_year"] == m.group(5) == NJ_TABLE_YEAR and not r["salary_not_reported"] and money(r) == m.group(3) and marked_fte(r) is not None:
                return m.group(1) + m.group(3) + NJ_CELL_BADGE.format(badge=badge(marked_fte(r))) + m.group(4) + m.group(5) + m.group(6)
        return m.group(0)

    page = NJ_ROW.sub(row, page)
    tail = low_tail(rows_of)
    if tail:
        if page.count(tail[0]) != 2:
            raise ValueError("the histogram alt text and figcaption do not both name the low tail")
        page = page.replace(*tail)
    fig = page.index("</figure>", page.index('<figure class="chart">')) + len("</figure>")
    if not page.startswith("\n<h2 id=\"list\">", fig):
        raise ValueError("the histogram figure is not followed by h2#list")
    return page[:fig] + NJ_NOTE + page[fig:]


# --- /about/ and llms.txt ---------------------------------------------------------------------------------------------------------------
TERM_QUIRK = re.compile(r'<h3 id="term-quirk">.*?</p>')


def rewrite_about(page):
    page = page.replace(ABOUT_BLOCK, "")
    m = TERM_QUIRK.search(page)
    if not m or len(TERM_QUIRK.findall(page)) != 1:
        raise ValueError("no single #term-quirk paragraph")
    return page[:m.end()] + ABOUT_BLOCK + page[m.end():]


def rewrite_llms(text):
    line = LLMS_LINE  # its {fte} is published text, not a value to fill
    if text.endswith(line + "\n"):
        text = text[:-len(line) - 1]
    elif text.endswith(line):
        text = text[:-len(line)]
    return text + ("" if text.endswith("\n") or not text else "\n") + line + "\n"


# --- the tree ---------------------------------------------------------------------------------------------------------------------------
def read(path):
    with open(path, encoding="utf-8", newline="") as fh:
        return fh.read()


def write(path, text):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def rows_of(leaid):
    return M.load_rows(leaid)


def pages():
    """[(path, leaid)] of every district page."""
    out = []
    for p in sorted(glob.glob(os.path.join(ROOT, "nj", "*", "index.html"))):
        m = re.search(r"-(\d+)[/\\]index\.html$", p)
        if m:
            out.append((p, m.group(1)))
    return out


def charts():
    return sorted(glob.glob(os.path.join(M.CHARS, "*-desktop.svg")))


def targets():
    """[(relative path, current text, final text)] for every file this tool owns."""
    out = []
    for f in charts():
        leaid = os.path.basename(f).split("-")[0]
        cur = read(f)
        out.append((os.path.relpath(f, ROOT), cur, render_chart(cur, rows_of(leaid))))
    for p, leaid in pages():
        cur = read(p)
        out.append((os.path.relpath(p, ROOT), cur, rewrite_district(cur, rows_of(leaid))))
    for rel, fn in (("nj/index.html", lambda t: rewrite_nj(t, rows_of)), ("about/index.html", rewrite_about), ("llms.txt", rewrite_llms)):
        cur = read(os.path.join(ROOT, rel))
        out.append((rel, cur, fn(cur)))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true")
    g.add_argument("--write", action="store_true")
    a = ap.parse_args(argv)
    stale = []
    for rel, cur, want in targets():
        if want != cur:
            stale.append(rel)
            if a.write:
                write(os.path.join(ROOT, rel), want)
    marked = sum(len(marked_rows(rows_of(os.path.basename(f).split("-")[0]))) for f in charts())
    districts = sum(1 for f in charts() if marked_rows(rows_of(os.path.basename(f).split("-")[0])))
    verb = "rewritten" if a.write else "stale"
    print(f"{districts} districts with a part-time dot, {marked} dots; {len(stale)} files {verb}" + "".join(f"\n  {s}" for s in stale[:50]))
    if len(stale) > 50:
        print(f"  ... and {len(stale) - 50} more")
    return 1 if a.check and stale else 0


if __name__ == "__main__":
    sys.exit(main())
