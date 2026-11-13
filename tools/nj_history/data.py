"""Data layer: pinned inputs, validation, derived coverage. No rendering here.

Reads only the inputs named in the data contract (see INPUT_PATHS), from a pinned git object of the
k12comp data repo (git show <commit>:<path>), or, in test-only fixture mode, from a fixture directory.
Guide cells come from the site's own published API files (the cells the site shows), cross-checked
against the pinned salary-cell file. Nothing is summed, averaged, rounded, interpolated or estimated.
"""
import csv
import hashlib
import io
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
WINDOW = ("2019-20", "2020-21", "2021-22", "2022-23", "2023-24", "2024-25", "2025-26")
GROUPS = ("teacher", "administrator", "special_service", "supervisor_coordinator")
REASONS = ("n_lt_10", "complementary")
SERIES_LABEL = "salary guide (negotiated)"
PARTIAL_LABEL = "partial history"
STAFF_FILE_COLS = ["state", "school_year", "nces_leaid", "nj_county_district_code", "district", "staff_group",
                   "headcount", "fte_sum", "suppressed", "suppression_reason", "source_url", "sha256"]
STAFF_PUB_COLS = ["state", "school_year", "nces_leaid", "nj_county_district_code", "district", "staff_group",
                  "headcount", "fte_sum", "suppressed", "suppression_reason", "source_url", "sha256", "retrieved_at"]
COVERAGE_COLS = ["school_year", "district_years", "with_salary_guide", "coverage_pct", "label", "series_label"]
# per-district file: staff rows plus that district's coverage row under one header (union of the two allowlists)
DISTRICT_FILE_COLS = STAFF_PUB_COLS + [c for c in COVERAGE_COLS if c not in STAFF_PUB_COLS]
MANIFEST_COLS = ["school_year", "url", "http_status", "sha256", "bytes", "retrieved_at", "identity_evidence", "status"]
COVERAGE_FILE_COLS = COVERAGE_COLS
INPUT_PATHS = tuple(f"data/nj_district_staff_{y}.csv" for y in WINDOW) + (
    "sources/nj_cs_manifest.csv", "data/nj-salary_cell.csv", "data/nj_history_coverage.csv")
# OQ-3 (locked): coverage counts exactly the guide cells the site publishes. The data file holds these LEAIDs
# back (K12-CLIFTON-IDENTITY-GUARD-001); the cross-check may differ only by them.
COVERAGE_EXCEPTIONS = {"3403300": "Clifton City (held in data/nj_history_coverage.csv, published on the site)"}
TZ = ZoneInfo("America/Toronto")


class BuildError(Exception):
    pass


def sha256_hex(b):
    return hashlib.sha256(b).hexdigest()


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def read_csv_text(text, cols=None, what="csv"):
    rd = csv.reader(io.StringIO(text, newline=""))
    rows = list(rd)
    if not rows:
        raise BuildError(f"{what}: empty file")
    head = rows[0]
    if cols is not None and head != list(cols):
        raise BuildError(f"{what}: header {head} is not the expected {list(cols)}")
    out = []
    for i, r in enumerate(rows[1:], 2):
        if len(r) != len(head):
            raise BuildError(f"{what}: line {i} has {len(r)} fields, expected {len(head)}")
        out.append(dict(zip(head, r)))
    return head, out


