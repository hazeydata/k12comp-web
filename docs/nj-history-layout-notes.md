# VOICE DRAFT — layout notes
status: draft only — no implementation or publishing
channel: K12Comp district section and statewide reference page
audience: readers checking staff figures and salary-guide coverage
inputs: copy.md and TRACE.md
kill list: person data; unrelated data; invented charts; seals; unsupported values

## Layout choice
Use C, minimal: a short introduction followed by the data and source links. This is a reference page, not a sales page: browsing districts is the primary action, so omit testimonials, benefit tiles and a decorative hero. Keep existing site navigation, newsletter, footer and page head conventions unchanged.

## District block order
Insert the new section after existing salary guides and before existing downloads. Do not rearrange or edit any existing section.

- H2 “Staff and salary-guide history”, id `staff-guide-history`.
- One-line introduction from copy.md.
- Coverage line, conditional “partial history” label, explanation and statewide link. Keep this block directly beside the chart on desktop and directly above it on mobile; never hide it in a toggle.
- Staff FTE slot, plain-words FTE definition, status key and matching data table.
- Guide-year slot, only where published guide cells exist. Label exactly “salary guide (negotiated)”. Link each year to its existing guide table and source.
- Applicable guide source credits; staff file credits for every year shown; as-is note.
- District history CSV link and both statewide CSV links. On the no-staff-row state, omit the district CSV link and staff chart/table.

For no staff rows, keep the section heading, empty state, exact not-available coverage line and statewide links. Do not show “partial history” or any percent. If there is no guide year, omit the entire guide element; no zero and no additional empty card.

## Statewide block order
- Existing header, breadcrumb back to /nj/, skip link and main landmark.
- H1 “New Jersey staff and salary-guide history”, id `nj-history-overview`; intro; primary link “Browse NJ districts”.
- H2 “Salary-guide coverage”, id `history-coverage`; snapshot sentence, definition, coverage visual/table slot. The percentage and “partial history” remain visible beside or immediately above the slot.
- H2 “Staff rows by year and group”, id `published-row-counts`; row-count explanation, row-count visual/table slot. No statewide FTE total.
- H2 “Districts with guide years”, id `guide-years`; linked district list and school years.
- H2 “Downloads”, id `history-downloads`; two statewide CSV links.
- H2 “Staff file sources”, id `staff-file-credits`; full credits, applicable guide sources and as-is note.
- Existing newsletter slot and footer, with existing behaviour unchanged.

Index the eventual statewide reference page; preview remains noindex. Use copy.md title and meta description, matching social title/description and canonical route /nj/history/. Retain the current head assets and source-host links; add no external fonts, image hosts or scripts. The current shared social image remains a page-head asset, not part of the new history section.

## Chart slots for dataviz
No chart is authored here. Each slot expects the dataviz packet's desktop and mobile assets, observed source values/counts only, caption, alt text and matching accessible table. Braced fields are substitution patterns, not prose to publish unfilled. Prefer a table alone over an invented visual if no approved asset exists.

### District staff slot
- Caption pattern: “{district}: NJDOE's published FTE totals by staff group, {first_school_year} to {last_school_year}. Suppressed values and missing rows are marked, not filled in.”
- Alt pattern: “Published FTE totals for {district}, {first_school_year} to {last_school_year}, for teachers, administrators, special services, and supervisors and coordinators. {source_backed_suppressed_years_and_groups} {source_backed_missing_years_and_groups} Exact values and statuses are in the staff data table.”
- Omit absent status clauses, rather than claiming gaps or suppression that are not present. Do not summarize trends or calculate changes.
- Data table uses one cell per school year and staff group, matching the source; use the exact two suppression labels and missing-row label from copy.md. Never connect across a suppressed or missing year. Never plot either as zero.
- Source line: the applicable staff-file credits in copy.md, with year, URL and retrieval date.

### District guide-year slot
- Caption pattern: “salary guide (negotiated): published teacher guide years for {district} within 2019-20 to 2025-26.”
- Alt pattern: “Published teacher salary-guide years for {district}: {published_school_years}. Each year links to the existing guide table and source.”
- This is a year-availability slot, not a pay-growth chart. No invented representative salary or comparison across steps/lanes. Show only years with qualifying published cells.
- Source line: matching public district document or unchanged OPRA response citation in copy.md. No universal NJ PERC attribution.

