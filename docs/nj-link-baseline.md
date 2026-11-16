# /nj/ link baseline (K12-NJ-UPKEEP-001)

`tools/nj_link_baseline.py` lists every external source and district link on the k12comp.com /nj/ pages, checks it politely and compares it
with the committed baseline `docs/nj-link-baseline.tsv`. It is stdlib-only Python. `docs/` is excluded from the published site (`_config.yml`),
so the baseline is not public.

## What it scans

- **Pages:** tracked `nj/**/*.html` (`git ls-files` in a git tree, otherwise a walk of `--root`): 586 district pages, `/nj/` and `/nj/history/`.
- **External URLs:** absolute http(s) values of `href`, `src`, `content` and `action` attributes and every URL in a JSON-LD block on those pages,
  plus every URL in `api/v1/nj/*.json` and in any file under `data/nj/` (CSV cells are read with the csv module).
- **Excluded (not source links):** k12comp.com (internal; resolved as a local ref instead), schema.org, creativecommons.org (licence),
  gc.zgo.at and k12comp.goatcounter.com (GoatCounter), hazeydata.ai (subscribe form).
- **Deduplication:** on the exact published string. No percent-decoding (`Certificated%20Staff%202021.zip` is requested as written), query strings
  are kept (`DisplayFile.aspx?itemId=...` is its own URL), and a fragment is stripped only when the URL is requested.
- **Local refs:** every relative, root-relative or `https://k12comp.com/...` `href`/`src` (and every k12comp.com `content`, `action` or JSON-LD
  URL) on the pages must resolve to a file in the tree: the path itself or its `index.html`.

The baseline has one row per unique URL, sorted by URL, with the columns
`url, pages, example_page, status, final_url, content_type, content_length, last_modified, etag, checked_at_utc`.
`pages` is the number of /nj/ pages carrying the URL (0 for a URL found only in `api/` or `data/`); `example_page` is the first such page, or
the first `api/`/`data/` file when no page carries it. A header the server does not send stays blank (West Windsor-Plainsboro sends no
last-modified or etag).

## Run modes

From the repo root:

```
python3 tools/nj_link_baseline.py --offline
python3 tools/nj_link_baseline.py --live --log link-requests.log --report link-report.md
python3 tools/nj_link_baseline.py --write-baseline --log link-requests.log
```

- **`--offline`** (the default; no network). Prints pages scanned, unique external URLs, local refs (and unique targets) and unresolved local
  refs, then exits 1 on any of: a URL with no baseline row, a baseline row whose URL is on no page, JSON or data file (stale), a baseline
  row whose status is not 2xx, an unresolved local ref, or a missing baseline file. Each problem is named on its own `FAIL` line.
  At dd15360d: 588 pages, 18 unique external URLs, 0 unresolved. `--root DIR` scans another tree (the tests use scratch copies);
  `--baseline FILE` reads another baseline.
- **`--live`** checks every URL found in the tree and every baseline URL on the network and compares each with its baseline row (classes below).
  Prints a summary and every WARN/FAIL line; `--report FILE` writes a markdown report (summary, request counts, minimum gap between request
  starts, one table row per URL); `--log FILE` writes one line per request: the UTC start time with milliseconds, method, URL, status
  (or `ERR-dns`, `ERR-tls`, `ERR-timeout`, `ERR-conn`) and body bytes read, tab-separated. Exit 1 on any FAIL (the URL is named on the
  `live: FAIL` line) or any offline problem, else 0. Timeouts are WARN and say "re-run".
- **`--write-baseline`** runs the same live check on every URL found in the tree (classified against the old baseline row when there is
  one), then rewrites `docs/nj-link-baseline.tsv`. It refuses (exit 1, file untouched) when any URL is FAIL, any request timed out, or any
  final status is not 2xx (a 401/403/429 cannot be baselined either). WARNs (a changed etag, length or date) do not block a rewrite: that is
  the refresh. Never baseline a dead link: a document URL (.csv, .zip, ...) answered with a 200 text/html page is a soft-404 FAIL even on a
  first run with no baseline.

## Classification (live)

Per URL, on the final response after redirects:

| class | when |
|---|---|
| FAIL | final status 404, 410 or any other 4xx except 401/403/429; any 5xx; a redirect chain ending in a FAIL status (the old Edison short-link pattern: 301 to a 404), or not ending (a 3xx with no Location, or more than 10 hops); DNS failure; TLS failure; connection refused or reset; a final content-type that flips from a document type in the baseline (pdf, csv, text/plain, zip, xlsx/xls) to text/html (soft-404 landing page); text/html for a URL whose path ends in a document extension (.pdf, .csv, .zip, .xlsx, .xls, .txt), with or without a baseline row |
| WARN (exit 0, listed) | 401, 403, 429; timeout ("re-run"); an etag, content-length, last-modified or final_url host that differs from the baseline: "source changed: re-hash per PLAN §4" |
| PASS | 2xx after redirects, none of the above |

www.nj.gov sits behind a bot filter that now and then answers a document URL with a short 200 `text/html` page (seen on Nov 16, 2026:
3 of 18 URLs on one run, all 18 real files on the next). The tool reads that as a soft-404 FAIL and `--write-baseline` refuses; re-run
once, a minute or more later, before treating the link as dead.

A header missing from both the baseline and the live response is not a change (no WARN). For a ranged GET answered with 206, content-length
is taken from the total in `Content-Range`, not the 1-byte part.

## Politeness

Strictly sequential; at least 1.1 s between any two request starts, and every redirect hop is a request with the same spacing. A HEAD
following redirects comes first and records `final_url`; a ranged GET (`Range: bytes=0-0`, following redirects) is sent only when the HEAD's
final status is not 2xx (for example a host that answers 405 or 403 to HEAD; 403 on both is WARN). At most 1 body byte is read and bodies are
never downloaded; 20 s timeout per request; User-Agent `k12comp-linkcheck/<version> (+https://k12comp.com/about/)`; no other retries.
18 URLs take about 20-40 s.

## Where it runs

- **CI:** offline only. The unittest suite (`tests/test_k12_nj_link_baseline.py`) runs the `--offline` check on the repo tree, the mutation
  cases on scratch trees and the classifier and politeness cases against a stubbed transport and a fake clock; it makes no request to nj.gov
  or any district host. No workflow runs `--live` or `--write-baseline`.
- **`--live`** runs (i) in test-run for every PR that touches `nj/`, `api/` or `data/`, and (ii) in the K12 owner's Monday daily run.
- No cron and no scheduled GitHub Action in v1 (unattended traffic to nj.gov and a new workflow to own); revisit if a dead link slips through.

## Refreshing the baseline

Run `--write-baseline` only in a PR that adds or removes a source URL, or after a WARN has been reviewed (a changed source is re-hashed per
PLAN §4 first). The PR diff of `docs/nj-link-baseline.tsv` is the record. A FAIL is never baselined: a dead link is fixed in its own
ticket (see K12-NJ-DEADLINK-001 in `docs/nj-history.md`), then the baseline is rewritten.