class Inputs:
    """Reads the pinned inputs. Every read goes through read(); any path outside INPUT_PATHS is refused."""

    def __init__(self, lock, repo=None, fixture_dir=None):
        self.lock, self.repo, self.fixture_dir = lock, repo, fixture_dir
        self.reads = []
        if fixture_dir is not None:
            if os.environ.get("K12_FIXTURE_MODE") != "1":
                raise BuildError("fixture inputs need K12_FIXTURE_MODE=1 (test-only)")
        else:
            if not repo:
                raise BuildError("no data repo: set K12_DATA_REPO or pass --data-repo")
            self._verify_commit()

    def _git(self, *args):
        p = subprocess.run(["git", "-C", self.repo, *args], capture_output=True)
        if p.returncode != 0:
            raise BuildError("git " + " ".join(args[:2]) + " failed")
        return p.stdout

    def _verify_commit(self):
        want = self.lock["data_commit"]
        got = self._git("rev-parse", "--verify", want + "^{commit}").decode().strip()
        if got != want:
            raise BuildError(f"pinned commit mismatch: {got} != {want}")

    def read(self, path):
        if path not in INPUT_PATHS:
            raise BuildError(f"not an allowed build input: {path}")
        if self.fixture_dir is not None:
            with open(os.path.join(self.fixture_dir, *path.split("/")), "rb") as f:
                raw = f.read()
        else:
            raw = self._git("show", f"{self.lock['data_commit']}:{path}")
            want = self.lock["inputs"].get(path)
            if want != sha256_hex(raw):
                raise BuildError(f"pin sha256 mismatch for {path}")
        self.reads.append(path)
        return raw.decode("utf-8")


def load_lock(path=None):
    lock = load_json(path or os.path.join(HERE, "pin.json"))
    for k in ("data_commit", "inputs", "names", "snapshot_date"):
        if k not in lock:
            raise BuildError(f"lock missing {k}")
    if set(lock["inputs"]) != set(INPUT_PATHS):
        raise BuildError("lock inputs differ from the data contract")
    return lock


def load_names(names_dir, lock, verify=True):
    out = {}
    for key, fn in (("district_names", "district_names.csv"), ("staff_names", "nj_staff_district_names.csv")):
        p = os.path.join(names_dir, fn)
        with open(p, "rb") as f:
            raw = f.read()
        if verify and lock["names"].get(fn) != sha256_hex(raw):
            raise BuildError(f"name table hash differs from the lock: {fn}")
        cols = ["nces_leaid", "district"] if key == "district_names" else ["nj_county_district_code", "district"]
        _, rows = read_csv_text(raw.decode("utf-8"), cols, fn)
        d = {r[cols[0]]: r[cols[1]] for r in rows}
        if len(d) != len(rows):
            raise BuildError(f"duplicate key in {fn}")
        out[key] = d
    return out["district_names"], out["staff_names"]


# ---------- formatting (shared by pages, tables and tests) ----------
def fmt_fte(s):
    """Verbatim CSV string; the only change is a thousands comma."""
    whole, dec = s.split(".")
    return f"{int(whole):,}.{dec}"


def pct_text(w, t):
    """One decimal, the collector's format; never '50.0' beside the partial label (AC 13f clamp)."""
    s = f"{100 * w / t:.1f}"
    if is_partial(w, t) and float(s) >= 50.0:
        s = f"{(1000 * w // t) / 10:.1f}"
    return s


def is_partial(w, t):
    return t > 0 and 2 * w < t


def collector_pct(w, t):
    return f"{100 * w / t:.1f}" if t else ""


def local_date(ts):
    dt = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    return dt.astimezone(TZ).strftime("%Y-%m-%d")


# ---------- staff + manifest ----------
def load_manifest(inputs):
    _, rows = read_csv_text(inputs.read("sources/nj_cs_manifest.csv"), MANIFEST_COLS, "manifest")
    by = {}
    for r in rows:
        if r["school_year"] in by:
            raise BuildError(f"manifest: duplicate year {r['school_year']}")
        by[r["school_year"]] = r
    for y in WINDOW:
        if y not in by:
            raise BuildError(f"manifest: no row for {y}")
        if by[y]["status"] != "ok":
            raise BuildError(f"manifest: {y} status is {by[y]['status']!r}, not ok")
        if not re.fullmatch(r"https://www\.nj\.gov/education/doedata/cs/\S+", by[y]["url"]):
            raise BuildError(f"manifest: {y} url is not an NJDOE Certificated Staff url")
        if not re.fullmatch(r"[0-9a-f]{64}", by[y]["sha256"]):
            raise BuildError(f"manifest: {y} sha256 malformed")
        if not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", by[y]["retrieved_at"]):
            raise BuildError(f"manifest: {y} retrieved_at malformed")
    extra = set(by) - set(WINDOW)
    if extra:
        raise BuildError(f"manifest: years outside the window: {sorted(extra)}")
    return by