### Statewide coverage slot
- Caption pattern: “Published teacher salary-guide coverage by school year, 2019-20 to 2025-26. partial history.”
- Alt pattern: “Teacher salary-guide coverage by school year, with an all-years total of {with_guide} of {district_years} district-years ({coverage_pct}%). {conditional_partial_history} Exact yearly counts and percentages are in the coverage table.”
- Caption and alt partial-history text are conditional on the same exact integer rule as the visible label, not a rounded percent. The current all-years values are in copy.md; bind yearly values from the approved build input.
- Table: each school year and ALL; district-year denominator, with-guide numerator, percentage and conditional coverage note. All-year label: “All school years”.
- Source line: staff manifest credits and applicable guide-source credits; the coverage definition stays immediately adjacent.

### Statewide staff-row slot
- Caption pattern: “Published and suppressed staff rows by school year and staff group, 2019-20 to 2025-26. These are rows, not people.”
- Alt pattern: “Counts of published and suppressed staff rows for teachers, administrators, special services, and supervisors and coordinators by school year. These count rows, not staff or FTE totals. Exact counts are in the row-count table.”
- Table uses School year, Staff group, Published rows, Suppressed rows; counts come fresh from the pinned files. No statewide FTE sum or average.
- Source line: staff-file credits in copy.md.

## At 390px
Use a single reading column with 16px page gutters and 16px mobile card padding. The available column is 358px; no visual, table, credit, hash or URL may exceed it. Stack charts, coverage, captions and sources in DOM reading order; do not shrink source text to make it fit.

Use Space Grotesk body text-base (16px/24px); secondary text-sm (14px/20px), not smaller; H1 text-3xl (30px/36px) and H2 text-2xl (24px/32px). Numbers and school years use existing JetBrains Mono. Desktop H1 text-5xl (48px, line-height 1), with heading and subheading max-width 680px; content max-width 1120px, text max-width 65ch. Balance headings and wrap prose naturally.

Use 8px between label and explanation, 16px between small blocks, 24px between chart/caption/table groups, 64px between mobile sections and 96px desktop. All margins, padding and gaps use the house spacing list. Cards use outer radius 16px; nested radii follow outer minus gap only where the result exceeds 2px. Links use existing accessible ink/teal-text tokens, not light teal small text.

For wide tables, group by school year into stacked semantic tables with staff groups as rows and value/status as columns. Coverage and row-count tables may likewise become school-year table groups with labelled row headers. Keep every source cell and full label; do not create a horizontal scrolling region. Long source URLs and sha256 values wrap anywhere without changing their strings. Keep captions and credit links outside images.

Every actionable link, toggle and summary has a minimum 44px hit area; use 48px line boxes where helpful, with 8px separation. Keep a visible focus ring. Native links/toggles have hover, active and focus states using current site tokens. No asynchronous loading is added: static tables remain available if an image is absent. If an optional asset fails, show “Chart unavailable. Read the data table below.” and keep its source and table. Do not add controls with no real target.

No decorative motion. If existing transitions apply, retain the site's transform/opacity-only curve and reduced-motion behaviour. No new forms, cookie handling or newsletter changes.

## About and machine-readable additions
Append the new H2 “How staff and salary-guide history works”, id `history-methodology`, after existing methodology content. The three current sections and all their text remain unchanged. Append only the llms.txt lines in copy.md; preserve every current line and its order.

## Notes for implementation
- All proposed IDs were checked against every HTML file at the required site pin; inputs/anchor-check.txt records zero existing occurrences. Do not reuse the heading History or the id history, nor alter existing source, guide or download anchors.
- These are layout specifications, not a claim of a rendered visual test. Implement must verify no horizontal overflow, clipped captions or broken targets at 390px, 1280px and 1440px, including the missing-year and no-row states.
- Use the dataviz packet for chart geometry and assets; if its slot structure differs, preserve these copy strings, coverage placement and source/table accessibility requirements.
