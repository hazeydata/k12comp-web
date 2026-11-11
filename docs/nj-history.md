# NJ staff and salary-guide history (K12-SITE-NJ-HISTORY-001)

> **Status: web PR #3 is open on `feat/2026-11-09-k12-site-nj-history`. Not merged, not production-deployed.** This follow-up commits the `_config.yml`
> excludes (docs, tests, tools) and the built NJ history pages in place, so a merge to main can publish them through GitHub Pages (legacy Jekyll, no `.nojekyll`).
> Test-run round 3 was READY yes at `4449f693`. The Weatherman re-gate, pre-deploy-check and Fred's merge/deploy go are still outstanding. The preview at
> https://nj-history-da0572d.k12comp-preview.pages.dev (deploy `06d471b9`) was built from `da0572d`, not this head; production is unchanged. The 4.7 MB statewide CSV (`/data/nj/nj-district-staff-history.csv`) is committed with the per-district CSVs and the small
> coverage CSV so GitHub Pages can serve them; it is under GitHub's file-size limits.

## Final rulings (Lucille 2, Nov 9, 2026, 3:21 PM ET, relayed by the parent)
1. **Per-district CSV header (AC 3, AC 16): approved.** One header that is the union of the staff allowlist and the coverage allowlist; staff rows leave the
   coverage columns empty; one final coverage row (`school_year=ALL`) leaves the staff-only columns empty. No new column. This is final, not provisional.
2. **Scale note: omit it where its claim is false.** The approved dataviz note ("the largest published values differ by more than 5 times between groups")
   is shown only on a district chart where that is true (at least two chart groups and the largest values differ by more than 5 times), and omitted on every
   other chart. This is the existing conditional code (`render.py scale_note_applies`). The exact list of districts that omit it is derived fresh from the
   pinned inputs and published in the web PR draft.
3. **Coverage above the charts (dataviz) is final.** The coverage block sits directly above the charts; four columns at 1100 px and up.

## Limits that remain (not product questions)
- The statewide head keeps `/nj/`'s head elements (AC 25); its title, description, og tags and `og:image:alt` are the approved history copy and the whole
  page passes the AC 22 scan. The shared `og-image.png` is unchanged and its pixels were not inspected.
- Guide-year links: with JavaScript (`/history.js`) they open and scroll to the existing guide table; without it they land on the guides section.
  One same-origin script is added; the layout notes forbid external scripts.
- Release: `tools/nj_history_release_guard.py` and the two workflows make the gates executable (see "Release guard"). The CI read secret `K12_DATA_READ_TOKEN` is set; chief provides the release gates input `K12_RELEASE_GATES` at release time, and CI fails closed until it is set. k12comp.com is GitHub Pages (legacy Jekyll, built from `main`), so a merge to `main` publishes the committed tree; the workflows only build and upload an artifact. The gates below still apply before any merge.
- Verification (104 Python tests under `-X dev -W error::ResourceWarning`, newsletter JS 12/12, 48 local browser renders, byte-identical builds, 1,185 local HTTP
  checks) was run on web commit `a078085`. Later commits changed more than documentation: `ci.yml` now fetches full history, and this follow-up adds the built pages,
  `_config.yml`, a narrowed release guard, new tests and the CI `--site` base-archive step. Re-run the suite for the current head. This is not a test-run, Weatherman or quality-gate result.
- Accessibility: an accessibility-tree dump was checked; no spoken screen-reader walkthrough was done.
- Charts follow the approved dataviz renderer; the approved files are pinned in `docs/nj-history-approved-files.json`.

## Run

    git archive 3b50ce10b88e80188e6c8265634b68b482c1a81f | tar -x -C ../k12comp-web-base   # new, empty directory
    K12_DATA_REPO=<read-only clone of hazeydata/k12comp> python3 tools/nj_history_postbuild.py --site ../k12comp-web-base --out ../k12comp-web-site

