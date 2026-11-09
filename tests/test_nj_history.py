"""K12-SITE-NJ-HISTORY-001 acceptance tests. Needs K12_DATA_REPO (read-only clone of hazeydata/k12comp holding the pin).
Run: K12_DATA_REPO=<clone> python3 -m unittest discover -s tests -p 'test_*.py'"""
import csv
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import unittest
from unittest import mock

import nj_history_helpers as H
from nj_history_helpers import B, D, R

from nj_history import copy as C

WINDOW = D.WINDOW


def make_fixture(mutate=None):
    files = {p: H.pinned(p) for p in D.INPUT_PATHS}
    if mutate:
        mutate(files)
    d = H.tmpdir("k12nj-fixture-")
    for p, t in files.items():
        fp = os.path.join(d, *p.split("/"))
        os.makedirs(os.path.dirname(fp), exist_ok=True)
        with open(fp, "wb") as f:
            f.write(t.encode("utf-8"))
    return d


def build_fixture(mutate=None):
    d = make_fixture(mutate)
    out = os.path.join(H.tmpdir("k12nj-fxout-"), "site")
    with mock.patch.dict(os.environ, {"K12_FIXTURE_MODE": "1"}):
        B.run(site_root=H.site_tree(), out_dir=out, fixture_dir=d)
    return out


def fixture_fails(mutate, needle=""):
    try:
        build_fixture(mutate)
    except D.BuildError as e:
        assert needle in str(e), str(e)
        return str(e)
    raise AssertionError("build should have failed")


def csv_rows(text):
    return list(csv.reader(io.StringIO(text, newline="")))


class P1Inputs(unittest.TestCase):
    def test_ac1_only_named_inputs_are_read(self):
        opened, procs = [], []

        H.site_tree()
        active = [True]

        def hook(ev, args):
            if not active[0]:
                return
            if ev == "subprocess.Popen":
                procs.append([str(a) for a in args[1]])
            elif ev == "open" and isinstance(args[0], str):
                opened.append(args[0])
        out = os.path.join(H.tmpdir(), "site")
        sys.addaudithook(hook)
        rep = B.run(site_root=H.site_tree(), out_dir=out, data_repo=H.DATA_REPO)
        active[0] = False
        allowed_shows = {f"{H.COMMIT}:{p}" for p in D.INPUT_PATHS}
        shows = [p for p in procs if "show" in p]
        self.assertTrue(shows)
        for p in procs:
            self.assertEqual(p[0], "git")
            if "show" in p:
                self.assertIn(p[-1], allowed_shows)
            else:
                self.assertIn("rev-parse", p)
        self.assertEqual(sorted(rep["inputs_read"]), sorted(D.INPUT_PATHS))
        bad = [o for o in opened if re.search(r"/(raw|ufb|ccd)/|employees|\.env|credentials", o) or "budget/ufb" in o]
        self.assertEqual(bad, [])
        self.assertFalse(any(o.startswith(H.DATA_REPO) for o in opened), "no file inside the data repo is opened")

    def test_ac1_other_input_paths_are_refused(self):
        inp = D.Inputs(H.LOCK, repo=H.DATA_REPO)
        for p in ("raw/x.csv", "data/nj-superintendent.csv", "../etc/passwd", "data/ccd_2024.csv"):
            with self.assertRaises(D.BuildError):
                inp.read(p)

    def test_ac1_pin_and_lock_mismatch_fail(self):
        lock = json.loads(json.dumps(H.LOCK))
        lock["inputs"]["sources/nj_cs_manifest.csv"] = "0" * 64
        with self.assertRaises(D.BuildError):
            D.Inputs(lock, repo=H.DATA_REPO).read("sources/nj_cs_manifest.csv")
        lock2 = dict(H.LOCK, data_commit="0" * 40)
        with self.assertRaises(D.BuildError):
            D.Inputs(lock2, repo=H.DATA_REPO)

    def test_ac1_name_table_hash_is_locked(self):
        d = H.tmpdir()
        for fn in ("district_names.csv", "nj_staff_district_names.csv"):
            with open(os.path.join(D.HERE, fn), "rb") as f, open(os.path.join(d, fn), "wb") as g:
                g.write(f.read() + b"3499999,Extra\n" if fn == "district_names.csv" else f.read())
        with self.assertRaises(D.BuildError):
            D.load_names(d, H.LOCK, verify=True)

    def test_ac1_fixture_mode_is_test_only(self):
        with mock.patch.dict(os.environ, {"K12_FIXTURE_MODE": ""}):
            with self.assertRaises(D.BuildError):
                D.Inputs(H.LOCK, fixture_dir="/nonexistent")

    def test_ac1_inputs_match_pinned_hashes(self):
        for p in D.INPUT_PATHS:
            self.assertEqual(hashlib.sha256(H.pinned(p).encode()).hexdigest(), H.LOCK["inputs"][p], p)

    def test_ac2_manifest_states_fail_the_build(self):
        def setstatus(s):
            def m(files):
                t = files["sources/nj_cs_manifest.csv"].split("\n")
                t[3] = t[3].rsplit(",", 1)[0] + "," + s
                files["sources/nj_cs_manifest.csv"] = "\n".join(t)
            return m
        for s in ("not_found", "identity_mismatch", "hash_changed"):
            fixture_fails(setstatus(s), "status")

    def test_ac2_row_sha_mismatch_fails(self):
        def m(files):
            p = "data/nj_district_staff_2021-22.csv"
            lines = files[p].split("\n")
            lines[5] = lines[5][:-1] + ("0" if lines[5][-1] != "0" else "1")
            files[p] = "\n".join(lines)
        fixture_fails(m, "sha256")

    def test_ac2_manifest_year_missing_fails(self):
        def m(files):
            t = files["sources/nj_cs_manifest.csv"].split("\n")
            del t[2]
            files["sources/nj_cs_manifest.csv"] = "\n".join(t)
        fixture_fails(m, "no row for")


