# VOICE DRAFT — K12-SITE-NJ-HISTORY-001
channel: district pages, statewide page, methodology, machine-readable site note
 audience: readers checking New Jersey staff and negotiated pay scales
status: draft only — do not send / post / publish
inputs: brief, site spec, upstream spec, pinned data and current site; see TRACE.md
kill list: personal information; unrelated datasets; unsupported values; seals; implied endorsement; derived staff totals

## District section
Heading: Staff and salary-guide history
Anchor: staff-guide-history

NJDOE staff figures and published salary guides for 2019-20 to 2025-26.

### Coverage next to the staff chart
Salary-guide coverage: {k} of {n} school years ({p}%).

partial history

We have a published, negotiated teacher salary guide for {k} of the {n} school years with NJDOE staff rows for this district. This counts salary guides, not years of staff data.

[See statewide coverage](/nj/history/)

### Staff figures
Staff FTE, as published

FTE means full-time equivalent. We show NJDOE's published FTE total, not a count of people. We do not fill gaps or calculate changes.

Group labels: Teachers; Administrators; Special services; Supervisors and coordinators.
Table labels: School year; Staff group; Published FTE; Status.
Data-table toggle: Show staff data table.

### Data states
- Small group: Suppressed: fewer than 10.
- Protected alongside another group: Suppressed: hidden to protect a small group.
- Explanation: Suppressed means the value is hidden to protect a small group. We never fill it in.
- Group suppressed every year: Every year is suppressed for this group, so we show it as a table, not a chart.
- Missing year: no row in the NJDOE file
- Explanation: No row means the file has no staff row for this district and school year. It does not mean zero.

### Salary guides when present
salary guide (negotiated)

These are negotiated pay scales by step and lane, not a report of what teachers actually earned. A step is a row in the pay scale; a lane is a qualification column.

Year-link label: View {school_year} salary guide.

### District with no staff rows
Staff history is not available for this district: there are no NJDOE staff rows in these files. This does not mean there were no staff.

Salary-guide coverage: not available (no NJDOE staff rows)

[See statewide coverage](/nj/history/)

