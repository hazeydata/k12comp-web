"""Approved copy (writing pass, docs/nj-history-copy.md). Strings are verbatim; braces are bound from data.
tests/test_nj_history_copy.py pins every string here to docs/nj-history-copy.md."""

# ---- district section
D_HEADING = "Staff and salary-guide history"
D_ANCHOR = "staff-guide-history"
D_INTRO = "NJDOE staff figures and published salary guides for 2019-20 to 2025-26."
D_COV = "Salary-guide coverage: {k} of {n} school years ({p}%)."
D_PARTIAL = "partial history"
D_COV_EXPLAIN = ("We have a published, negotiated teacher salary guide for {k} of the {n} school years with NJDOE "
                 "staff rows for this district. This counts salary guides, not years of staff data.")
D_STATE_LINK = "See statewide coverage"
D_STAFF_HEAD = "Staff FTE, as published"
D_FTE_DEF = ("FTE means full-time equivalent. We show NJDOE's published FTE total, not a count of people. "
             "We do not fill gaps or calculate changes.")
GROUP_LABELS = {"teacher": "Teachers", "administrator": "Administrators", "special_service": "Special services",
                "supervisor_coordinator": "Supervisors and coordinators"}
TABLE_HEADS = ("School year", "Staff group", "Published FTE", "Status")
TABLE_TOGGLE = "Show staff data table"
STATUS_SMALL = "Suppressed: fewer than 10."
STATUS_COMP = "Suppressed: hidden to protect a small group."
SUPPRESSED_EXPLAIN = "Suppressed means the value is hidden to protect a small group. We never fill it in."
ALL_SUPPRESSED = "Every year is suppressed for this group, so we show it as a table, not a chart."
MISSING = "no row in the NJDOE file"
MISSING_EXPLAIN = "No row means the file has no staff row for this district and school year. It does not mean zero."
GUIDE_LABEL = "salary guide (negotiated)"
GUIDE_EXPLAIN = ("These are negotiated pay scales by step and lane, not a report of what teachers actually earned. "
                 "A step is a row in the pay scale; a lane is a qualification column.")
GUIDE_YEAR_LINK = "View {school_year} salary guide."
NO_ROWS = ("Staff history is not available for this district: there are no NJDOE staff rows in these files. "
           "This does not mean there were no staff.")
NO_ROWS_COV = "Salary-guide coverage: not available (no NJDOE staff rows)"
DL_DISTRICT = "Download this district's staff history and coverage (CSV)"
DL_ALL = "Download all NJ staff history (CSV)"
DL_COV = "Download statewide salary-guide coverage (CSV)"
# captions and alt text (layout-notes patterns)
STAFF_CAPTION = ("{district}: NJDOE's published FTE totals by staff group, {first} to {last}. "
                 "Suppressed values and missing rows are marked, not filled in.")
STAFF_ALT = ("Published FTE totals for {district}, {first} to {last}, for teachers, administrators, special services, "
             "and supervisors and coordinators. {suppressed}{missing}Exact values and statuses are in the staff data table.")
GUIDE_CAPTION = "salary guide (negotiated): published teacher guide years for {district} within 2019-20 to 2025-26."
GUIDE_ALT = ("Published teacher salary-guide years for {district}: {years}. "
             "Each year links to the existing guide table and source.")
CHART_UNAVAILABLE = "Chart unavailable. Read the data table below."

# ---- statewide page
S_PATH = "/nj/history/"
S_TITLE = "NJ staff and salary-guide history | K12 Comp"
S_DESC = ("NJ staff figures and negotiated salary-guide coverage for 2019-20 to 2025-26. "
          "Partial history, with source links and CSV downloads.")
S_H1 = "New Jersey staff and salary-guide history"
S_H1_ANCHOR = "nj-history-overview"
S_INTRO = ("See which school years have staff rows and published teacher salary guides. "
           "This is partial history, not a complete record of teacher pay.")
S_BROWSE = "Browse NJ districts"
S_COV_HEAD = "Salary-guide coverage"
S_COV_ANCHOR = "history-coverage"
S_COV_SNAP = ("As of {date} (America/Toronto), published teacher salary guides cover {w} of {t} district-years "
              "({p}%) for 2019-20 to 2025-26{tail}")
S_COV_DEF = ("A district-year is one district in one school year. The denominator counts district-years with a "
             "recorded district identifier in the NJDOE staff files. Coverage counts those with at least one "
             "published teacher salary-guide value; it does not measure staff-data completeness.")
S_COV_CAPTION = "Published teacher salary-guide coverage by school year."
S_COV_HEADS = ("School year", "District-years with staff rows", "With a published teacher salary guide", "Coverage",
               "Coverage note")
