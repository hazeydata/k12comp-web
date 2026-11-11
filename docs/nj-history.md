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
- **Leftover 7b, "Base salary by year" mobile charts.** `tools/nj_mobile_chart_fit.py --write` rewrote the 572 of 573 `charts/d/<leaid>-mobile.svg`
  that misfit their 390 px box: an end-value label whose estimated right edge passes x=384 is right-aligned at x=384 and set 10 px above its dot
  (below it when the line comes down into the dot); a year label that overlaps the final year's label is dropped (first and final years always stay;
  the alt text still lists every year and value). Lines, dots, gridlines, y labels, alt text and the desktop SVGs are unchanged. `--check` exits 1 on any misfit; re-running `--write` changes nothing.
- **Leftover 10, the `/nj/` Dataset JSON-LD.** `/nj/index.html` named `/api/v1/nj/` as its Dataset `contentUrl` with `encodingFormat: application/json`.
  That URL was a 404. A first fix (commit `d501474`) put an HTML index there, which made the URL resolve but left the metadata saying JSON about an HTML page.
  `tools/nj_api_index.py --write` now writes three things, and `--check` exits 1 if any is missing or stale:
  - `api/v1/nj/index.json`: `{count, description, files: [{district, nces_leaid, page, url}], license, state}`, one entry per district JSON file (586),
    each `district` and `nces_leaid` read from that file, written like the district files (indent 1, sorted keys, final newline). No person field.
  - `api/v1/nj/index.html`: the same list as a page for people, in the site header and footer, with a link to `index.json`. No metadata calls this page JSON.
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
  that only labels moved (values, first and final years unchanged), that no desktop chart changed, both index files are fresh, complete and agree with each
  district file, that `/nj/index.html` differs from `a41b5838` by the `contentUrl` only and from `3b50ce10` by that and the history link only, that every
  `3b50ce10` path still exists, and that nothing else changed since `a41b5838` (explicit lists, no pattern wider than the mobile chart names).
  `tests/test_jsonld_content_urls.py` runs the JSON-LD check on the committed tree and on small bad sites: missing target, directory URL with an HTML index
  (the first fix), HTML under a `.json` name, JSON under an `.html` name, truncated JSON, another host, a path above the site root, an unpublished path. It fails if anything opens a network socket.