### District downloads
[Download this district's staff history and coverage (CSV)](/data/nj/history/{nces_leaid}.csv)
[Download all NJ staff history (CSV)](/data/nj/nj-district-staff-history.csv)
[Download statewide salary-guide coverage (CSV)](/data/nj/nj-history-coverage.csv)

## Statewide page
Page path: /nj/history/
Title: NJ staff and salary-guide history | K12 Comp
Meta description: NJ staff figures and negotiated salary-guide coverage for 2019-20 to 2025-26. Partial history, with source links and CSV downloads.
H1: New Jersey staff and salary-guide history
Anchor: nj-history-overview

See which school years have staff rows and published teacher salary guides. This is partial history, not a complete record of teacher pay.

Primary link: [Browse NJ districts](/nj/)

### Salary-guide coverage
As of 2026-11-09 (America/Toronto), published teacher salary guides cover 14 of 4,676 district-years (0.3%) for 2019-20 to 2025-26: partial history.

A district-year is one district in one school year. The denominator counts district-years with a recorded district identifier in the NJDOE staff files. Coverage counts those with at least one published teacher salary-guide value; it does not measure staff-data completeness.

Table caption: Published teacher salary-guide coverage by school year.
Table headings: School year; District-years with staff rows; With a published teacher salary guide; Coverage; Coverage note.
ALL display label: All school years.

### Staff rows by year and group
See how many staff rows are published or suppressed in each school year. These are counts of rows, not counts of people. No statewide staff total is calculated.

Table caption: Published and suppressed staff rows by school year and staff group.
Table headings: School year; Staff group; Published rows; Suppressed rows.

### Districts with guide years
These districts have published teacher salary guides within 2019-20 to 2025-26. Each link opens the district page.

- [Bayonne City](/nj/bayonne-city-3401260/) · 2023-24, 2024-25, 2025-26
- [Clifton City](/nj/clifton-city-3403300/) · 2024-25, 2025-26
- [Edison Twp](/nj/edison-twp-3404500/) · 2023-24, 2024-25, 2025-26
- [Toms River Regional](/nj/toms-river-regional-3416230/) · 2024-25, 2025-26
- [Vineland City](/nj/vineland-city-3416800/) · 2025-26
- [W Windsor-Plainsboro Reg](/nj/w-windsor-plainsboro-reg-3417700/) · 2023-24, 2024-25, 2025-26

### Downloads
[Download all NJ staff history (CSV)](/data/nj/nj-district-staff-history.csv)
[Download statewide salary-guide coverage (CSV)](/data/nj/nj-history-coverage.csv)

## Credits shared by the district and statewide pages
### Staff files
- Source: New Jersey Department of Education · 2019-20 · retrieved 2026-11-06 (America/Toronto) · https://www.nj.gov/education/doedata/cs/cs20/cert_staff_state_1920.zip
- Source: New Jersey Department of Education · 2020-21 · retrieved 2026-11-06 (America/Toronto) · https://www.nj.gov/education/doedata/cs/cs21/Certificated%20Staff%202021.zip
- Source: New Jersey Department of Education · 2021-22 · retrieved 2026-11-06 (America/Toronto) · https://www.nj.gov/education/doedata/cs/cs22/Certificated%20Staff%202122.zip
- Source: New Jersey Department of Education · 2022-23 · retrieved 2026-11-06 (America/Toronto) · https://www.nj.gov/education/doedata/cs/cs23/Certificated%20Staff%202023.zip
- Source: New Jersey Department of Education · 2023-24 · retrieved 2026-11-06 (America/Toronto) · https://www.nj.gov/education/doedata/cs/cs24/CertificatedStaff_2024.zip
- Source: New Jersey Department of Education · 2024-25 · retrieved 2026-11-06 (America/Toronto) · https://www.nj.gov/education/doedata/cs/cs25/Certificated%20Staff%202025.xlsx
- Source: New Jersey Department of Education · 2025-26 · retrieved 2026-11-06 (America/Toronto) · https://www.nj.gov/education/doedata/cs/cs26/Certificated%20Staff%202026.zip

### Guide sources
- OPRA response from Bayonne City, received 2026-10-20, sha256 cb734d36db820b134e3db2589fcbf2835f9c3e65e97700a712d8c0f7d1f60c45
  - Data years: 2023-24, 2024-25, 2025-26. Retrieved 2026-10-20 (America/Toronto). Link each guide table to the existing source anchor on its district page; there is no public document URL.
- OPRA response from Clifton City, received 2026-10-21, sha256 2212af5d5ac7f8e49d487a6ba9bff5b51686e83e73aa0c5199823680e9f54b2c
  - Data years: 2024-25, 2025-26. Retrieved 2026-10-21 (America/Toronto). Link each guide table to the existing source anchor on its district page; there is no public document URL.
- Source: district contract · 2023-24, 2024-25, 2025-26 · retrieved 2026-10-20 (America/Toronto) · https://5il.co/2u0cp
- OPRA response from Toms River Regional, received 2026-10-20, sha256 9c3dc6805c72f9ef55f4ce2aec23509e0c755aaaafe42ab45a1fdeeb50a031cb
  - Data years: 2024-25, 2025-26. Retrieved 2026-10-20 (America/Toronto). Link each guide table to the existing source anchor on its district page; there is no public document URL.
- OPRA response from Vineland City, received 2026-10-22, sha256 36dd948aa4e46420fec2f143bf64443da4a1e0c5805d610c568c21cf3efc967c
  - Data years: 2025-26. Retrieved 2026-10-22 (America/Toronto). Link each guide table to the existing source anchor on its district page; there is no public document URL.
- Source: district contract · 2023-24, 2024-25, 2025-26 · retrieved 2026-10-20 (America/Toronto) · https://www.west-windsor-plainsboro.k12.nj.us/common/pages/DisplayFile.aspx?itemId=60107411

### Source rule for a later verified contract
NJ PERC · {school_year} · retrieved {retrieval_date_in_America_Toronto} · {verified_PERC_document_https_URL}

### As-is note
Provided as is. No endorsement by the source agencies is implied.

## About page addition
H2: How staff and salary-guide history works
Anchor: history-methodology

The history covers 2019-20 to 2025-26. Staff figures come from NJDOE Certificated Staff files. FTE means full-time equivalent: we show NJDOE's published FTE total, not a count of people. Values stay as published; we do not add them up, estimate missing values or calculate changes.

Suppressed values are hidden to protect a small group. We distinguish “fewer than 10” from “hidden to protect a small group”. A missing year says “no row in the NJDOE file”; it is not zero. We do not join records across different district identifiers.

Salary guides are negotiated pay scales by step and lane, not actual earnings. We show only published teacher guide cells within the history window. Each guide links to its source or its public-records response citation. A public-records response is a document received through New Jersey's Open Public Records Act (OPRA).

Coverage is the share of school years with staff rows that also have a published teacher salary-guide value. Statewide, we count district-years with a recorded district identifier. The percent appears beside the chart; “partial history” appears when fewer than half have guides. Districts with no staff rows show “not available”, not a percentage.

[See NJ history, source credits and CSV downloads](/nj/history/)

Provided as is. No endorsement by the source agencies is implied.

## llms.txt addition
NJ staff and salary-guide history: /nj/history/ covers 2019-20 to 2025-26. Staff values are NJDOE's published FTE totals, not headcounts; salary guide (negotiated) values are pay-scale cells, not actual earnings.
History CSVs: /data/nj/nj-district-staff-history.csv (all staff rows); /data/nj/nj-history-coverage.csv (statewide coverage); /data/nj/history/<nces_leaid>.csv (district staff rows and coverage, where staff rows exist).
Suppression: fewer than 10 and hidden to protect a small group are distinct states. A missing staff year is no row in the NJDOE file, never zero. Suppressed values stay empty.
Coverage: published teacher guide years divided by school years with staff rows; statewide, count district-years with a recorded district identifier. Always show the percentage, with partial history below half; no staff rows means not available, with no percentage.
No estimates: staff values and guide cells stay as published; no sums, averages, interpolation, derived headcounts or calculated raises. Source credits include the file URL, school year and retrieval date, or the existing OPRA response citation. Provided as is.

## Notes for implementation
- Template braces are data-bound fields, not unverified facts. Bind them only from the approved pin and published-cell filter.
- Render the partial-history label only when twice the numerator is less than the denominator. Omit it otherwise. When there are no staff rows, render neither a percent nor the label.
- Display coverage to one decimal. Apply the spec's near-half clamp so the partial label never sits beside a rounded half.
- No guide years: omit the whole guide element. Do not print a zero or a no-guide card.
- No staff rows: omit the district CSV link and staff chart/table; keep statewide links and the empty state.
- Show staff credits for every year shown, including years containing suppressed values. Use the same credit block on the statewide page.
- Show only the applicable guide credits near the corresponding guides. In-window public documents are district contracts or OPRA responses, not PERC documents. Do not render the future PERC template now.
- Existing source anchors are src- plus the first twelve characters of the matching sha256. Keep the source citation reachable outside collapsed content. Each guide year links to its existing guide table, not merely the section heading.
- Keep OPRA citation strings exact; put data years and retrieval dates on a separate line. Never fabricate a public URL for an OPRA response.
- Append the About and llms.txt additions only; preserve all existing text and lines byte for byte. Preserve the existing district title and meta description.
- Add link label “NJ staff and salary-guide history” to /nj/ and /about/, targeting /nj/history/.
- Statewide table values and row counts are bound fresh from the pin, not hardcoded from this draft. Include all school years and the ALL coverage row.
- The snapshot date describes these checked inputs, not a new retrieval or a promise of current coverage. Re-pin means recheck the date and coverage.