`--out` must be a new or empty directory outside the repo (the existing tests glob the repo tree for pages). After this follow-up the working tree is no longer a
fresh unbuilt site (the history pages are committed in place), so the default `--site .` fails with "page already carries the history section". `--site` must be a
`git archive` of base commit `3b50ce10b88e80188e6c8265634b68b482c1a81f` (the `BASE_COMMIT` constant in `tests/nj_history_helpers.py`). The committed pages are
the output of exactly that build; `tests/test_nj_history_committed.py` checks them byte for byte, with one named exception: the committed
`/nj/index.html` carries the leftover 10 `contentUrl` edit (one exact substitution, `SCOPED_EDITS` in that test; see "Follow-up fixes"). After copying a
fresh build in place, run `python3 tools/nj_api_index.py --write` to put that edit back. The statewide CSV is committed at
`data/nj/nj-district-staff-history.csv` (so Pages can serve it) and is also written to `--out`; the test checks the committed copy against that build.
The build tool does not publish; a merge to `main` does (see Release guard).

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
only by the one added link paragraph, `/about/` only by the appended section. There is no other normalisation (no id stripping). That is the build
output, and `tests/test_nj_history.py` still checks it unchanged. The committed `/nj/index.html` has one more difference, made after the build: its
Dataset `contentUrl` (leftover 10, below). The committed tree also has two new files under `/api/v1/nj/` (`index.html`, `index.json`); the 586 district JSON files are byte-identical.

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
  coverage row leaves the staff-only columns empty. Approved by Lucille 2 (Nov 9, 3:21 PM ET).

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
  the tree is clean, `build/` is not tracked, and every tracked file is under 1 MB except the statewide CSV, which is tracked and allowed (it may exceed 1 MB; cap 50 MB). The in-place built HTML and the small CSVs (`data/nj/history/*.csv`, `data/nj/nj-history-coverage.csv`) are committed and allowed.
- `release --head <sha> --gates <file> --out <dir>`: additionally needs a gates file outside the repo with test-run PASS, Weatherman SHIP,
  pre-deploy-check PASS, Fred's go relayed by chief and a pre-push scan with 0 findings, each recorded for that exact full head, which must equal the
  checked-out head. It then builds into `--out` (outside the repo) and checks the output. Success prints that nothing was deployed.
- `.github/workflows/ci.yml` runs preflight, the tests (ResourceWarning is an error) and the build, and uploads the output as an artifact.
  `.github/workflows/release-build.yml` (manual) runs the release guard and uploads the artifact. Neither has a deploy step. Both fail at the first
  step if `K12_DATA_READ_TOKEN` (and, for the release build, `K12_RELEASE_GATES`) is not set. `K12_DATA_READ_TOKEN` is now a repo secret; `K12_RELEASE_GATES` is still filled by chief at release time.
- On the box, `guard.sh` (`guarded_push`) and `prepush-scan --base origin/main` still apply to every push.
- A merge to `main` publishes the committed tree to k12comp.com via GitHub Pages (legacy Jekyll). `release-build.yml` only builds an artifact and does not publish. Merge and publish still need the gates above and Fred's go.

## Follow-up fixes outside the history build (leftovers 7 and 10, 2026-11-11)

These change committed site files after the history build; the build, its pin and its own tests (`tests/test_nj_history.py`, AC 23/24 against
`3b50ce10`) are untouched. They start from web main `a41b5838`. Visible on the site: yes (leftover 7 and the new `/api/v1/nj/` page; Lucille 2 narrative review before merge).
The CI and release artifacts are still built from base `3b50ce10` alone, so they do not carry these fixes; the published site is the committed tree
(a merge to `main`), which does. The release guard and both workflows are unchanged and still fail closed.

- **Leftover 7a, guide tables at 336/390 px.** The site-wide `overflow-wrap:anywhere` on `body` let guide-table cells shrink to one digit per line.
  One added `style.css` line, mobile only: `.grid th` (column and step headers) and `.grid td.num` get `white-space:nowrap`, so the
  table scrolls sideways inside its existing focusable `.table-wrap` region. Only the 8 district pages with guide tables (`section.grid`) are affected.
  PR #5 fix 1 (section below) keeps a native sr-only caption at every width, and adds the swipe cue and the sticky Step column.
- **Leftover 7b, "Base salary by year" mobile charts.** `tools/nj_mobile_chart_fit.py --write` rewrote the 572 of 573 `charts/d/<leaid>-mobile.svg`
  that misfit their 390 px box: an end-value label whose estimated right edge passes x=384 is right-aligned at x=384 and set 10 px above its dot
  (below it when the line comes down into the dot); a year label that overlaps the final year's label is dropped (first and final years always stay;
  the alt text still lists every year and value). Lines, dots, gridlines, y labels, alt text and the desktop SVGs are unchanged. `--check` exits 1 on any misfit; re-running `--write` changes nothing.
  Superseded by K12-CHART-MOBILE-TEXT-001 (section at the end): the same tool now redraws these charts in a 304-unit viewBox.