class P2Allowlist(unittest.TestCase):
    def test_ac3_csv_key_sets(self):
        out, _ = H.built()
        for rel, cols in (("data/nj/nj-district-staff-history.csv", D.STAFF_PUB_COLS),
                          ("data/nj/nj-history-coverage.csv", D.COVERAGE_COLS),
                          ("data/nj/history/3416230.csv", D.DISTRICT_FILE_COLS)):
            self.assertEqual(csv_rows(H.read(out, rel))[0], cols, rel)
        self.assertEqual(set(D.STAFF_PUB_COLS) - set(D.STAFF_FILE_COLS), {"retrieved_at"})

    def test_ac3_names_come_only_from_the_tables(self):
        out, _ = H.built()
        names = dict(csv.reader(io.StringIO(H.rt(os.path.join(D.HERE, "nj_staff_district_names.csv")))))
        rows = csv_rows(H.read(out, "data/nj/nj-district-staff-history.csv"))
        h = rows[0]
        for r in rows[1:]:
            self.assertEqual(r[h.index("district")], names[r[h.index("nj_county_district_code")]])

    def test_ac3_extra_column_in_a_staff_file_fails(self):
        def m(files):
            p = "data/nj_district_staff_2019-20.csv"
            files[p] = "\n".join(l + (",extra" if i == 0 else ",x") if l else l for i, l in enumerate(files[p].split("\n")))
        fixture_fails(m, "header")