def load_staff(inputs, manifest):
    """All staff rows in source order, each validated against its manifest year. Returns raw dicts (12 cols)."""
    rows = []
    for y in WINDOW:
        _, part = read_csv_text(inputs.read(f"data/nj_district_staff_{y}.csv"), STAFF_FILE_COLS, f"staff {y}")
        m = manifest[y]
        for i, r in enumerate(part, 2):
            where = f"staff {y} line {i}"
            if r["state"] != "NJ" or r["school_year"] != y:
                raise BuildError(f"{where}: state/school_year not NJ/{y}")
            if r["sha256"] != m["sha256"]:
                raise BuildError(f"{where}: sha256 differs from the manifest")
            if r["source_url"] != m["url"]:
                raise BuildError(f"{where}: source_url differs from the manifest")
            if r["nces_leaid"] and not re.fullmatch(r"\d{7}", r["nces_leaid"]):
                raise BuildError(f"{where}: nces_leaid malformed")
            if not re.fullmatch(r"\d\d-\d{4}", r["nj_county_district_code"]):
                raise BuildError(f"{where}: nj_county_district_code malformed")
            if r["staff_group"] not in GROUPS:
                raise BuildError(f"{where}: staff_group not allowed")
            if r["headcount"] != "":
                raise BuildError(f"{where}: headcount must be empty")
            if r["suppressed"] == "true":
                if r["fte_sum"] != "":
                    raise BuildError(f"{where}: suppressed row carries fte_sum")
                if r["suppression_reason"] not in REASONS:
                    raise BuildError(f"{where}: suppression_reason not allowed")
            elif r["suppressed"] == "false":
                if not re.fullmatch(r"\d+\.\d", r["fte_sum"]):
                    raise BuildError(f"{where}: fte_sum malformed")
                if r["suppression_reason"] != "":
                    raise BuildError(f"{where}: reason on an unsuppressed row")
            else:
                raise BuildError(f"{where}: suppressed must be true or false")
            rows.append(r)
    return rows


# ---------- guides (the cells the site publishes) ----------
def is_perc_url(u):
    p = urlparse(u)
    return p.scheme == "https" and ((p.hostname or "").startswith("perc.") or p.path.lower().startswith("/perc/")
                                    or "perc" in (p.hostname or "").split("."))


# K12-NJ-DEADLINK-001: the Edison Twp contract short link below is dead (redirect chain ends in a 404). The district's current copy
# of the same document (identical text, same sha256 of the extracted copy) replaces it wherever a guide source URL is read. The build reads
# the site's own api/v1/nj files, and the release/tests rebuild from a pre-fix site tree, so the substitution lives here, not in the data repo.
SOURCE_URL_OVERRIDES = {
    "https://5il" ".co/2u0cp": "https://files-backend.assets.thrillshare.com/documents/asset/uploaded_file/4500/Eps/"
                            "7025b86b-a5ce-4996-9ba2-429cad8337e7/ETEA-Certified-Contract-July-2023-June-2028.pdf",
}


def apply_source_url_overrides(page):
    """K12-NJ-DEADLINK-001: the old URL in a district page (links, JSON-LD) becomes the new one; so does the short link text (the URL's last path segment)."""
    for old, new in SOURCE_URL_OVERRIDES.items():
        page = page.replace(f"{old}\">{old.rsplit('/', 1)[1]}</a>", f"{new}\">{new.rsplit('/', 1)[1]}</a>").replace(old, new)
    return page