S_ALL_LABEL = "All school years"
S_ROWS_HEAD = "Staff rows by year and group"
S_ROWS_ANCHOR = "published-row-counts"
S_ROWS_INTRO = ("See how many staff rows are published or suppressed in each school year. These are counts of rows, "
                "not counts of people. No statewide staff total is calculated.")
S_ROWS_CAPTION = "Published and suppressed staff rows by school year and staff group."
S_ROWS_HEADS = ("School year", "Staff group", "Published rows", "Suppressed rows")
S_GUIDES_HEAD = "Districts with guide years"
S_GUIDES_ANCHOR = "guide-years"
S_GUIDES_INTRO = ("These districts have published teacher salary guides within 2019-20 to 2025-26. "
                  "Each link opens the district page.")
S_DL_HEAD = "Downloads"
S_DL_ANCHOR = "history-downloads"
S_CREDITS_HEAD = "Staff file sources"
S_CREDITS_ANCHOR = "staff-file-credits"
S_STAFF_CREDITS = "Staff files"
S_GUIDE_CREDITS = "Guide sources"
AS_IS = "Provided as is. No endorsement by the source agencies is implied."
CREDIT_NJDOE = "Source: New Jersey Department of Education · {year} · retrieved {date} (America/Toronto) · {url}"
CREDIT_PERC = "NJ PERC · {year} · retrieved {date} (America/Toronto) · {url}"
CREDIT_CONTRACT = "Source: district contract · {years} · retrieved {date} (America/Toronto) · {url}"
CREDIT_DATA_YEARS = "Data years: {years}. Retrieved {date} (America/Toronto)."
CREDIT_OPRA_NOTE = "Link each guide table to the existing source anchor on its district page; there is no public document URL."

# ---- about and llms
A_HEAD = "How staff and salary-guide history works"
A_ANCHOR = "history-methodology"
A_PARAS = (
    "The history covers 2019-20 to 2025-26. Staff figures come from NJDOE Certificated Staff files. FTE means "
    "full-time equivalent: we show NJDOE's published FTE total, not a count of people. Values stay as published; "
    "we do not add them up, estimate missing values or calculate changes.",
    "Suppressed values are hidden to protect a small group. We distinguish “fewer than 10” from “hidden "
    "to protect a small group”. A missing year says “no row in the NJDOE file”; it is not zero. We do "
    "not join records across different district identifiers.",
    "Salary guides are negotiated pay scales by step and lane, not actual earnings. We show only published teacher "
    "guide cells within the history window. Each guide links to its source or its public-records response citation. "
    "A public-records response is a document received through New Jersey's Open Public Records Act (OPRA).",
    "Coverage is the share of school years with staff rows that also have a published teacher salary-guide value. "
    "Statewide, we count district-years with a recorded district identifier. The percent appears beside the chart; "
    "“partial history” appears when fewer than half have guides. Districts with no staff rows show "
    "“not available”, not a percentage.",
)
A_LINK = "See NJ history, source credits and CSV downloads"
LINK_LABEL = "NJ staff and salary-guide history"
LLMS_LINES = (
    "NJ staff and salary-guide history: /nj/history/ covers 2019-20 to 2025-26. Staff values are NJDOE's published FTE "
    "totals, not headcounts; salary guide (negotiated) values are pay-scale cells, not actual earnings.",
    "History CSVs: /data/nj/nj-district-staff-history.csv (all staff rows); /data/nj/nj-history-coverage.csv "
    "(statewide coverage); /data/nj/history/<nces_leaid>.csv (district staff rows and coverage, where staff rows exist).",
    "Suppression: fewer than 10 and hidden to protect a small group are distinct states. A missing staff year is no row "
    "in the NJDOE file, never zero. Suppressed values stay empty.",
    "Coverage: published teacher guide years divided by school years with staff rows; statewide, count district-years "
    "with a recorded district identifier. Always show the percentage, with partial history below half; no staff rows "
    "means not available, with no percentage.",
    "No estimates: staff values and guide cells stay as published; no sums, averages, interpolation, derived headcounts "
    "or calculated raises. Source credits include the file URL, school year and retrieval date, or the existing OPRA "
    "response citation. Provided as is.",
)

# ---- chart strings from the approved dataviz files (render_lib.py), not in copy.md; pinned by tests/test_nj_history_dataviz.py
PANEL_CHART_NOTE = "Dot chart: one dot per published school year"
PANEL_TABLE_NOTE = "Table first: 2 or fewer published values, so no chart is drawn"
SCALE_NOTE = ("Independent FTE scales: each group has its own horizontal axis starting at 0, because the largest published "
              "values differ by more than 5 times between groups, so one shared scale would flatten the smaller groups. Do not compare "
              "dot positions between groups; compare the printed values.")
STATUS_PUBLISHED = "Published"  # dataviz status_text() for a published row
