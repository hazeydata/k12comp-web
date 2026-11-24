# K12-INDEXING-001: county hubs, same-county peer links, unique titles and the sitemap

Google knew 590 k12comp.com URLs but had indexed 1 (GSC, Nov 16, 2026). Crawl depth was fine (max 2) and nothing blocked crawling, but 578 of
586 district pages had exactly one linking page (`/nj/`), no district page linked another, 11 duplicate-title groups covered 24 pages, and the
district `lastmod` dates did not track the HTML changes. This ticket adds structure only: no salary, source URL, sha256 line, chart, `api/` or
`data/` file changes.

## The tool

`tools/nj_indexing.py` (stdlib only; deterministic and idempotent):

    python3 tools/nj_indexing.py [site] --check   # exit 1 if any file it owns is not in its final form (site defaults to the repo root)
    python3 tools/nj_indexing.py [site] --write   # rewrite in place; also the default when neither flag is given

Every file is first stripped of the tool's own markup and then rewritten, so a second run changes no byte. It reads only the site's HTML pages
and `sitemap.xml`: the `/nj/` table (names, LEAIDs, counties, row markup), the pages' titles, canonicals, robots meta and "Updated" dates.

### Run order

1. The history build: `K12_DATA_REPO=<clone> python3 tools/nj_history_postbuild.py --site <git archive of the base> --out <dir>`
   (see `docs/nj-history.md`). Its fresh-sitemap check runs here, on the build's own sitemap, and it appends `/nj/history/`.
2. The existing rewrites, each `--write`: `nj_api_index` -> `nj_guide_tables` -> `nj_fte_marks` -> `nj_mobile_chart_fit` -> `nj_chart_label_edge`.
3. `tools/nj_district_summaries.py --write` (K12-DISTRICT-SUMMARIES-001, `docs/nj-district-summaries.md`): one summary paragraph on every district page.
4. **`tools/nj_indexing.py --write` last.** It reads the final `/nj/` table (with the FTE badges `nj_fte_marks` adds, which the hubs copy) and
   then regenerates `sitemap.xml` from the finished tree, which is why it runs after `build.py`'s fresh-sitemap check rather than inside it.

`tests/test_nj_history_committed.py` checks that the committed tree is exactly this: fresh build, the existing rewrites, then this tool
(`expected_final`: `expected_fte` -> `expected_summaries` -> `expected_indexing` for every district page, `/nj/` and `sitemap.xml`; the hubs and `/` must equal the tool's output).

## What it writes

- **County hubs**, 21 files `nj/county/<slug>/index.html`, one per county in the `/nj/` County column (11 to 76 districts each, 586 in all).
  Slug rule: the county name without " County", lowercased, any run of characters other than `a-z0-9` becomes `-`; a county name that is
  not ASCII stops the tool (pick its slug by hand). Example: "Cape May County" -> `cape-may`.
  Each hub has `/nj/`'s head (Dataset block removed; own title, description, canonical, og:url) and header/footer, then:
  breadcrumb "New Jersey / <County>", h1 "<County> superintendent salaries", the intro line
  "Latest superintendent base salary for the <n> districts in <County>, as reported to NJDOE." (its only number is the district count;
  no median, total or other statistic), the `/nj/` disclaimer, the county's `/nj/` rows copied byte for byte and in `/nj/` order (FTE badges
  included) in the same table markup (caption "<County> districts"), and a link "All New Jersey districts" back to `/nj/`.
  Title "<County>, NJ superintendent salaries | K12 Comp"; description "Latest superintendent base salary for the <n> school districts in
  <County>, New Jersey, each linked to its source document."; BreadcrumbList JSON-LD (`id="ld-breadcrumb"`). No newsletter block (as on `/nj/`).
- **District pages** (all 586): the breadcrumb "Districts / <District>" becomes "New Jersey / <County> / <District>" (links `/nj/` and the hub),
  with a matching BreadcrumbList block (`id="ld-breadcrumb"`) before `</head>`; the Dataset blocks are byte-unchanged. A peer block
  `<section class="peers">` headed "Other districts in <County>" sits at the end of `<main>` (after Download) with **8 name-only links**.
  **Peer rule (OQ-1):** sort the county's districts by display name (casefolded, then the name as written, then LEAID as the tie-break); a
  district's peers are the **4 alphabetically previous and the 4 next** in that list, **wrapping** around the ends. A county with 9 or fewer
  districts would list all the others (none today: the smallest, Mercer, has 11). No salary or other number in the block.
  The h1 and everything else in `<main>` are unchanged.
