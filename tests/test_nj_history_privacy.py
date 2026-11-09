"""AC 21 and AC 22: planted canaries never reach an output file; no UFB or person data in history outputs."""
import csv
import io
import json
import os
import re
import unittest
from unittest import mock

import nj_history_helpers as H
from nj_history import build as B, data as D

NAME = "Jane " + "Plantedname"
ID = "ZZ-" + "123456"
PLANT = f"{NAME} {ID}"


def fixture_files(mutate):
    files = {p: H.pinned(p) for p in D.INPUT_PATHS}
    mutate(files)
    d = H.tmpdir("k12nj-canary-")
    for p, t in files.items():
        fp = os.path.join(d, *p.split("/"))
        os.makedirs(os.path.dirname(fp), exist_ok=True)
        open(fp, "w", encoding="utf-8", newline="").write(t)
    # the M4 PERC-signatory fixture, planted with the canary; it is not an allowed input and must never be read
    fx = os.path.join(d, "tests", "fixtures", "nj_cs")
    os.makedirs(fx)
    open(os.path.join(fx, "perc_signatory.txt"), "w").write(f"Agreement between the Alpha Board and the Association.\nSigned: {PLANT}, President\n")
    return d


def leaks(out):
    hits = []
    for dp, _, fs in os.walk(out):
        for f in fs:
            raw = open(os.path.join(dp, f), "rb").read().lower()
            if NAME.lower().encode() in raw or ID.lower().encode() in raw:
                hits.append(os.path.join(dp, f))
    return hits


def run_fixture(mutate):
    d = fixture_files(mutate)
    out = os.path.join(H.tmpdir("k12nj-canary-out-"), "site")
    with mock.patch.dict(os.environ, {"K12_FIXTURE_MODE": "1"}):
        B.run(site_root=H.site_tree(), out_dir=out, fixture_dir=d)
    return out


def plant_staff_column(col):
    def m(files):
        p = "data/nj_district_staff_2022-23.csv"
        rows = list(csv.reader(io.StringIO(files[p], newline="")))
        i = rows[0].index(col)
        for r in rows[1:4] + rows[500:503]:
            r[i] = PLANT
        buf = io.StringIO(newline="")
        csv.writer(buf, lineterminator="\n").writerows(rows)
        files[p] = buf.getvalue()
    return m


class Canary(unittest.TestCase):
    def test_ac21_every_staff_column(self):
        outcomes = {}
        for col in D.STAFF_FILE_COLS:
            try:
                out = run_fixture(plant_staff_column(col))
            except D.BuildError:
                outcomes[col] = "validation error"
                continue
            self.assertEqual(leaks(out), [], col)
            outcomes[col] = "built, no leak"
        # district is replaced by the committed name table; the rest are validated against the manifest and enums
        self.assertEqual(outcomes["district"], "built, no leak")
        self.assertEqual({c for c, o in outcomes.items() if o == "validation error"} | {"district"}, set(D.STAFF_FILE_COLS))

    def test_ac21_extra_non_allowlisted_column(self):
        def m(files):
            p = "data/nj_district_staff_2021-22.csv"
            lines = files[p].split("\n")
            files[p] = "\n".join((l + ",notes" if i == 0 else l + "," + PLANT) if l else l for i, l in enumerate(lines))
        with self.assertRaises(D.BuildError):
            run_fixture(m)

    def test_ac21_salary_cell_free_text_columns(self):
        def m(files):
            p = "data/nj-salary_cell.csv"
            rows = list(csv.reader(io.StringIO(files[p], newline="")))
            free = [rows[0].index(c) for c in rows[0] if c not in ("nces_leaid", "school_year", "staff_group", "salary_usd", "identity_status")]
            for r in rows[1:]:
                for i in free:
                    r[i] = PLANT
            buf = io.StringIO(newline="")
            csv.writer(buf, lineterminator="\n").writerows(rows)
            files[p] = buf.getvalue()
        out = run_fixture(m)
        self.assertEqual(leaks(out), [])

    def test_ac21_perc_signatory_fixture_is_never_read_or_published(self):
        out = run_fixture(lambda files: None)
        self.assertEqual(leaks(out), [])

    def test_ac21_canary_in_the_site_guide_json_only_reaches_allowlisted_fields(self):
        """A planted name in a published cell's free text does not surface: only citation/source fields are rendered, and they are asserted."""
        site = H.tmpdir("k12nj-site-")
        import shutil
        shutil.copytree(H.site_tree(), os.path.join(site, "s"))
        p = os.path.join(site, "s", "api", "v1", "nj", "3416230.json")
        d = json.load(open(p))
        for c in d["salary_cells"]:
            c["guide_name"] = PLANT
            c["lane_label"] = PLANT
        json.dump(d, open(p, "w"), sort_keys=True)
        out = os.path.join(H.tmpdir("k12nj-canary-out-"), "site")
        B.run(site_root=os.path.join(site, "s"), out_dir=out, data_repo=H.DATA_REPO)
        hits = [h for h in leaks(out) if "/api/v1/" not in h]  # the copied API file itself is the unchanged site input
        self.assertEqual(hits, [])

    def test_real_build_has_no_canary(self):
        out, _ = H.built()
        self.assertEqual(leaks(out), [])


FORBIDDEN = re.compile(r"budget/ufb|employees2|person_name|superintendent|base_salary|ufb_", re.I)


class NoUfbOrPerson(unittest.TestCase):
    def test_ac22_history_outputs_are_clean(self):
        out, _ = H.built()
        pages = B.discover_pages(H.site_tree())
        for leaid, path in pages.items():
            p = H.read(out, path.strip("/") + "/index.html")
            sec = H.history_section(p)
            self.assertIsNone(FORBIDDEN.search(sec), (leaid, FORBIDDEN.search(sec)))
            m = re.search(r'<script type="application/ld\+json" id="ld-nj-history">(.*?)</script>', p, re.S)
            if m:
                self.assertIsNone(FORBIDDEN.search(m.group(1)), leaid)
        sw = H.read(out, "nj/history/index.html")
        main = sw[sw.index('<main id="main">'):sw.index("</main>")]
        self.assertIsNone(FORBIDDEN.search(main))
        self.assertIsNone(FORBIDDEN.search(re.search(r'id="ld-nj-history">(.*?)</script>', sw, re.S).group(1)))
        for dp, _, fs in os.walk(os.path.join(out, "data", "nj")):
            for f in fs:
                t = open(os.path.join(dp, f), encoding="utf-8").read()
                self.assertIsNone(FORBIDDEN.search(t), f)
                self.assertTrue(csv.reader(io.StringIO(t)).__next__() in (D.STAFF_PUB_COLS, D.COVERAGE_COLS, D.DISTRICT_FILE_COLS), f)

    def test_ac22_no_person_types_or_names_in_history_jsonld(self):
        out, _ = H.built()
        for rel in ("nj/history/index.html", "nj/toms-river-regional-3416230/index.html"):
            p = H.read(out, rel)
            blob = re.search(r'id="ld-nj-history">(.*?)</script>', p, re.S).group(1)
            self.assertNotIn("Person", blob)


if __name__ == "__main__":
    unittest.main()
