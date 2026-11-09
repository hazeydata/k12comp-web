# NJ staff and salary-guide history (K12-SITE-NJ-HISTORY-001)

> **Status: local prototype, round 2. Not deploy-ready, not approved for release.** Nothing is pushed, no issue or PR exists, no preview is
> published. Open questions below need a spec or product decision before it can ship.

## Open questions and limits
- **OPEN QUESTION for Lucille 2 (AC 3 and AC 16): the per-district CSV header.** The spec says each `/data/nj/history/<leaid>.csv` holds "staff rows
  plus that district's coverage row" and that each CSV's key set equals its allowlist, but it names no combined header. The most literal reading is
  used, with no invented column: one header that is the union of the staff allowlist and the coverage allowlist, staff rows leaving the coverage
  columns empty, and one final coverage row (`school_year=ALL`) leaving the staff-only columns empty. AC 3 and AC 16 are provisional until this is answered.
- **OPEN QUESTION (layout):** the approved dataviz design puts coverage above the four panels; writing's layout notes say beside the chart on desktop.
  This build follows the dataviz geometry (four columns at 1100 px and up, needs the full width) and places the coverage block directly above the chart.
- **OPEN QUESTION (scale note):** the approved dataviz note says the largest values "differ by more than 5 times between groups". The approved code shows it
  on every page with a chart, so on pages where that is false it would be wrong. This build shows the exact approved sentence only when the claim is
  true for that district, and shows no scale note otherwise. Dataviz to say what, if anything, should appear on the other pages.
- The statewide head keeps `/nj/`'s head elements (AC 25). Its description, `og:title`, `og:description`, `og:image:alt`, title and canonical are the
  approved history copy, so the whole page passes the AC 22 scan. The shared `og-image.png` file is unchanged and its pixels were not inspected.
- Release: `tools/nj_history_release_guard.py` and the two workflows make the gates executable (see "Release guard"). The CI read secret
  `K12_DATA_READ_TOKEN` and the gates secret `K12_RELEASE_GATES` do not exist yet (owner: chief / Fred); until they do, CI fails closed. Nothing deploys from this repo.
- Accessibility: the check was a Chrome accessibility-tree dump. No spoken screen-reader walkthrough was done.
- Charts follow the approved dataviz renderer; the approved files are pinned in `docs/nj-history-approved-files.json`.

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
  block, and a separate Dataset JSON-LD block (`id="ld-nj-history"`, staff-rows pages only) before `</head>`. Old markup is never edited: each
  guide year links with `#guides-h:~:text=Teacher%20salary%20guide%2C%20<year>`, the existing `#guides-h` anchor plus a text-fragment directive that
  that some browsers use to scroll to the existing teacher guide heading. A small same-origin `/history.js` (loaded from inside the section, `defer`) opens the closed year block and scrolls to the heading in every browser; without JavaScript the link lands on the guides section. This is one new script; the layout notes ask for no *external* scripts, and this one is not external.
- `/nj/history/` (statewide page), built from `/nj/index.html`'s head, header and footer so head parity holds by construction.
- `/history.css` and `/history.js` (same-origin; loaded from inside the new sections, not from any head).
- `/data/nj/nj-district-staff-history.csv` (18,732 rows), `/data/nj/nj-history-coverage.csv` (7 years plus ALL) and
  `/data/nj/history/<leaid>.csv` for the 585 districts with staff rows.
- A link on `/nj/`, a methodology section on `/about/`, one sitemap entry (`/nj/history/`) and five appended `llms.txt` lines.
- Unchanged: `robots.txt`, `CNAME`, the 586 `/api/v1/nj/*.json` files, and every other file.

AC 24: removing the history section and the `ld-nj-history` block leaves each district page byte-identical to k12comp-web 3b50ce1; `/nj/` differs
only by the one added link paragraph, `/about/` only by the appended section. There is no other normalisation (no id stripping).

## Data rules

- fte_sum is the CSV string; the only change is a thousands comma. Nothing is summed, averaged, rounded, interpolated or turned into a change.
  headcount is never shown. Suppressed rows show no number anywhere and stay empty in CSV. A line never bridges a suppressed or missing year.
- Suppressed `n_lt_10` and `complementary` have distinct wording. A year with no row says "no row in the NJDOE file" and is never zero.
- Charts follow the approved dataviz `render_lib.py panel()`: time down seven rows, FTE across from 0 on each group's own scale, the largest value
  `plot_w - 64` from the axis so its label sits beside the dot (8 pt offset), dots joined only across consecutive published years; a group with 2 or
  fewer published values is a table-first row list drawn in the same SVG grid. Two sizes are rendered (253 px wide for the 1120 px desktop four-column
  design, 304 px for the stacked design) and CSS shows one. Chart data comes fresh from the pinned inputs; only the rules and fixed strings are pinned
  (`tests/test_nj_history_dataviz.py`). Every panel set has a matching data table. "Published" and the panel and scale notes are the approved dataviz strings.
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
Four short strings are not in copy.md; they are the approved dataviz strings (render_lib.py): "Published", "Dot chart: one dot per published school year",
"Table first: 2 or fewer published values, so no chart is drawn", and the independent-scales note.

## Privacy

Output carries only allowlisted columns. Every staff column is validated (shape, enumeration, equality with the manifest), so a planted
string fails the build rather than reaching a page. `tests/test_nj_history_privacy.py` plants canaries in every staff column, an extra
column, the salary-cell file and the PERC-signatory fixture, and scans all output. No person, UFB or superintendent data is in any history output.

## Release guard (AC 29)

Nothing merges to k12comp-web main and nothing deploys to k12comp.com until test-run PASS, Weatherman SHIP at the exact head,
pre-deploy-check PASS and Fred's go relayed by chief. Before that the work exists only as a preview on k12comp-preview.

`tools/nj_history_release_guard.py` enforces this for the build artifact and fails closed (no skip mode):

- `preflight`: the CI read secret is present (value never printed), the data clone is at the pinned commit with every input equal to its lock hash,
  the tree is clean, nothing generated is tracked (`data/nj/`, the statewide CSV) and no tracked file is over 1 MB.
- `release --head <sha> --gates <file> --out <dir>`: additionally needs a gates file outside the repo with test-run PASS, Weatherman SHIP,
  pre-deploy-check PASS, Fred's go relayed by chief and a pre-push scan with 0 findings, each recorded for that exact full head, which must equal the
  checked-out head. It then builds into `--out` (outside the repo) and checks the output. Success prints that nothing was deployed.
- `.github/workflows/ci.yml` runs preflight, the tests (ResourceWarning is an error) and the build, and uploads the output as an artifact.
  `.github/workflows/release-build.yml` (manual) runs the release guard and uploads the artifact. Neither has a deploy step. Both fail at the first
  step if `K12_DATA_READ_TOKEN` (and, for the release build, `K12_RELEASE_GATES`) is not set. Those secrets are not provisioned.
- On the box, `guard.sh` (`guarded_push`) and `prepush-scan --base origin/main` still apply to every push.
- Publishing the artifact (preview or live) is outside this repo and needs its own approval.