- **Leftover 10, the `/nj/` Dataset JSON-LD.** `/nj/index.html` named `/api/v1/nj/` as its Dataset `contentUrl` with `encodingFormat: application/json`.
  That URL was a 404. A first fix (commit `d501474`) put an HTML index there, which made the URL resolve but left the metadata saying JSON about an HTML page.
  `tools/nj_api_index.py --write` now writes three things, and `--check` exits 1 if any is missing or stale:
  - `api/v1/nj/index.json`: `{count, description, files: [{district, nces_leaid, page, url}], license, state}`, one entry per district JSON file (586),
    each `district` and `nces_leaid` read from that file, written like the district files (indent 1, sorted keys, final newline). No person field.
  - `api/v1/nj/index.html`: the same list as a page for people, in the site header and footer, with a link to `index.json`. No metadata calls this page JSON. Its table has class `api-files` (PR #5 fix list, below).
  - `/nj/index.html`: one scoped edit. `"contentUrl": "/api/v1/nj/"` becomes `"contentUrl": "/api/v1/nj/index.json"`; `encodingFormat` stays `application/json`.
    Nothing else on the page changes. The tool refuses to edit unless it finds that text exactly once. The generator and the history build are not changed:
    the build still writes the old value, so `tests/test_nj_history_committed.py` expects the committed page to equal the build output with exactly this
    substitution (`SCOPED_EDITS`), and every other committed file to equal it byte for byte.
  Neither index file is added to `sitemap.xml` or `llms.txt` (build outputs).
- **JSON-LD check.** `python3 tools/jsonld_content_urls.py` walks every JSON-LD block of every published page (594 pages, 1,173 blocks). For each
  `contentUrl` whose `encodingFormat` is `application/json` (1, the `/nj/` Dataset) or `text/csv` (586, the history Datasets) it finds the file GitHub Pages
  would serve, and requires that it exists, is published, has the matching extension (a directory URL is `index.html`, so it fails) and parses.
  It reads from disk only: root-relative, page-relative and `https://k12comp.com/` URLs are mapped to files; a URL on any other host is a failure, not a fetch. Exit 1 on any problem.
- Tests (no data repo needed): `tests/test_nj_leftovers_7_10.py` checks the CSS line, every mobile chart against the fit rules, idempotence,
  that values and dot heights stay (K12-CHART-MOBILE-TEXT-001 now redraws x), that no desktop chart changed, both index files are fresh, complete and agree with each
  district file, that `/nj/index.html` differs from `a41b5838` by the `contentUrl` only and from `3b50ce10` by that and the history link only, that every
  `3b50ce10` path still exists, and that nothing else changed since `a41b5838` (explicit lists, no pattern wider than the mobile chart names;
  the PR #5 fix list adds its 8 guide pages by exact path and its four new files).
  `tests/test_jsonld_content_urls.py` runs the JSON-LD check on the committed tree and on small bad sites: missing target, directory URL with an HTML index
  (the first fix), HTML under a `.json` name, JSON under an `.html` name, truncated JSON, another host, a path above the site root, an unpublished path. It fails if anything opens a network socket.

## PR #5 fix list, fix 1: guide tables on mobile (2026-11-11)

Ann's PR #5 dataviz review (fix 1): at 336/390 px the guide table's `<caption>` sat inside the sideways scroller and was cut off
("Teacher salary guide, 2026-2…"), nothing said more columns exist, scrolling right hid the Step column, and at 336 px the source line broke
as "Source:" / link / ", pages 58–62". Visible on the site: yes. Fix 2 (mobile chart text size) is not in this change: it is a separate ticket
(`k12comp/specs/k12-chart-mobile-text-001.md`, owner implement), and no chart, SVG or chart tool is changed here.

- `tools/nj_guide_tables.py --write` rewrites the 40 guide tables on the 8 district pages with `section.grid`; `--check` exits 1 if any page is stale.
  It is the static publication source transform (not a change to the historical base generator), and is idempotent. It accepts both the original
  build markup and the previous visible-caption publication markup, then emits the current committed markup.
  - Lucille 2's follow-up ruling keeps the full unchanged caption inside the table as `<caption class="sr-only" id="guide-cap-N">` at **every width**;
    the table keeps the same accessible name through `aria-labelledby="guide-cap-N"`. The existing `h3` stays visible. No copy changes: the region's
    `aria-label`, heading, caption, source line, note and cells are unchanged.
  - Tables with 3+ header cells (23 of 40) get `<p class="guide-cue" aria-hidden="true">Swipe to see more columns →</p>` above the
    scroller. The wording is the approved copy (Lindsay, `SCROLL_CUE`, pinned in `tests/test_nj_guide_tables.py`); to change it, edit `SCROLL_CUE`,
    update the pin and re-run `--write`. Step + one column tables (Bayonne, Edison) fit at 336 px and get no cue.
- `style.css` gains two lines for this (after the newsletter rules; a third line, below, is for `/api/v1/nj/`). All widths: `.grid caption.sr-only` uses the standard clip pattern
  (`position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0`),
  and `.guide-cue{display:none}`. The scoped caption rule overrides the generic caption padding without changing other tables.
  At <=640 px: the cue shows (14 px, muted); the Step column (`.grid tr>th:first-child`) is `position:sticky; left:0` with a background and a
  1 px edge, so row context stays when scrolled right; the source line is `text-wrap:balance` and its link is `display:inline` with 12 px vertical
  padding (a 44 px target), so the link starts on the "Source:" line and ", pages 58–62" stays with it. No copy is shortened; values keep 16 px and `nowrap`.
  At 1280 px the caption is also visually hidden; the existing heading still shows and the cue stays hidden. The cue and sticky Step rules are unchanged by this follow-up.
- AC 23/24: the history build still writes the old guide markup, so `tests/test_nj_history_committed.py` allows, on exactly these 8 pages
  (`GUIDE_PAGES`), the committed page to equal `nj_guide_tables.rewrite(build page)`, and checks by hand that removing fix 1's markup gives the
  build page back byte for byte. Every other committed file must still equal the build. Like leftovers 7 and 10, release artifacts built from
  `3b50ce10` alone do not carry this fix (the generator-port leftover).
- Tests: `tests/test_nj_guide_tables.py` (static: copy pin, the old placeholder cue wording appears nowhere, the 8 pages / 40 tables, idempotence,
  diff from web main is fix 1's markup only, captions unchanged, cue placement, cells unchanged, CSS rules). `tests/test_nj_guide_tables_browser.py`
  (real local Chrome through the Python `playwright` package, skipped without it; 127.0.0.1 server, throwaway profile, other requests aborted) checks
  all 40 tables at 336, 390 and 1280 px, initial and scrolled right: native sr-only caption has a clipped 1 × 1 px box at every width, the unchanged heading remains visible, and the caption is still the table's accessible name
  in Chrome's accessibility tree; cue shown above the scroller at 336/390 exactly where columns are hidden and hidden at 1280; Step column stuck at
  the left edge with the last column fully visible beside it; salary cells on one line at 16 px; source line wrapping as described; no page-level sideways scroll.

### Same round: `/api/v1/nj/` file names on mobile (quality-gate round 1 nit)

The web PR #5 gate (round 1) noted that the `/api/v1/nj/` file column wraps mid-name at 390 px; at 336 px "District page" also broke inside
"District". `tools/nj_api_index.py` now writes `<table class="api-files">` (the only change to `api/v1/nj/index.html`), and one mobile-only
`style.css` line keeps each file name on one line (`white-space:nowrap`), lets the other cells wrap only between words (`overflow-wrap:break-word`
instead of the site-wide `anywhere`), and uses 6 px cell padding with none on the outer edges (the region has no border on mobile), so the three
columns fit the 304 px column at 336 px. `index.json`, `/nj/index.html`, the rows and their text are unchanged; desktop is unchanged.
`tests/test_nj_api_index_browser.py` (same local-Chrome setup as the guide test, skipped without it) checks at 336, 390 and 1280 px: all 586
file names whole on one line with a 44 px link, no cell broken inside a word, no page-level sideways scroll, and the table inside the content column.

## K12-CHART-MOBILE-TEXT-001: readable mobile chart text (2026-11-11)

`figure.chart img` is `width:100%`, so a mobile SVG renders at the content width: 304 px at a 336 px viewport, 358 px at 390. Effective text
size is font units x ancestor transform scale x content width / viewBox width. The district charts (390-unit viewBox, 12/14-unit text) gave
9.35/10.91 px at 304; the `/nj/` distribution (matplotlib, 280.8-unit viewBox, 6 to 11-unit text) gave 6.50 px. No CSS change.
- **Gate.** `python3 tools/nj_mobile_chart_fit.py --check` measures every text node of the 573 district mobile charts and the `/nj/` distribution
  mobile chart at 304 and 358 px content (`CONTENT_PX`) and exits 1 on any node under 12 px, listing each chart with its count and smallest size,
  then the chart count and the nodes under 12 px. The box-fit checks still run, retargeted to the new geometry, and also fail on a value label
  that covers a dot or line or sits nearer another dot than its own.
- **District charts.** `--write` redraws each `charts/d/<leaid>-mobile.svg` in a 304-unit viewBox (1 unit = 1 CSS px at 336) from itself and its
  desktop twin, which it reads only. Kept byte for byte: every y coordinate, label text, colour, the `<style>` block (12-unit text, 14-unit bold
  values) and the height. The plot runs from x=48 to x=272. Each dot sits at its true school-year position, linear in the start year over the
  axis range (the desktop's first to last year slot). The desktop has one slot per source year, so in 34 charts where the source skips a year the
  desktop spaces years unevenly; it is byte-frozen and keeps that. Value labels take the first spot, in a fixed order, that stays inside the plot,
  clears every dot, line and other label, and is no nearer another dot than its own (`place_value`).
- **Value-label leaders and early last dots (PR #6 review, fixes 2 and 3).** A value label more than 20 units from its dot (nearest point of
  its box to the dot's centre) gets a leader: a #999 line, 0.75 wide, no arrowhead, from that nearest box edge to the dot, drawn under the
  dots. Nearer labels get none. The rule is generic (8 charts have one: 3403930, 3405550, 3406870, 3410320, 3411280, 3411310, 3412390,
  3414880). When the labelled dot is not at the rightmost year slot, the years to its right are empty, so the label is never right-aligned
  at the plot edge: it goes level 8 units right of the dot, else start-aligned 6 units right of it, above or below (6 charts; 3414220's
  $20,000 now starts at x=214 beside its 2024-25 dot at x=208). `--check` fails on a missing, extra or misplaced leader and on a label
  right-aligned past such a dot.
- **Year labels (review-web5-r1 nit).** One rule: the latest axis year, then every k-th year counting back from it, k the smallest whole step
  whose label pitch is at least one label width plus 6 units. On an 8-year axis that is 2020-21, 2022-23, 2024-25, 2026-27. The labels are evenly
  spaced because the years they mark are; the first year is labelled only when it falls on the step. No plotted position moves. The visible
  figcaption and the alt text list every year and value.
- **NJ distribution.** `--write` reflows the original matplotlib SVG once, inside the SVG. A file already in the 304 viewBox is left alone, so to
  change the layout, restore the original from git and re-run. Title, subtitle and source note keep their words and are rewrapped (title 13 units
  bold, everything else 12). The two outlier notes move clear of the stems (`OUTLIERS`). "Newark City / $330,978" keeps its line breaks.
  "Hampton Twp / $56,225" goes one word per line, left-aligned near the first low-tail stem and just below the "20" tick level, at least
  6 units clear of the "20" label (PR #6 review fix 1). As two lines, "Hampton Twp" would run into the $120-130k stems there. The plot is
  only translated (`translate(8 dy)`), never scaled. The viewBox is 304 x 507.5, so the chart renders 507.5 px tall at 304 (was 405).
  Nothing moved to HTML, so no wording went to Lindsay.
- Tests: `tests/test_k12_chart_mobile_text.py` (no data repo needed). The gate passes on the tree and reproduces the PR #5 review's browser counts
  at base. `--write` on the base SVGs gives the committed ones. Each district's dot years equal its page's alt text, at true positions. Heights,
  values, lines and gridlines are kept, and lines join the same dots. The year-label rule holds. Every label more than 20 units from its dot
  has exactly one leader joining its box edge and the dot, and nearer labels have none. A label whose dot is before the last year slot starts
  6 to 8 units right of it. NJ words are verbatim and its marks are only translated. Its text stays inside the viewBox, clear of stems, dots
  and other text, and the Hampton note is at least 6 units from every tick label. Only the in-scope mobile SVGs change on the site, and
  desktop charts equal web main.