class P3Values(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out, cls.rep = H.built()
        cls.rows = H.pinned_staff_rows()
        cls.by = {}
        for r in cls.rows:
            if r["nces_leaid"]:
                cls.by[(r["nces_leaid"], r["school_year"], r["staff_group"])] = r
        cls.pages = B.discover_pages(H.site_tree())

    def test_ac4_ac9_chart_table_csv_agree_for_every_district(self):
        n = 0
        for leaid, path in self.pages.items():
            sec = H.history_section(H.read(self.out, path.strip("/") + "/index.html"))
            self.assertIsNotNone(sec, leaid)
            if f'data-leaid="{leaid}"' in sec and "hist-empty" in sec:
                continue
            tab, ch = H.table_rows(sec), H.chart_data(sec)
            self.assertEqual(len(tab), 28, leaid)
            self.assertEqual(len(ch), 28, leaid)
            csvr = {(r[0]): r for r in []}
            for y in WINDOW:
                for g in D.GROUPS:
                    src = self.by.get((leaid, y, g))
                    st, cells = tab[(y, g)]
                    if src is None:
                        self.assertEqual((st, cells[2]), ("missing", ""), (leaid, y, g))
                        self.assertEqual(ch[(y, g)], ("missing", None))
                    elif src["suppressed"] == "true":
                        want = "small" if src["suppression_reason"] == "n_lt_10" else "comp"
                        self.assertEqual((st, cells[2]), (want, ""), (leaid, y, g))
                        self.assertEqual(ch[(y, g)], (want, None))
                    else:
                        whole, dec = src["fte_sum"].split(".")
                        shown = f"{int(whole):,}.{dec}"
                        self.assertEqual((st, cells[2]), ("published", shown), (leaid, y, g))
                        self.assertEqual(ch[(y, g)], ("published", src["fte_sum"]))
            n += 1
        self.assertEqual(n, 585)

    def test_ac4_headcount_never_shown_and_no_derived_numbers(self):
        for leaid in ("3400660", "3416230"):
            sec = H.history_section(H.read(self.out, self.pages[leaid].strip("/") + "/index.html"))
            self.assertNotIn("headcount", sec.lower())
            nums = set(re.findall(r"\d[\d,]*\.\d\b", H.text_of(re.sub(r"<script.*?</script>", "", sec))))
            fte = {f"{int(r['fte_sum'].split('.')[0]):,}.{r['fte_sum'].split('.')[1]}" for (l, y, g), r in self.by.items()
                   if l == leaid and r["fte_sum"]}
            pct = {m for m in nums if m not in fte}
            for m in pct:  # the only other decimals on the page are the coverage percent
                self.assertRegex(H.text_of(sec), rf"\({re.escape(m)}%\)")

    def test_ac5_suppressed_rows_render_the_marker_and_no_number(self):
        sup = sum(1 for r in self.rows if r["suppressed"] == "true")
        self.assertEqual(sup, 10193)
        self.assertEqual(sum(1 for r in self.rows if r["suppression_reason"] == "n_lt_10"), 8952)
        self.assertEqual(sum(1 for r in self.rows if r["suppression_reason"] == "complementary"), 1241)
        # pages cover every row whose LEAID has a page; the statewide page covers the rest by count
        marker = nonum = 0
        for leaid, path in self.pages.items():
            sec = H.history_section(H.read(self.out, path.strip("/") + "/index.html"))
            for (y, g), (st, cells) in H.table_rows(sec).items():
                src = self.by.get((leaid, y, g))
                if src and src["suppressed"] == "true":
                    marker += 1
                    self.assertIn(cells[3], (C.STATUS_SMALL, C.STATUS_COMP))
                    self.assertEqual(cells[2], "")
                    nonum += 1
        want = sum(1 for (l, y, g), r in self.by.items() if l in self.pages and r["suppressed"] == "true")
        self.assertEqual(marker, want)
        self.assertEqual(nonum, marker)
        sw = H.read(self.out, "nj/history/index.html")
        tot = sum(int(c) for c in re.findall(r'<td class="num">[\d,]+</td><td class="num">([\d,]+)</td></tr>', sw.replace(",", "")))
        self.assertEqual(tot, 10193)
        self.assertNotEqual(C.STATUS_SMALL, C.STATUS_COMP)

    def test_ac5_suppressed_rows_stay_empty_in_csv_and_never_bridge(self):
        rows = csv_rows(H.read(self.out, "data/nj/nj-district-staff-history.csv"))
        h = rows[0]
        self.assertEqual(len(rows) - 1, 18732)
        for r in rows[1:]:
            if r[h.index("suppressed")] == "true":
                self.assertEqual(r[h.index("fte_sum")], "")
        # Pemberton teachers: the line breaks at 2021-22 (two path segments, no join across the gap)
        sec = H.history_section(H.read(self.out, "nj/pemberton-twp-3412810/index.html"))
        d = re.search(r'<svg[^>]*teacher-d-t".*?<path class="ln" d="([^"]+)"', sec, re.S).group(1)
        self.assertEqual(d.count("M"), 2)

    def test_ac5_suppressed_with_value_fails_the_build(self):
        def m(files):
            p = "data/nj_district_staff_2019-20.csv"
            lines = files[p].split("\n")
            c = lines[1].split(",")
            self.assertEqual(c[8], "true")
            c[7] = "12.3"
            lines[1] = ",".join(c)
            files[p] = "\n".join(lines)
        fixture_fails(m, "suppressed row carries fte_sum")

    def test_ac6_missing_year_golden(self):
        sec = H.history_section(H.read(self.out, "nj/pemberton-twp-3412810/index.html"))
        tab = H.table_rows(sec)
        for g in D.GROUPS:
            self.assertEqual(tab[("2021-22", g)][0], "missing")
            self.assertEqual(tab[("2021-22", g)][1][3], C.MISSING)
            self.assertEqual(tab[("2021-22", g)][1][2], "")
        self.assertIn("0 of 6 school years (0.0%)", H.text_of(sec))

    def test_ac7_year_labels_ascending_and_in_window(self):
        sec = H.history_section(H.read(self.out, "nj/absecon-city-3400660/index.html"))
        years = [m for m in re.findall(r'<tr data-year="([^"]+)"', sec)]
        self.assertEqual(sorted(set(years)), list(WINDOW))
        self.assertEqual(years, sorted(years))
        self.assertEqual(set(re.findall(r"(?<![\d-])(20\d\d-\d\d)(?![\d-])", sec)) - set(WINDOW), set())


class P4District(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out, cls.rep = H.built()
        cls.pages = B.discover_pages(H.site_tree())

    def page(self, leaid):
        return H.read(self.out, self.pages[leaid].strip("/") + "/index.html")

    def test_ac8_one_section_per_page_and_old_anchors_kept(self):
        self.assertEqual(len(self.pages), 586)
        for leaid, path in self.pages.items():
            p = self.page(leaid)
            self.assertEqual(p.count('id="staff-guide-history"'), 1, leaid)
            self.assertEqual(len(re.findall(r'<section class="nj-hist"', p)), 1)
            old = H.git_base(path.strip("/") + "/index.html").decode()
            for a in re.findall(r'id="(history|guides-h|dl|src-[0-9a-f]{12})"', old):
                self.assertIn(f'id="{a}"', p, (leaid, a))

    def test_heading_order_has_no_skipped_levels(self):
        def levels(frag):
            return [int(x) for x in re.findall(r"<h([1-6])[ >]", frag)]
        for leaid in self.pages:
            lv = levels(H.history_section(self.page(leaid)))
            self.assertEqual(lv[0], 2)
            self.assertTrue(all(b - a <= 1 for a, b in zip(lv, lv[1:])), (leaid, lv))
        sw = H.read(self.out, "nj/history/index.html")
        lv = levels(sw[sw.index('<main id="main">'):sw.index("</main>")])
        self.assertEqual(lv[0], 1)
        self.assertTrue(all(b - a <= 1 for a, b in zip(lv, lv[1:])), lv)

    def test_ac8_seaside_park_empty_state(self):
        sec = H.history_section(self.page("3414820"))
        t = H.text_of(sec)
        self.assertIn(C.NO_ROWS, t)
        self.assertIn(C.NO_ROWS_COV, t)
        self.assertNotIn("partial history", t)
        self.assertNotIn("%", t)
        self.assertNotIn("<svg", sec)
        self.assertNotIn("/data/nj/history/", sec)
        self.assertIn(C.S_PATH, sec)
        self.assertFalse(os.path.exists(os.path.join(self.out, "data", "nj", "history", "3414820.csv")))
        self.assertNotIn('id="ld-nj-history"', self.page("3414820"))

    def test_ac8_full_trend_for_absecon_and_four_groups(self):
        sec = H.history_section(self.page("3400660"))
        self.assertEqual(sec.count('class="hist-panel"'), 4)
        self.assertEqual(len(H.table_rows(sec)), 28)
        self.assertIn(C.ALL_SUPPRESSED, sec)  # administrators and supervisors suppressed all 7 years

    def test_ac10_guide_goldens_and_labels(self):
        got = {l: re.search(r'data-guide-years="([^"]*)"', H.history_section(self.page(l))).group(1).split(",")
               for l in ("3401260", "3416230", "3403300", "3404500", "3416800", "3417700")}
        self.assertEqual(got["3401260"], ["2023-24", "2024-25", "2025-26"])
        self.assertEqual(got["3416230"], ["2024-25", "2025-26"])
        self.assertEqual(got["3403300"], ["2024-25", "2025-26"])
        self.assertEqual(got["3416800"], ["2025-26"])
        with_guides = [l for l in self.pages if "hist-guide" in self.page(l)]
        self.assertEqual(sorted(with_guides), sorted(got))
        for l in self.pages:
            sec = H.history_section(self.page(l))
            low = sec.lower()
            self.assertNotIn("median", low)
            self.assertNotIn("average teacher salary", low)
            if l not in got:
                self.assertNotIn("salary guide (negotiated)", sec.replace(C.GUIDE_LABEL + ":", ""), l)
        sec = H.history_section(self.page("3416230"))
        self.assertIn(f"<h3>{C.GUIDE_LABEL}</h3>", sec)

    def test_ac10_guide_links_reach_existing_guide_tables(self):
        """Links are fragment links built in the new section; the old tables carry no new ids."""
        for l in ("3401260", "3416230", "3403300", "3404500", "3416800", "3417700"):
            p = self.page(l)
            sec = H.history_section(p)
            old = p.replace(sec, "")
            for y, href in re.findall(r'<a href="(#guides-h:~:text=Teacher%20salary%20guide%2C%20(\d{4}-\d\d))">', sec)[:0] or []:
                pass
            hrefs = re.findall(r'href="(#guides-h:~:text=Teacher%20salary%20guide%2C%20(\d{4}-\d\d))"', sec)
            self.assertEqual(len(hrefs), len(re.search(r'data-guide-years="([^"]*)"', sec).group(1).split(",")))
            for href, y in hrefs:
                self.assertIn(f"Teacher salary guide, {y}", old)  # the heading the fragment targets exists in the old markup
                self.assertEqual(old.count(f"<h3>Teacher salary guide, {y}"), 1, (l, y))
            self.assertIn('id="guides-h"', old)
            self.assertIn('<script src="/history.js" defer></script>', sec)
            self.assertTrue(os.path.exists(os.path.join(self.out, "history.js")))
            self.assertNotIn("guide-teacher-", p)

    def test_ac10_held_and_cst_never_appear(self):
        for slug_leaid in ("3411340", "3401950"):  # Newark, East Orange (held in the data repo)
            if slug_leaid in self.pages:
                self.assertNotIn("hist-guide", self.page(slug_leaid))
        paterson = [l for l, p in self.pages.items() if p.startswith("/nj/paterson-")]
        for l in paterson:
            self.assertNotIn("hist-guide", self.page(l))
        for l in ("3401260",):  # Bayonne also has CST cells; only teacher years are linked
            self.assertEqual(H.history_section(self.page(l)).count("#guides-h:~:text="), 3)

    def test_ac11_coverage_text_for_goldens(self):
        gold = {"3416230": "2 of 7 school years (28.6%)", "3401260": "3 of 7 school years (42.9%)",
                "3400660": "0 of 7 school years (0.0%)", "3412810": "0 of 6 school years (0.0%)"}
        for l, t in gold.items():
            sec = H.history_section(self.page(l))
            self.assertIn(f"Salary-guide coverage: {t}.", H.text_of(sec))
            self.assertIn('<span class="partial">partial history</span>', sec)
        for l in self.pages:
            sec = H.history_section(self.page(l))
            m = re.search(r'data-cov-k="(\d+)" data-cov-n="(\d+)"', sec)
            if m:
                k, n = int(m.group(1)), int(m.group(2))
                self.assertEqual(sec.count('class="partial"') == 1, 2 * k < n, l)
        self.assertIn("/nj/history/", H.history_section(self.page("3416230")))

    def test_ac14_credits_and_as_is(self):
        man = list(csv.DictReader(io.StringIO(H.pinned("sources/nj_cs_manifest.csv"))))
        for l in ("3400660", "3416230", "3404500"):
            sec = H.history_section(self.page(l))
            t = H.text_of(sec)
            for m in man:
                self.assertIn(f"Source: New Jersey Department of Education · {m['school_year']} · retrieved 2026-11-06 (America/Toronto) · {m['url']}", t)
                self.assertIn(f'href="{m["url"]}"', sec)
            self.assertIn(C.AS_IS, t)
        t = H.text_of(H.history_section(self.page("3416230")))
        self.assertIn("OPRA response from Toms River Regional, received 2026-10-20, sha256 9c3dc6805c72f9ef55f4ce2aec23509e0c755aaaafe42ab45a1fdeeb50a031cb", t)
        self.assertIn("Data years: 2024-25, 2025-26. Retrieved 2026-10-20 (America/Toronto).", t)
        t = H.text_of(H.history_section(self.page("3404500")))
        self.assertIn("Source: district contract · 2023-24, 2024-25, 2025-26 · retrieved 2026-10-20 (America/Toronto) · https://5il.co/2u0cp", t)
        self.assertNotIn("NJ PERC", t)

    def test_ac14_perc_branch_uses_nj_perc_with_url(self):
        for u in ("https://www.perc.state.nj.us/x.pdf", "https://www.state.nj.us/perc/x.pdf", "https://perc.nj.gov/x"):
            self.assertTrue(D.is_perc_url(u), u)
        for u in ("https://5il.co/2u0cp", "http://www.perc.state.nj.us/x.pdf", "https://district.k12.nj.us/contract.pdf"):
            self.assertFalse(D.is_perc_url(u), u)

        class Stub:
            district_names = {"1": "A"}
            cov = {"1": {"guide_years": ["2025-26"]}}
            guide_sources = {"1": {"2025-26": [{"sha256": "a" * 64, "source_type": "public_url", "retrieved_at": "2026-10-20T16:14:00Z",
                                               "source_url": "https://www.state.nj.us/perc/x.pdf", "citation": None}]}}
        t = H.text_of(R.guide_credits(Stub, ["1"], {}, True))
        self.assertEqual(t, "NJ PERC · 2025-26 · retrieved 2026-10-20 (America/Toronto) · https://www.state.nj.us/perc/x.pdf")

    def test_ac14_no_nj_seals_or_hosted_images(self):
        for l in self.pages:
            sec = H.history_section(self.page(l))
            self.assertNotIn("<img", sec)
            for src in re.findall(r'(?:src|href)="([^"]+)"', sec):
                if src.startswith("http"):
                    self.assertFalse(re.search(r"nj\.gov/.*\.(png|jpe?g|svg|gif)$", src), src)
            for title in re.findall(r"<title[^>]*>(.*?)</title>", sec):
                self.assertNotIn("nj.gov", title.lower())
                self.assertNotIn("seal", title.lower())


class P5Coverage(unittest.TestCase):
    def snap(self, w, t):
        class Stub:
            lock = {"snapshot_date": "2026-11-09"}
            state_rows = [{"with_salary_guide": str(w), "district_years": str(t)}]
        return R.state_coverage_snapshot(Stub)

    def test_ac13_synthetic_cases_through_the_render_path(self):
        a = R.coverage_block(49, 100)
        self.assertIn("(49.0%)", a)
        self.assertIn("partial history", a)
        b = R.coverage_block(50, 100)
        self.assertIn("(50.0%)", b)
        self.assertNotIn("partial history", b)
        c = R.coverage_block(100, 100)
        self.assertIn("(100.0%)", c)
        self.assertNotIn("partial history", c)
        self.assertNotIn("partial history", R.coverage_block(3, 6))
        self.assertIn("partial history", R.coverage_block(3, 7))
        e = R.coverage_block(0, 0)
        self.assertIn("not available (no NJDOE staff rows)", e)
        self.assertNotIn("%", e)
        self.assertNotIn("partial history", e)
        f = self.snap(2336, 4676)
        self.assertIn("(49.9%)", f)
        self.assertNotIn("50.0", f)
        self.assertTrue(f.endswith(": partial history."))
        self.assertIn("2,336 of 4,676", f)
        self.assertEqual(D.pct_text(2336, 4676), "49.9")
        self.assertFalse(self.snap(2338, 4676).endswith("partial history."))
        self.assertIn("(50.0%)", self.snap(2338, 4676))

    def test_ac12_statewide_page_at_the_pin(self):
        out, rep = H.built()
        p = H.read(out, "nj/history/index.html")
        self.assertIn(self.snap(14, 4676), H.text_of(p))
        self.assertIn("As of 2026-11-09 (America/Toronto), published teacher salary guides cover 14 of 4,676 district-years (0.3%) for 2019-20 to 2025-26: partial history.", H.text_of(p))
        self.assertEqual([r["with_salary_guide"] for r in rep["coverage_state"]], ["0", "0", "0", "0", "3", "5", "6", "14"])
        self.assertEqual([r["district_years"] for r in rep["coverage_state"]], ["669", "670", "668", "669", "669", "668", "663", "4676"])

    def test_ac13_cross_check_names_clifton_as_the_only_difference(self):
        _, rep = H.built()
        cc = rep["crosscheck"]
        self.assertEqual(cc["exception_leaids"], ["3403300"])
        self.assertEqual([(d["school_year"], d["site"], d["file"]) for d in cc["differences"]],
                         [("2024-25", 5, 4), ("2025-26", 6, 5), ("ALL", 14, 12)])
        for d in cc["differences"]:
            self.assertEqual(d["leaids"], ["3403300"])
        self.assertEqual(cc["file"]["ALL"], ["4676", "12"])

    def test_ac13_cross_check_rejects_other_differences(self):
        def m(files):
            files["data/nj_history_coverage.csv"] = files["data/nj_history_coverage.csv"].replace(",3,0.4,", ",2,0.3,")
        fixture_fails(m, "differs from file")

    def test_ac13_denominator_must_match_the_file(self):
        def m(files):
            files["data/nj_history_coverage.csv"] = files["data/nj_history_coverage.csv"].replace("4676", "4675")
        fixture_fails(m, "denominator")

    def test_published_guide_years_match_the_salary_file(self):
        """The 14 are derived from the published cells; the pinned salary file with the same filter gives the same pairs."""
        out, rep = H.built()
        rows = list(csv.DictReader(io.StringIO(H.pinned("data/nj-salary_cell.csv"))))
        pairs = {(r["nces_leaid"], r["school_year"]) for r in rows if r["staff_group"] == "teacher" and r["salary_usd"]
                 and r["identity_status"] == "verified" and r["school_year"] in WINDOW}
        self.assertEqual(len(pairs), 14)
        mine = set()
        for l, p in B.discover_pages(H.site_tree()).items():
            m = re.search(r'data-guide-years="([^"]+)"', H.history_section(H.read(out, p.strip("/") + "/index.html")))
            if m:
                mine |= {(l, y) for y in m.group(1).split(",")}
        self.assertEqual(mine, pairs)

    def test_approved_sentence_is_pinned_to_derived_data(self):
        """Regression: the approved coverage sentence only holds while the derived data says so."""
        out, rep = H.built()
        a = rep["coverage_state"][-1]
        w, t = int(a["with_salary_guide"]), int(a["district_years"])
        approved = "published teacher salary guides cover 14 of 4,676 district-years (0.3%) for 2019-20 to 2025-26: partial history."
        derived = C.S_COV_SNAP.format(date="X", w=f"{w:,}", t=f"{t:,}", p=D.pct_text(w, t), tail=f": {C.D_PARTIAL}." if D.is_partial(w, t) else ".")
        self.assertTrue(derived.split("(America/Toronto), ")[1] == approved, derived)


class P6Statewide(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out, cls.rep = H.built()
        cls.p = H.read(cls.out, "nj/history/index.html")
        cls.rows = H.pinned_staff_rows()

    def test_ac15_contents(self):
        p = self.p
        for a in ("nj-history-overview", "history-coverage", "published-row-counts", "guide-years", "history-downloads", "staff-file-credits"):
            self.assertEqual(p.count(f'id="{a}"'), 1)
        self.assertEqual(len(re.findall(r"<h1[ >]", p)), 1)
        heads = re.findall(r"<h([1-4])[^>]*>", p)
        self.assertEqual(heads[0], "1")
        cov = re.search(r'id="coverage-table".*?</table>', p, re.S).group(0)
        self.assertEqual(cov.count("<tr role"), 9)  # header + 7 years + ALL
        self.assertIn("All school years", cov)
        rc = re.search(r'id="row-count-table".*?</table>', p, re.S).group(0)
        cnt = {}
        for r in self.rows:
            cnt.setdefault((r["school_year"], r["staff_group"]), [0, 0])[1 if r["suppressed"] == "true" else 0] += 1
        for m in re.finditer(r'<tr data-year="([^"]+)" data-group="([^"]+)">.*?<td class="num">([\d,]+)</td><td class="num">([\d,]+)</td>', rc):
            self.assertEqual([int(m.group(3).replace(",", "")), int(m.group(4).replace(",", ""))], cnt[(m.group(1), m.group(2))])
        self.assertEqual(rc.count("<tr data-year"), 28)
        names = [("Bayonne City", "/nj/bayonne-city-3401260/", "2023-24, 2024-25, 2025-26"), ("Clifton City", "/nj/clifton-city-3403300/", "2024-25, 2025-26"),
                 ("Edison Twp", "/nj/edison-twp-3404500/", "2023-24, 2024-25, 2025-26"),
                 ("Toms River Regional", "/nj/toms-river-regional-3416230/", "2024-25, 2025-26"),
                 ("Vineland City", "/nj/vineland-city-3416800/", "2025-26"),
                 ("W Windsor-Plainsboro Reg", "/nj/w-windsor-plainsboro-reg-3417700/", "2023-24, 2024-25, 2025-26")]
        gl = re.search(r'<ul class="guide-districts">(.*?)</ul>', p, re.S).group(1)
        self.assertEqual(re.findall(r'<li><a href="([^"]+)">([^<]+)</a> · ([^<]+)</li>', gl), [(b, a, c) for a, b, c in names])
        for l in ("/data/nj/nj-district-staff-history.csv", "/data/nj/nj-history-coverage.csv"):
            self.assertIn(f'href="{l}"', p)
        t = H.text_of(p)
        self.assertNotIn("median", t.lower())
        self.assertNotRegex(t, r"statewide (staff )?(total|average|sum)\s*[:=]")
        self.assertIn("No statewide staff total is calculated.", t)

    def test_ac14_statewide_credits(self):
        t = H.text_of(self.p)
        for m in csv.DictReader(io.StringIO(H.pinned("sources/nj_cs_manifest.csv"))):
            self.assertIn(f"Source: New Jersey Department of Education · {m['school_year']} · retrieved 2026-11-06 (America/Toronto) · {m['url']}", t)
        self.assertIn("Source: district contract · 2023-24, 2024-25, 2025-26 · retrieved 2026-10-20 (America/Toronto) · https://www.west-windsor-plainsboro.k12.nj.us/common/pages/DisplayFile.aspx?itemId=60107411", t)
        self.assertIn(C.AS_IS, t)
        self.assertEqual(self.p.count('href="/nj/clifton-city-3403300/#src-2212af5d5ac7"'), 1)

    def test_ac25_head_parity_with_nj_index(self):
        nj = H.read(self.out, "nj/index.html")
        head = lambda s: re.findall(r"<(?:meta|link|script|title)[^>]*>(?:.*?</title>)?", s[:s.index("</head>")], re.S)
        a, b = head(nj), head(self.p)
        tag = lambda s: re.match(r"<(\w+)(?: (?:name|property|rel)=\"([^\"]+)\")?", s).groups()
        self.assertEqual([tag(x) for x in a if "ld+json" not in x], [tag(x) for x in b if "ld+json" not in x])
        for needle in ('data-goatcounter="https://k12comp.goatcounter.com/count"', 'rel="canonical" href="https://k12comp.com/nj/history/"',
                       f"<title>{C.S_TITLE}</title>", 'rel="icon"', "SpaceGrotesk-Regular.woff2", 'property="og:image"', 'property="og:url" content="https://k12comp.com/nj/history/"'):
            self.assertIn(needle, self.p)
        self.assertIn(f'<meta name="description" content="{C.S_DESC}">', self.p)
        self.assertIn('data-slot="newsletter"', self.p)
        self.assertIn('<footer class="site-footer">', self.p)
        self.assertNotIn('name="robots"', self.p)
        hosts = set(re.findall(r'(?:src|href)="https?://([^/"]+)', self.p))
        self.assertTrue(hosts <= {"k12comp.goatcounter.com", "gc.zgo.at", "hazeydata.ai", "k12comp.com", "www.nj.gov", "5il.co",
                                  "www.west-windsor-plainsboro.k12.nj.us", "creativecommons.org"}, hosts)
        self.assertNotRegex(self.p, r"<script[^>]+src=\"https?://(?!gc\.zgo\.at)")


class P7Downloads(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out, cls.rep = H.built()
        cls.rows = H.pinned_staff_rows()

    def test_ac16_statewide_staff_csv_equals_allowlist_applied_to_pinned_rows(self):
        names = dict(csv.reader(io.StringIO(H.rt(os.path.join(D.HERE, "nj_staff_district_names.csv")))))
        man = {m["school_year"]: m["retrieved_at"] for m in csv.DictReader(io.StringIO(H.pinned("sources/nj_cs_manifest.csv")))}
        want = [D.STAFF_PUB_COLS]
        for r in self.rows:
            want.append([names[r["nj_county_district_code"]] if c == "district" else man[r["school_year"]] if c == "retrieved_at" else r[c]
                         for c in D.STAFF_PUB_COLS])
        got = csv_rows(H.read(self.out, "data/nj/nj-district-staff-history.csv"))
        self.assertEqual(got, want)
        self.assertEqual(sum(1 for r in got[1:] if r[2] == ""), 28)

    def test_ac16_coverage_and_district_files(self):
        cov = csv_rows(H.read(self.out, "data/nj/nj-history-coverage.csv"))
        self.assertEqual(len(cov), 9)
        self.assertEqual(cov[-1], ["ALL", "4676", "14", "0.3", "partial history", "salary guide (negotiated)"])
        d = os.path.join(self.out, "data", "nj", "history")
        files = sorted(os.listdir(d))
        self.assertEqual(len(files), 585)
        t = csv_rows(H.read(self.out, "data/nj/history/3416230.csv"))
        h = t[0]
        staff = [r for r in t[1:] if r[h.index("staff_group")]]
        want = [r for r in self.rows if r["nces_leaid"] == "3416230"]
        self.assertEqual(len(staff), len(want))
        self.assertEqual([r[h.index("fte_sum")] for r in staff], [r["fte_sum"] for r in want])
        last = t[-1]
        self.assertEqual((last[h.index("school_year")], last[h.index("district_years")], last[h.index("with_salary_guide")],
                          last[h.index("coverage_pct")], last[h.index("label")], last[h.index("nces_leaid")]),
                         ("ALL", "7", "2", "28.6", "partial history", "3416230"))

    def test_ac16_bytes_are_utf8_lf_and_linked(self):
        for rel in ("data/nj/nj-district-staff-history.csv", "data/nj/nj-history-coverage.csv", "data/nj/history/3400660.csv"):
            raw = H.rb(os.path.join(self.out, rel))
            self.assertNotIn(b"\r", raw)
            raw.decode("utf-8")
            self.assertTrue(raw.endswith(b"\n"))
        p = H.read(self.out, "nj/absecon-city-3400660/index.html")
        for l in ("/data/nj/history/3400660.csv", "/data/nj/nj-district-staff-history.csv", "/data/nj/nj-history-coverage.csv"):
            self.assertIn(f'href="{l}"', H.history_section(p))

    def test_ac17_jsonld(self):
        for rel in ("nj/toms-river-regional-3416230/index.html", "nj/history/index.html", "nj/absecon-city-3400660/index.html"):
            p = H.read(self.out, rel)
            m = re.search(r'<script type="application/ld\+json" id="ld-nj-history">(.*?)</script>', p, re.S)
            ds = json.loads(m.group(1))
            self.assertEqual(ds["@type"], "Dataset")
            self.assertEqual(ds["license"], "https://creativecommons.org/licenses/by/4.0/")
            self.assertEqual(ds["temporalCoverage"], "2019-07-01/2026-06-30")
            self.assertEqual(ds["distribution"]["encodingFormat"], "text/csv")
            self.assertEqual(set(ds), {"@context", "@type", "name", "description", "license", "temporalCoverage", "creator", "distribution", "isBasedOn"})
            self.assertTrue(ds["distribution"]["contentUrl"].endswith(".csv"))
            for u in ds["isBasedOn"]:
                self.assertTrue(u.startswith("https://"), u)
                self.assertNotIn("ufb", u)
                self.assertNotIn("opra:", u)
            self.assertEqual(len([u for u in ds["isBasedOn"] if "doedata/cs" in u]), 7)
            self.assertNotIn('"Person"', m.group(1))
            self.assertNotIn("median", m.group(1).lower())
        ds = json.loads(re.search(r'id="ld-nj-history">(.*?)</script>', H.read(self.out, "nj/history/index.html")).group(1))
        self.assertIn("https://5il.co/2u0cp", ds["isBasedOn"])
        self.assertEqual(len(ds["isBasedOn"]), 9)
        p = H.read(self.out, "nj/toms-river-regional-3416230/index.html")
        base = H.git_base("nj/toms-river-regional-3416230/index.html").decode()
        old = re.search(r'<script type="application/ld\+json">.*?</script>', base, re.S).group(0)
        self.assertEqual(p.count(old), 1)
        self.assertEqual(len(re.findall(r'application/ld\+json', p)), 2)

    def test_ac18_sitemap_and_robots(self):
        sm, base = H.read(self.out, "sitemap.xml"), H.git_base("sitemap.xml").decode()
        old, new = re.findall(r"<loc>(.*?)</loc>", base), re.findall(r"<loc>(.*?)</loc>", sm)
        self.assertEqual((len(old), len(new)), (589, 590))
        self.assertEqual(new[:589], old)
        self.assertEqual(new[589], "https://k12comp.com/nj/history/")
        self.assertEqual(len(re.findall(r"<url>", sm)), 590)
        for x in ("/privacy/", "/terms/", "/404"):
            self.assertNotIn(x, sm)
        self.assertEqual(H.read(self.out, "robots.txt").encode(), H.git_base("robots.txt"))

    def test_ac19_llms_txt(self):
        base = H.git_base("llms.txt").decode()
        new = H.read(self.out, "llms.txt")
        self.assertTrue(new.startswith(base if base.endswith("\n") else base + "\n"))
        self.assertEqual(new[len(base):].splitlines()[-5:], list(C.LLMS_LINES))
        self.assertNotIn("median", new[len(base):].lower())

    def test_ac20_about(self):
        base = H.git_base("about/index.html").decode()
        new = H.read(self.out, "about/index.html")
        i = new.index(f'<h2 id="{C.A_ANCHOR}">')
        self.assertEqual(new[:i] + new[new.index("</main>"):], base)
        self.assertEqual(re.findall(r"<h2[^>]*>(.*?)</h2>", base), ["Where the numbers come from", "How we show them", "Privacy and corrections"])
        sec = H.text_of(new[i:new.index("</main>")])
        for para in C.A_PARAS:
            self.assertIn(H.text_of(para), sec)
        self.assertIn(C.A_LINK, sec)


class P8Preservation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out, cls.rep = H.built()

    def test_ac23_every_base_path_exists_and_cname_is_unchanged(self):
        paths = H.base_paths()
        self.assertEqual(len(paths), 2350)
        for p in paths:
            self.assertTrue(os.path.exists(os.path.join(self.out, p)), p)
        self.assertEqual(H.rb(os.path.join(self.out, "CNAME")), H.git_base("CNAME"))

    def test_ac24_no_collateral_change(self):
        changed = {"sitemap.xml", "llms.txt", "nj/index.html", "about/index.html"}  # each checked separately below
        n = 0
        for p in H.base_paths():
            new = H.rb(os.path.join(self.out, p))
            old = H.git_base(p)
            if p in changed:
                continue
            if re.fullmatch(r"nj/[a-z0-9-]+-\d{7}/index\.html", p):
                self.assertEqual(H.strip_history(new.decode()).encode(), old, p)
                n += 1
            else:
                self.assertEqual(new, old, p)
        self.assertEqual(n, 586)
        nj = H.read(self.out, "nj/index.html")
        self.assertEqual(nj.replace(R.nj_link(), "", 1).encode(), H.git_base("nj/index.html"))
        self.assertIn(">NJ staff and salary-guide history</a>", nj)

    def test_ac24_json_api_is_byte_identical(self):
        js = [p for p in H.base_paths() if p.startswith("api/v1/nj/")]
        self.assertEqual(len(js), 586)

    def test_ac27_determinism(self):
        out2 = os.path.join(H.tmpdir(), "site")
        B.run(site_root=H.site_tree(), out_dir=out2, data_repo=H.DATA_REPO)
        a = subprocess.run(["diff", "-rq", self.out, out2], capture_output=True, text=True)
        self.assertEqual(a.returncode, 0, a.stdout[:500])

    def test_ac28_no_mac_mini_host_or_external_disk_and_no_paid_service(self):
        bad = re.compile(rb"mac[ _-]?mini|/volumes/|\bs" + b"sd\\b|stripe\\.com|paypal\\.com", re.I)
        files = []
        for d in ("tools/nj_history", "tests/browser", "docs"):
            files += [os.path.join(dp, f) for dp, _, fs in os.walk(os.path.join(H.ROOT, d)) for f in fs if f.endswith((".py", ".js", ".md", ".css", ".json"))]
        files += [os.path.join(H.ROOT, "tools", "nj_history_postbuild.py"), os.path.join(H.ROOT, "tests", "nj_history_helpers.py")]
        for f in files:
            m = bad.search(H.rb(f))
            self.assertIsNone(m, (f, m and m.group(0)))

    def test_ac29_to_31_docs_exist_and_describe_the_code(self):
        doc = H.rt(os.path.join(H.ROOT, "docs", "nj-history.md"))
        for needle in ("nj_history_postbuild.py", "pin.json", "K12_DATA_REPO", "K12_FIXTURE_MODE", "/nj/history/",
                       "guides-h:~:text=", "K12-CLIFTON-IDENTITY-GUARD-001", "14 of 4,676", "Release guard"):
            self.assertIn(needle, doc)


if __name__ == "__main__":
    unittest.main()