- **Titles (OQ-4).** The tool groups the indexable pages by title (as the build wrote it); every district page in a group of 2 or more gets
  its county: "Franklin Twp (Somerset Co) superintendent salary, 2026-27". " | K12 Comp" stays only while the title is under 60 characters
  (the rule in `tools/seo_postbuild.py`; all 24 drop it today). `og:title` mirrors `<title>`, as the site already does. Today that is 24 pages
  in 11 groups; every other title is unchanged. A duplicate on a page the tool does not own stops it.
- **`/` and `/nj/`**: a "By county" list of all 21 hubs (on `/` before the closing paragraph, on `/nj/` after the table). The `/nj/` h1 becomes
  "New Jersey superintendent salaries, 586 districts" (the count is the table's row count). The County cells in the table are not linked (OQ-10).
- **`sitemap.xml`**: every indexable HTML page = no robots `noindex` and exactly one canonical pointing at the page itself, except `api/`
  (OQ-9: `/api/v1/nj/` stays out). Same format as before; sorted by file path with `/nj/history/` last (where the build appends it).
  **lastmod (OQ-6):** hubs `RELEASE_DATE`; pages the tool rewrites (districts, `/`, `/nj/`) max(the page's "Updated" date, `RELEASE_DATE`);
  every other page keeps its current lastmod (an indexable page with none stops the tool). `RELEASE_DATE = "2026-11-24"` is a constant in the
  tool (bumped from 2026-11-16 for K12-DISTRICT-SUMMARIES-001); bump it in the release that next changes these pages. 611 URLs today (590 + 21). `robots.txt` is unchanged and
  `tools/nj_history_release_guard.py` still finds `/nj/history/`.

The new visible strings live once, at the top of the tool (`NJ_H1`, `BY_COUNTY_H2`, `PEERS_H2`, `CRUMB_ROOT`, `HUB_*`, `DUP_TITLE`).

## Tests

`tests/test_k12_indexing.py` checks the committed tree with its own parsers (not the tool's): hub set == `/nj/` County column; hub rows ==
`/nj/` rows cell for cell (11-76, sum 586), every district linked; no number on a hub that is not in its `/nj/` rows or the intro count and no
text outside the template; the existing no-UFB/no-names guard (`FORBIDDEN` from `test_nj_history_privacy.py`, minus the role word) and a
planted-name canary; the 8 peers recomputed; the offline link graph (every district >= 10 linking pages, every hub >= 2, depth <= 2 from `/`,
hubs at 1, `/` and `/nj/` link all hubs); BreadcrumbList == visible breadcrumb; Dataset blocks == 7e99b60e; 0 duplicate titles, changed
titles == the 24, each with its county; unique descriptions; one self-canonical; noindex pages unchanged; sitemap == indexable set (611),
lastmod rule; robots unchanged; district `<main>` minus breadcrumb/peer block == 7e99b60e. Scratch copies show idempotence (sha256 of every
file), a rebuild from the 7e99b60e pages giving the committed bytes, and that a dropped peer link, a changed hub row, a title collision, a
removed sitemap URL, a wrong BreadcrumbList item or a missing home county list each fail. `tests/k12_indexing_helpers.py` lets older
byte-diff tests undo this ticket's markup.

## Mobile fix (Ann, 304px)

`tools/nj_history/history.css` (copied to `/history.css`) gains `@media (max-width: 640px) { .hist-panels { grid-template-columns: minmax(0, 1fr); } }` after the existing 640px block: the `minmax(304px,358px)` column was wider than the 272px content box at 304px viewport width (scrollWidth 320) on district pages. Pinned in tests/test_k12_hist_panels_mobile.py.

## Out of scope

Google Search Console writes (no sitemap resubmit, no URL inspection; OQ-7); IndexNow/Bing (OQ-8); per-district summary sentences (OQ-2; done in
K12-DISTRICT-SUMMARIES-001, `docs/nj-district-summaries.md`); medians or other county statistics (OQ-3); linking the `/nj/` County cells (OQ-10); noindex or removal of any page
and any change to `/api/v1/nj/` (OQ-9); the `/nj/history/` breadcrumb; backlinks and outreach.
