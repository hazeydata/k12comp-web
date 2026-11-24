# K12-DISTRICT-SUMMARIES-001: one data-derived summary paragraph on every NJ district page

Google had indexed 1 of 590 known k12comp.com URLs (GSC, Nov 16, 2026) and a median 60% of a district page's 5-word shingles appear on most district
pages. This ticket adds one short paragraph to each of the 586 district pages that differs from every other page's and is built only from that
district's committed data. It is a content-uniqueness bet, not a finding: GSC movement is tracked as an outcome, not a merge gate. No salary, source URL,
sha256 line, chart, title, meta description, JSON-LD block, `api/` or `data/` file changes.

## The tool and the copy file

`tools/nj_district_summaries.py` (stdlib only; no network, subprocess or model; deterministic and idempotent):

    python3 tools/nj_district_summaries.py [site] --check           # exit 1 if any district page is not in its final form (site defaults to the repo root)
    python3 tools/nj_district_summaries.py [site] --write           # rewrite in place; also the default when neither flag is given
    python3 tools/nj_district_summaries.py [site] --trace out.json  # also write a trace, outside the site

Each page is first stripped of its own `<p class="district-summary" id="district-summary">...</p>` and the paragraph is then inserted, so a second run
changes no byte. It reads only `api/v1/nj/<leaid>.json`, `data/nj/history/<leaid>.csv` and the page itself (h1, county breadcrumb, the "Latest base salary"
block, the "Starts at" note); before `nj_indexing` has written the county breadcrumb it takes the county from the `/nj/` table's County cell, which is the
text `nj_indexing` then puts in the breadcrumb. The paragraph sits in `<main>` directly after `<p class="disclaimer">...</p>` and before whatever follows it
(`<section class="summary"` on every page today). Names are HTML-escaped (`&`, apostrophes). The district name is the JSON `district` field (the tool stops if
it differs from the h1).

**All English template strings live only in `tools/nj_district_summaries_copy.json`**, one key per slot (`S0`, `S0b`, `S1`, `S2`, `S3`, `SH`, `S4`, `S5`, `S5_one`) with
`{field}` placeholders, plus `"max_words": 80` and a `_status` object naming each slot's wording status: `APPROVED writing · Lindsay Bluth, Nov 24, 2026, 12:04 PM ET round 2` for every slot (final wording; no placeholders remain). The tool holds no English sentence (a test greps for that). Swapping a slot's wording is a
one-line edit of the copy file; then run `--write`, regenerate `tests/fixtures/k12_district_summaries/` and the sitemap (`nj_indexing.py --write`).

## Slots (in this order; one sentence each; 2 to 5 sentences per page, at most `max_words` words)

Salary page = at least one superintendent row with `salary_not_reported` false. "Latest" = the max `salary_year` among those rows. Dollars print as the page prints
them (`$263,750`), dates as in the JSON (ISO). A missing, blank, zero or suppressed value omits its slot: nothing prints `0`, `n/a` or an empty value.

- **S1** (salary pages, 575): `{district}` and `{county}` (page breadcrumb), `{base_salary}` and `{salary_year}` of the latest row. When the page's "Latest base salary"
  block shows a figure it is that row (on the 4 districts with more than one latest-year salary, 3401470, 3401860, 3407680 and 3412690, the row whose salary the page
  shows; the trace names it). On 6 pages (e.g. 3403660 Deerfield Twp) the block shows a newer "Not reported" row; S1 then states the latest *reported* year, which History lists.