def guide_cells_from_site(site_root, leaid):
    """Published teacher guide cells inside the window: the site's own API file for the district."""
    p = os.path.join(site_root, "api", "v1", "nj", f"{leaid}.json")
    if not os.path.exists(p):
        return {}
    d = load_json(p)
    out = {}
    for c in d.get("salary_cells", []):
        if c.get("staff_group") != "teacher" or not c.get("salary_usd") or c.get("identity_status") != "verified":
            continue
        y = c.get("school_year")
        if y not in WINDOW:
            continue
        cur = out.setdefault(y, {}).get(c["sha256"])
        if cur is None or (c.get("retrieved_at") or "") < (cur["retrieved_at"] or ""):
            out[y][c["sha256"]] = {
                "sha256": c["sha256"], "source_type": c.get("source_type"), "source_url": SOURCE_URL_OVERRIDES.get(c.get("source_url"), c.get("source_url")),
                "citation": c.get("citation"), "retrieved_at": c.get("retrieved_at")}
    return {y: [v[k] for k in sorted(v)] for y, v in out.items()}


def salary_file_pairs(inputs, leaids):
    """Cross-check only: (leaid, year) pairs the pinned salary-cell file holds as verified teacher cells."""
    _, rows = read_csv_text(inputs.read("data/nj-salary_cell.csv"), None, "salary cells")
    need = {"nces_leaid", "school_year", "staff_group", "salary_usd", "identity_status"}
    if rows and not need <= set(rows[0]):
        raise BuildError("salary cells: expected columns missing")
    return {(r["nces_leaid"], r["school_year"]) for r in rows
            if r["staff_group"] == "teacher" and r["salary_usd"] and r["identity_status"] == "verified"
            and r["school_year"] in WINDOW and r["nces_leaid"] in leaids}


