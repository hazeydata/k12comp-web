# NJ staff and salary-guide history (K12-SITE-NJ-HISTORY-001)

An add-on post-build step (OQ-1, no generator migration). It copies the committed site tree to an output directory and adds
the history there. Nothing in the committed tree changes, and the 4.7 MB statewide CSV is generated at build time, not committed.

## Run

    K12_DATA_REPO=<read-only clone of hazeydata/k12comp> python3 tools/nj_history_postbuild.py --out ../k12comp-web-site

The output must be a new or empty directory outside the repo (the existing tests glob the repo tree for pages). The deploy job has to run this step and publish `--out`;
this repo does not deploy anything (see Release guard).

Tests: `K12_DATA_REPO=<clone> python3 -m unittest discover -s tests -p 'test_*.py'`, plus `node tests/newsletter.test.js`.
Real-browser layout, clipping and accessibility checks: `tests/browser/run_browser_check.py --build <out>` (local headless Chrome, local HTTP
server, throwaway profile; not Cloudflare). A static, local-only responses check is `tests/local_preview_check.py --build <out>`.

## Inputs (AC 1, 2)

`tools/nj_history/pin.json` pins `hazeydata/k12comp` at a full commit and holds the sha256 of every input. The build reads only
these paths, with `git show <commit>:<path>`; any other path is refused:

- `data/nj_district_staff_2019-20.csv` .. `_2025-26.csv`
- `sources/nj_cs_manifest.csv` (every staff row's sha256 and source_url must equal its year's manifest row, and that row must be `status=ok`)
- `data/nj-salary_cell.csv` (cross-check only, see Guides)
- `data/nj_history_coverage.csv` (cross-check only, see Coverage)

`K12_FIXTURE_MODE=1` with `--fixture-dir` replaces the git source in tests only. No raw/, UFB or CCD file and no network fetch is an input.
Display names come only from the two committed tables `district_names.csv` (nces_leaid, from the live page headings) and
`nj_staff_district_names.csv` (county district code, latest school year's spelling), both hashed in the lock.

Re-pin: `python3 tools/nj_history_postbuild.py --gen-lock --data-repo <clone> --commit <full sha> --snapshot-date <YYYY-MM-DD>`
regenerates the tables and `pin.json`. Recheck the snapshot date and coverage in the approved copy when you do.

## What it adds

- Every `/nj/<slug>-<leaid>/` page: one `<section class="nj-hist">` (heading id `staff-guide-history`) inserted before the newsletter
  block, a separate Dataset JSON-LD block (`id="ld-nj-history"`, staff-rows pages only) before `</head>`, and an `id="guide-teacher-YYYY-YY"`
  attribute on each existing teacher guide table in the window so each guide year links to its table. The existing `#history`,
  `#guides-h`, `#dl` and `#src-*` anchors and the existing JSON-LD are untouched.
- `/nj/history/` (statewide page), built from `/nj/index.html`'s head, header and footer so head parity holds by construction.
- `/history.css` (same-origin; loaded from inside the new sections, not from any head).
- `/data/nj/nj-district-staff-history.csv` (18,732 rows), `/data/nj/nj-history-coverage.csv` (7 years plus ALL) and
  `/data/nj/history/<leaid>.csv` for the 585 districts with staff rows.
- A link on `/nj/`, a methodology section on `/about/`, one sitemap entry (`/nj/history/`) and five appended `llms.txt` lines.
- Unchanged: `robots.txt`, `CNAME`, the 586 `/api/v1/nj/*.json` files, and every other file.

AC 24 declared normalisation list: removing the history section, the `ld-nj-history` block and the `guide-teacher-` id attributes
leaves each district page byte-identical to k12comp-web 3b50ce1; `/nj/` differs only by the one added link paragraph, `/about/`
only by the appended section.

## Data rules

- fte_sum is the CSV string; the only change is a thousands comma. Nothing is summed, averaged, rounded, interpolated or turned into a change.
  headcount is never shown. Suppressed rows show no number anywhere and stay empty in CSV. A line never bridges a suppressed or missing year.
- Suppressed `n_lt_10` and `complementary` have distinct wording. A year with no row says "no row in the NJDOE file" and is never zero.
- A group with 3 or more published values gets a dot-and-line panel (own scale from 0, value labels in a column right of the dots);
  a group with 2 or fewer gets a row list (the dataviz rule). Every panel set has a matching data table.
- Per-district CSV: the spec says "staff rows plus that district's coverage row" in one file. It uses one header (the union of the staff
  and coverage allowlists) and a final coverage row with `school_year=ALL`; staff rows leave the coverage columns empty and the
  coverage row leaves the staff-only columns empty. This is an interpretation, flagged in the cycle decisions.

## Guides and coverage (OQ-3, locked)

Guide years are the teacher cells with a salary that the site already publishes (`api/v1/nj/<leaid>.json`, verified identity,
2019-20..2025-26). The build cross-checks them against the pinned `data/nj-salary_cell.csv` with the same filter and fails on any difference.
Coverage counts exactly those published cells, so Clifton City (3403300, 2024-25 and 2025-26) is included: **14 of 4,676 district-years (0.3%)**,
per year 0, 0, 0, 0, 3, 5, 6. The upstream `data/nj_history_coverage.csv` still says 12 (0, 0, 0, 0, 3, 4, 5) because the data repo holds Clifton back
(missing alias evidence, K12-CLIFTON-IDENTITY-GUARD-001). The build compares with the file: denominators must be equal, and numerators
must be equal or differ only by the LEAIDs in `COVERAGE_EXCEPTIONS` (Clifton only); anything else fails. The 14 is never hard-coded.
When the identity-guard fix regenerates the file, the difference disappears and the exception can be removed.

District coverage is `k of n school years (p%)` with n = years in the window with a staff row and k = those with a published teacher guide year.
"partial history" shows iff 2k < n (exact integers). The percent has one decimal and is clamped so "50.0" never sits beside the label.

## Copy

`docs/nj-history-copy.md` is the approved writing copy and `docs/nj-history-layout-notes.md` its layout notes (caption and alt patterns); each is
identical to the writing packet's file except the trailing lint line, which names a local path. `tools/nj_history/copy.py` holds the strings; `tests/test_nj_history_copy.py` pins every string to that file.
`pin.json` `copy_sha256` is the sha256 of the writing packet's original copy.md (including its lint line).
Strings that are not in the approved copy and were added by the build: the status word "Published" in the data table, and the short
chart note "Each group has its own scale, starting at 0. Compare the printed values, not dot positions."

## Privacy

Output carries only allowlisted columns. Every staff column is validated (shape, enumeration, equality with the manifest), so a planted
string fails the build rather than reaching a page. `tests/test_nj_history_privacy.py` plants canaries in every staff column, an extra
column, the salary-cell file and the PERC-signatory fixture, and scans all output. No person, UFB or superintendent data is in any history output.

## Release guard (AC 29)

Nothing merges to k12comp-web main and nothing deploys to k12comp.com until test-run PASS, Weatherman SHIP at the exact head,
pre-deploy-check PASS and Fred's go relayed by chief. Before that the work exists only as a preview on k12comp-preview.
The deploy path that publishes `--out` is not part of this change.