- **S2** (two or more salary years, 573): `{base_salary}` and `{salary_year}` of the earliest salary year (the page's "Starts at" note; the tool stops if they differ).
  Raw values only: no difference, percentage or growth.
- **S3** (contract dates, 335): `{contract_start}`, `{contract_end}`, `{ufb_work_days}` of the S1 row. Omitted when the displayed S1 row (the row the page's "Latest base salary" block shows) has `term_ends_before_year` true
  (238 pages), and when the work days are 0 or blank (2 pages: 3400069 Bayshore Jointure Comm and 3407200 Highlands Boro; the dates branch is 337 = 575 - 238).
  The spec's "It is reported as a shared-service arrangement." add-on is dropped; SH is its own slot.
- **SH** (shared service, 40): when ANY latest-year row has `ufb_shared` = Y, independent of S3 (so also on term-ended pages). One fixed sentence, no fields, no digits:
  "The superintendent contract on file is reported as a shared-service arrangement." (approved writing, Lindsay Bluth, Nov 24, 2026, 11:19 AM ET).
- **S4** (teacher staff FTE, 577): the history CSV's latest `school_year`, `staff_group` = teacher, `suppressed` false, `fte_sum` printed exactly as the page's FTE section prints
  it (the CSV string with a thousands comma). Omitted when suppressed, blank, zero or when there is no CSV (Seaside Park Boro, 3414820).
- **S5** (teacher salary guides, 8): `{n_guide_years}` = the number of distinct `salary_cells` `school_year` values. Used when there are 2 or more guide years; this is the only formula in the summaries (the trace
  marks it `FORMULA`).
- **S5_one** (the singular form of S5, same 8-page S5 total): used instead of S5 when `n_guide_years` is 1 (Cherry Hill Twp, 3403000). No fields, no digit, so the trace has no
  token for it (7 `FORMULA` tokens remain). The tool only chooses the key; the sentence lives in the copy file.
- **S0** (no salary pages, 11): `{district}`, `{county}`. Then S4 when present.
- **S0b** (no salary and no S4: 3414820 Seaside Park Boro and 3410170 Milford Boro): one neutral fixed sentence, no fields, no digits, true on both pages.

No other number is derived: no rank, median, difference or percentage; part-time status (`ufb_fte` other than 1) is not mentioned.

## Run order

1. The history build (`docs/nj-history.md`).
2. The existing rewrites, each `--write`: `nj_api_index` -> `nj_guide_tables` -> `nj_fte_marks` -> `nj_mobile_chart_fit` -> `nj_chart_label_edge`.
3. `tools/nj_district_summaries.py --write` (this tool).
4. `tools/nj_indexing.py --write` last (it regenerates `sitemap.xml`).

`RELEASE_DATE` in `tools/nj_indexing.py` is bumped to `2026-11-24` with this change, so every district page's sitemap `lastmod` is `max(Updated, RELEASE_DATE)` = `2026-11-24`
(611 URLs). The run order in `docs/nj-indexing.md` and `tests/test_nj_history_committed.py` (`expected_final`: `expected_fte` -> `expected_summaries` -> `expected_indexing`)
includes this step.

## Trace

`--trace <path>` writes JSON `{leaid: {"page", "summary", "tokens": [{"token", "slot", "source", "path", "rendered"}]}}`. Every number-like token of the summary
(`$263,750`, `2026-27`, `2026-07-01`, `693.7`, `260`, `8`, any digit) maps to `api/v1/nj/<leaid>.json` + `superintendent_contracts[i].<field>`, or to
`data/nj/history/<leaid>.csv` + `row <n> <field>`, plus the rendered string; S5's count is marked `FORMULA count(distinct salary_cells[*].school_year)`. The trace must be
written outside the site.

## Tests

`tests/test_k12_district_summaries.py` (own parsers and own recompute): AST import allowlist and no English sentence literal in the tool; copy-file keys, statuses and
`max_words`; `--write` twice and `--check` on a scratch copy (sha256 of every file), a stale tree, a rebuild from pages without the paragraph; 586 pages with one paragraph at the
position and no other page with one; 2 to 5 sentences, at most 80 words; a recompute of all 586 with 0 mismatches and every digit traced; S1 against the page's latest figure
and label; branch counts against a fresh recount (S1 575, S2 573, S3 335 = 337 dates branch - 2 zero-work-day pages, SH 40, S4 577, S5 8, S0 11, S0b 2); no person name, UFB token or
suppressed value (the `FORBIDDEN` guard of `tests/test_nj_history_privacy.py` without the role word, plus a planted-name canary); 14 golden paragraphs under
`tests/fixtures/k12_district_summaries/` byte for byte (including SH on 3400990 and 3401590 and not on 3416800); 586 distinct summaries; every district page equal to
`bd37e392` apart from the paragraph; only `tools/`, `tests/`, `docs/`, district pages and `sitemap.xml` changed. `tests/k12_district_summaries_helpers.py` (`strip`) lets older byte-diff
tests undo this paragraph (`tests/k12_indexing_helpers.py` `undo` calls it).