class History:
    """Everything derived from the pinned inputs. Built once per run."""

    def __init__(self, inputs, site_root, district_names, staff_names, page_leaids, lock):
        self.lock, self.district_names, self.staff_names = lock, district_names, staff_names
        self.page_leaids = sorted(page_leaids)
        self.manifest = load_manifest(inputs)
        raw = load_staff(inputs, self.manifest)
        self.raw_rows = raw
        # published rows: allowlisted columns only, names from the two site tables, retrieved_at from the manifest
        self.rows = []
        for r in raw:
            code = r["nj_county_district_code"]
            if code not in staff_names:
                raise BuildError(f"no display name for county district code {code}")
            row = {c: r[c] for c in STAFF_FILE_COLS}
            row["district"] = staff_names[code]
            row["retrieved_at"] = self.manifest[r["school_year"]]["retrieved_at"]
            self.rows.append(row)
        self.by_leaid, self._rows_by_leaid = {}, {}
        for r in self.rows:
            if r["nces_leaid"]:
                self._rows_by_leaid.setdefault(r["nces_leaid"], []).append(r)
                self.by_leaid.setdefault(r["nces_leaid"], {}).setdefault(r["school_year"], {})[r["staff_group"]] = r
        self.years_with_rows = {l: [y for y in WINDOW if y in ys] for l, ys in self.by_leaid.items()}
        # guides
        self.guide_sources = {l: guide_cells_from_site(site_root, l) for l in self.page_leaids}
        self.guide_sources = {l: g for l, g in self.guide_sources.items() if g}
        self.guide_pairs = {(l, y) for l, g in self.guide_sources.items() for y in g}
        sal = salary_file_pairs(inputs, set(self.page_leaids))
        if sal != self.guide_pairs:
            raise BuildError("published guide years differ from the pinned salary-cell file: "
                             f"{sorted(self.guide_pairs ^ sal)[:6]}")
        # district coverage: k counts guide years that are also years with a staff row
        self.cov = {}
        for l in self.page_leaids:
            ys = self.years_with_rows.get(l, [])
            ks = [y for y in ys if (l, y) in self.guide_pairs]
            self.cov[l] = {"n": len(ys), "k": len(ks), "guide_years": ks}
        # statewide: identical to collector compute(), with the site's published cells as numerator
        dy = {y: set() for y in WINDOW}
        for r in self.rows:
            if r["nces_leaid"]:
                dy[r["school_year"]].add(r["nces_leaid"])
        self.state_rows = []
        tw = tt = 0
        for y in WINDOW:
            t = len(dy[y])
            w = sum(1 for l in dy[y] if (l, y) in self.guide_pairs)
            tw, tt = tw + w, tt + t
            self.state_rows.append(self._cov_row(y, w, t))
        self.state_rows.append(self._cov_row("ALL", tw, tt))
        self.guide_pairs_counted = {(l, y) for y in WINDOW for l in dy[y] if (l, y) in self.guide_pairs}
        # published/suppressed row counts per year and group (rows, not people; blank-LEAID rows included)
        self.group_counts = {(y, g): [0, 0] for y in WINDOW for g in GROUPS}
        for r in self.rows:
            self.group_counts[(r["school_year"], r["staff_group"])][1 if r["suppressed"] == "true" else 0] += 1
        self.crosscheck = self._crosscheck(inputs)

    @staticmethod
    def _cov_row(y, w, t):
        return {"school_year": y, "district_years": str(t), "with_salary_guide": str(w),
                "coverage_pct": collector_pct(w, t), "label": PARTIAL_LABEL if is_partial(w, t) else "",
                "series_label": SERIES_LABEL}

    def _crosscheck(self, inputs):
        """AC 13: denominators equal the data file; numerators equal it or differ only by COVERAGE_EXCEPTIONS."""
        _, frows = read_csv_text(inputs.read("data/nj_history_coverage.csv"), COVERAGE_FILE_COLS, "coverage file")
        fmap = {r["school_year"]: r for r in frows}
        report = {"file": {k: [v["district_years"], v["with_salary_guide"]] for k, v in fmap.items()},
                  "site": {r["school_year"]: [r["district_years"], r["with_salary_guide"]] for r in self.state_rows},
                  "exception_leaids": sorted(COVERAGE_EXCEPTIONS), "differences": []}
        for r in self.state_rows:
            y = r["school_year"]
            if y not in fmap:
                raise BuildError(f"coverage file has no row for {y}")
            f = fmap[y]
            if f["district_years"] != r["district_years"]:
                raise BuildError(f"coverage denominator for {y}: site {r['district_years']} != file {f['district_years']}")
            if f["with_salary_guide"] != r["with_salary_guide"]:
                if y == "ALL":
                    excl = sum(1 for (l, yy) in self.guide_pairs_counted if l in COVERAGE_EXCEPTIONS)
                else:
                    excl = sum(1 for (l, yy) in self.guide_pairs_counted if yy == y and l in COVERAGE_EXCEPTIONS)
                if int(r["with_salary_guide"]) - excl != int(f["with_salary_guide"]):
                    raise BuildError(f"coverage numerator for {y}: site {r['with_salary_guide']} differs from file "
                                     f"{f['with_salary_guide']} by more than {sorted(COVERAGE_EXCEPTIONS)}")
                report["differences"].append({"school_year": y, "site": int(r["with_salary_guide"]),
                                              "file": int(f["with_salary_guide"]), "leaids": sorted(COVERAGE_EXCEPTIONS)})
        extra = [k for k in fmap if k not in WINDOW and k != "ALL"]
        if extra:
            raise BuildError(f"coverage file has unexpected rows: {extra}")
        return report

    # ---------- per-district helpers ----------
    def district_rows(self, leaid):
        """That district's published staff rows, in source order."""
        return self._rows_by_leaid.get(leaid, [])

    def district_coverage_row(self, leaid):
        c = self.cov[leaid]
        return {"school_year": "ALL", "nces_leaid": leaid, "district": self.district_names[leaid],
                "district_years": str(c["n"]), "with_salary_guide": str(c["k"]),
                "coverage_pct": collector_pct(c["k"], c["n"]),
                "label": PARTIAL_LABEL if is_partial(c["k"], c["n"]) else "", "series_label": SERIES_LABEL}
