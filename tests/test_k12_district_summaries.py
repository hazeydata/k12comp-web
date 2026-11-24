"""K12-DISTRICT-SUMMARIES-001: tools/nj_district_summaries.py (spec ACs 1-11, 13, 14, 20, as amended by the owner's Nov 24, 2026 rulings: 2 to 5
sentences, SH shared-service slot, S3 without the shared-service add-on).

The checks use their own parsers and their own recompute from api/v1/nj/<leaid>.json, data/nj/history/<leaid>.csv and the page (not the tool's
functions); the tool is only run (scratch copies, --trace). Base comparisons use web main bd37e392 through `git show`. No network, no data repo.
"""
import ast
import collections
import contextlib
import csv
import hashlib
import html
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nj_district_summaries as S  # noqa: E402
import k12_district_summaries_helpers as Y  # noqa: E402
import k12_indexing_helpers as X  # noqa: E402

BASE = "bd37e392b94cd7f692e6a61886053cd9d4ed119d"  # web main before this ticket
TOOL = os.path.join(ROOT, "tools", "nj_district_summaries.py")
COPY = os.path.join(ROOT, "tools", "nj_district_summaries_copy.json")
FIX = os.path.join(ROOT, "tests", "fixtures", "k12_district_summaries")
GOLDEN = "3416800 3400004 3400006 3400069 3401020 3401200 3401260 3401470 3403840 3406150 3408370 3414820 3400990 3401590".split()
SH_SENTENCE = "The superintendent contract on file is reported as a shared-service arrangement."
DISTRICT = re.compile(r"nj/([a-z0-9-]+-(\d{7}))/index\.html")
PARA = re.compile(r'<p class="district-summary" id="district-summary">(.*?)</p>', re.S)
TOKEN = re.compile(r"\d{4}-\d\d-\d\d|\d{4}-\d\d|\$?\d{1,3}(?:,\d{3})+(?:\.\d+)?|\$?\d+(?:\.\d+)?")


def slurp(path):
    with open(path, encoding="utf-8", newline="") as f:
        return f.read()


def jload(path):
    return json.loads(slurp(path))


def rd(root, rel):
    with open(os.path.join(root, *rel.split("/")), encoding="utf-8", newline="") as f:
        return f.read()


def pages(root=ROOT):
    return {m.group(2): f"nj/{m.group(1)}/index.html"
            for n in sorted(os.listdir(os.path.join(root, "nj"))) if (m := DISTRICT.fullmatch(f"nj/{n}/index.html"))}


def doc_of(root, leaid):
    return json.loads(rd(root, f"api/v1/nj/{leaid}.json"))


def money(v):
    return "$" + format(int(v), ",")


def history(root, leaid):
    p = os.path.join(root, "data", "nj", "history", leaid + ".csv")
    if not os.path.isfile(p):
        return []
    with open(p, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def sha_tree(root):
    out = {}
    for dp, _, fns in os.walk(root):
        for f in fns:
            p = os.path.join(dp, f)
            with open(p, "rb") as fh:
                out[os.path.relpath(p, root)] = hashlib.sha256(fh.read()).hexdigest()
    return out


def run_tool(*argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        rc = S.main(list(argv))
    return rc, out.getvalue()


def copy_site(dest):
    """What the tool reads and writes: /nj/ pages, the per-district JSON and history CSV."""
    for rel in ("nj", "api/v1/nj", "data/nj/history"):
        shutil.copytree(os.path.join(ROOT, *rel.split("/")), os.path.join(dest, *rel.split("/")))


class Page:
    """Our own reading of a district page."""

    def __init__(self, text):
        self.text = text
        m = re.search(r"<main.*?</main>", text, re.S)
        self.main = m.group(0)
        self.h1 = html.unescape(re.search(r"<h1>(.*?)</h1>", self.main).group(1))
        c = re.search(r'<nav aria-label="Breadcrumb" class="crumbs"><a href="/nj/">New Jersey</a> / <a href="/nj/county/[a-z0-9-]+/">([^<]*)</a> / ', self.main)
        self.county = html.unescape(c.group(1)) if c else None
        self.paras = PARA.findall(self.main)
        self.summary = html.unescape(self.paras[0]) if self.paras else None
        self.big = re.search(r'<p class="big num">([^<]*)</p>', self.main).group(1)
        self.label = re.search(r'<h2 id="latest" class="label">Latest base salary · ([^<]*)</h2>', self.main).group(1)
        st = re.search(r'Starts at <span class="num">([^<]*)</span> in (\d{4}-\d\d)', self.main)
        self.starts = st.groups() if st else None
        # the FTE section's staff table: {(year, group): shown value}
        self.fte = {(a, b): v for a, b, v in re.findall(r'<tr data-year="([\d-]+)" data-group="(\w+)" data-status="published"><th scope="row">[\d-]+</th>'
                                                         r'<td>[^<]*</td><td class="num">([^<]*)</td>', self.main)}


def recompute(root, leaid, page, copy):
    """The summary text, from the data files, the page and the copy file only (written independently of the tool)."""
    doc, hist = doc_of(root, leaid), history(root, leaid)
    assert page.h1 == doc["district"], leaid
    rows = doc["superintendent_contracts"]
    sal = [r for r in rows if not r["salary_not_reported"]]
    out = []
    if sal:
        ys = sorted({r["salary_year"] for r in sal})
        latest = [r for r in sal if r["salary_year"] == ys[-1]]
        shown = [r for r in latest if money(r["base_salary"]) == page.big]
        r1 = (shown or latest)[0]
        out.append(copy["S1"].format(district=doc["district"], county=page.county, base_salary=money(r1["base_salary"]), salary_year=r1["salary_year"]))
        if len(ys) >= 2:
            first = [r for r in sal if r["salary_year"] == ys[0]]
            assert page.starts and page.starts[1] == ys[0]
            r2 = [r for r in first if money(r["base_salary"]) == page.starts[0]][0]
            out.append(copy["S2"].format(base_salary=money(r2["base_salary"]), salary_year=r2["salary_year"]))
        if (not r1["term_ends_before_year"] and r1["ufb_work_days"] not in ("", "0")):
            out.append(copy["S3"].format(contract_start=r1["contract_start"], contract_end=r1["contract_end"], ufb_work_days=r1["ufb_work_days"]))
        if any(r["ufb_shared"] == "Y" for r in latest):
            out.append(copy["SH"])
    else:
        out.append(copy["S0"].format(district=doc["district"], county=page.county))
    s4 = False
    if hist:
        ly = max(r["school_year"] for r in hist if r["school_year"] not in ("", "ALL"))
        t = [r for r in hist if r["school_year"] == ly and r["staff_group"] == "teacher"]
        if t and t[0]["suppressed"] != "true" and t[0]["fte_sum"] and float(t[0]["fte_sum"]) > 0:
            shown = page.fte[(ly, "teacher")]  # as the FTE section prints it
            out.append(copy["S4"].format(fte_sum=shown, school_year=ly))
            s4 = True
    if not sal and not s4:
        out.append(copy["S0b"])
    if doc["salary_cells"]:
        ng = len({c["school_year"] for c in doc["salary_cells"]})
        out.append(copy["S5_one"] if ng == 1 else copy["S5"].format(n_guide_years=ng))
    return " ".join(out)


def slot_text(copy, slot):
    return copy[slot]


class ToolSource(unittest.TestCase):
    """AC 1 and AC 9."""

    def test_imports_are_stdlib_only_and_offline(self):
        tree = ast.parse(slurp(TOOL))
        mods = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                mods |= {a.name.split(".")[0] for a in n.names}
            elif isinstance(n, ast.ImportFrom):
                mods.add((n.module or "").split(".")[0])
        self.assertEqual(mods, {"argparse", "csv", "html", "json", "os", "re", "sys"})
        for bad in ("urllib", "http", "socket", "subprocess", "ssl", "requests", "ftplib", "smtplib"):
            self.assertNotIn(bad, mods)
        src = slurp(TOOL)
        self.assertNotRegex(src, r"\b(urlopen|socket\.|subprocess|os\.system|os\.popen|__import__|eval\(|exec\()")

    def test_no_english_sentence_literal_in_the_tool(self):
        tree = ast.parse(slurp(TOOL))
        doc = set()
        for n in ast.walk(tree):
            try:
                has_doc = ast.get_docstring(n, clean=False) is not None  # module, function and class docstrings
            except TypeError:
                continue
            if has_doc:
                doc.add(id(n.body[0].value))
        bad = []
        for n in ast.walk(tree):
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in doc and not re.search(r"[<>\\|()\[\]{}]", n.value):
                words = re.findall(r"(?<![\w<\"=/$.-])[A-Za-z][a-z']*[.,;:]?(?![\w=\"/>-])", n.value)
                if len(words) >= 3 or re.search(r"[A-Za-z]{3,} [A-Za-z]{2,}.*\.$", n.value):
                    bad.append(n.value)
        self.assertEqual(bad, [])
        # and the copy file's sentences do not occur in the tool
        src = slurp(TOOL)
        copy = jload(COPY)
        for k in S.SLOTS:
            self.assertNotIn(copy[k], src)
            self.assertNotIn(copy[k][:25], src)

    def test_copy_file_has_one_key_per_slot_with_status_and_limit(self):
        copy = jload(COPY)
        self.assertEqual(set(copy) - {"_note", "_status", "max_words"}, set("S0 S0b S1 S2 S3 SH S4 S5 S5_one".split()))
        self.assertEqual(copy["max_words"], 80)
        self.assertEqual(set(copy["_status"]), set(S.SLOTS))
        for k, v in copy["_status"].items():
            self.assertEqual(v, "APPROVED writing · Lindsay Bluth, Nov 24, 2026, 12:04 PM ET round 2", k)
        self.assertEqual(copy["SH"], SH_SENTENCE)
        self.assertNotIn("shared-service arrangement", copy["S3"])  # the spec's S3 add-on is dropped
        self.assertIsNone(re.search(r"\d", copy["SH"] + copy["S0"] + copy["S0b"] + copy["S5_one"]))
        self.assertIn("{fte_sum}", copy["S4"])
        for k in ("S1", "S2", "S3", "S4", "S5", "S0"):
            self.assertRegex(copy[k], r"\{[a-z_]+\}")

    def test_swapping_a_slot_is_a_one_line_copy_edit(self):
        with tempfile.TemporaryDirectory(prefix="k12ds-copy-") as d:
            copy = jload(COPY)
            copy["S2"] = "First on file: {base_salary} ({salary_year})."
            p = os.path.join(d, "copy.json")
            with open(p, "w", encoding="utf-8") as f:
                json.dump(copy, f)
            page = rd(ROOT, "nj/vineland-city-3416800/index.html")
            with mock.patch.object(S, "COPY", p):
                new, text, _ = S.rewrite(page, doc_of(ROOT, "3416800"), S.history_rows(ROOT, "3416800"), None, "3416800")
            self.assertIn("First on file: $181,938 (2019-20).", text)
            self.assertNotIn("earliest salary on record", text)
            self.assertEqual(Y.strip(new), Y.strip(page))


@unittest.skipUnless(os.path.isdir(os.path.join(ROOT, "nj")), "site tree")
class Committed(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.copy = jload(COPY)
        cls.pages = pages()
        cls.parsed = {L: Page(rd(ROOT, rel)) for L, rel in cls.pages.items()}
        cls.td = tempfile.TemporaryDirectory(prefix="k12ds-trace-")
        cls.trace_path = os.path.join(cls.td.name, "trace.json")
        rc, out = run_tool("--check", "--trace", cls.trace_path)
        assert rc == 0, out
        cls.trace = jload(cls.trace_path)

    @classmethod
    def tearDownClass(cls):
        cls.td.cleanup()

    # AC 3
    def test_586_pages_one_paragraph_after_the_disclaimer(self):
        self.assertEqual(len(self.pages), 586)
        for L, rel in self.pages.items():
            t = rd(ROOT, rel)
            self.assertEqual(t.count('class="district-summary"'), 1, rel)
            self.assertEqual(t.count('id="district-summary"'), 1, rel)
            self.assertEqual(len(self.parsed[L].paras), 1, rel)
            self.assertRegex(t, r'<main id="main">.*?<p class="disclaimer">[^<]*</p><p class="district-summary" id="district-summary">[^<]*</p>'
                                r'<section class="summary" aria-labelledby="latest">')
            # inside <main>, once, and nothing else with the class
            self.assertEqual(self.parsed[L].main.count('class="district-summary"'), 1)

    def test_no_other_page_has_one(self):
        n = 0
        for dp, dns, fns in os.walk(ROOT):
            dns[:] = [d for d in dns if d not in (".git", "node_modules", "tests", "tools", "docs")]
            for f in fns:
                if f.endswith(".html"):
                    rel = os.path.relpath(os.path.join(dp, f), ROOT).replace(os.sep, "/")
                    if not DISTRICT.fullmatch(rel):
                        n += 1
                        self.assertNotIn("district-summary", rd(ROOT, rel), rel)
        self.assertGreater(n, 20)  # hubs, /, /nj/, about, ... were scanned

    # AC 4
    def test_two_to_five_sentences_and_word_limit(self):
        dist = collections.Counter()
        words = 0
        for L, p in self.parsed.items():
            t = p.summary
            # sentences: take the district and county names out first (they may hold periods), then split at ". " + capital
            u = t.replace(p.h1, "X").replace(p.county, "Y")
            sentences = re.split(r"(?<=\.)\s+(?=[A-Z])", u)
            self.assertTrue(all(s.endswith(".") for s in sentences), L)
            self.assertTrue(2 <= len(sentences) <= 5, (L, len(sentences)))
            self.assertLessEqual(len(t.split()), self.copy["max_words"], L)
            dist[len(sentences)] += 1
            words = max(words, len(t.split()))
        self.assertEqual(sum(dist.values()), 586)
        self.assertGreater(dist[5], 0)  # the 5-sentence cap is reached, and the rulings' bound holds
        self.assertLessEqual(words, 80)

    # AC 5
    def test_recompute_all_586_with_zero_mismatches(self):
        bad = []
        for L, p in self.parsed.items():
            if recompute(ROOT, L, p, self.copy) != p.summary:
                bad.append(L)
        self.assertEqual(bad, [])
        # the tool's own text (via --trace) agrees too
        self.assertEqual({L: v["summary"] for L, v in self.trace.items()}, {L: p.summary for L, p in self.parsed.items()})

    def test_every_digit_token_is_traced_to_a_source_and_renders_exactly(self):
        formulas = 0
        for L, p in self.parsed.items():
            toks = self.trace[L]["tokens"]
            found = TOKEN.findall(p.summary)
            self.assertEqual(sorted(t["token"] for t in toks), sorted(found), L)
            # every digit of the summary is inside a token
            self.assertEqual("".join(re.findall(r"\d", p.summary)), "".join(re.findall(r"\d", " ".join(found))), L)
            doc = doc_of(ROOT, L)
            for t in toks:
                self.assertIn(t["token"], TOKEN.findall(t["rendered"]))
                if t["path"].startswith("FORMULA"):
                    formulas += 1
                    self.assertEqual(t["slot"], "S5")
                    self.assertEqual(t["path"], "FORMULA count(distinct salary_cells[*].school_year)")
                    self.assertEqual(t["source"], f"api/v1/nj/{L}.json")
                    self.assertEqual(t["rendered"], str(len({c["school_year"] for c in doc["salary_cells"]})))
                elif t["source"].startswith("api/"):
                    m = re.fullmatch(r"superintendent_contracts\[(\d+)\]\.(\w+)", t["path"])
                    self.assertTrue(m, (L, t))
                    v = doc["superintendent_contracts"][int(m.group(1))][m.group(2)]
                    self.assertIn(t["rendered"], (v, money(v) if m.group(2) == "base_salary" else v), (L, t))
                else:
                    self.assertEqual(t["source"], f"data/nj/history/{L}.csv")
                    m = re.fullmatch(r"row (\d+) (fte_sum|school_year)", t["path"])
                    self.assertTrue(m, (L, t))
                    with open(os.path.join(ROOT, *t["source"].split("/")), encoding="utf-8", newline="") as f:
                        row = list(csv.reader(f))[int(m.group(1)) - 1]
                    with open(os.path.join(ROOT, *t["source"].split("/")), encoding="utf-8", newline="") as f:
                        head = next(csv.reader(f))
                    v = row[head.index(m.group(2))]
                    self.assertEqual(t["rendered"], S.fmt_fte(v) if m.group(2) == "fte_sum" else v)
                    self.assertEqual(row[head.index("staff_group")], "teacher")
        self.assertEqual(formulas, 7)  # S5's count is the only formula (3403000 uses S5_one, no digit)

    def test_multi_row_latest_districts_trace_names_the_row_the_page_shows(self):
        for L, row in (("3401470", "row 263"), ("3401860", "row 4667"), ("3407680", "row 2117"), ("3412690", "row 4946")):
            doc = doc_of(ROOT, L)
            t = [x for x in self.trace[L]["tokens"] if x["slot"] == "S1" and x["rendered"].startswith("$")][0]
            i = int(re.search(r"\[(\d+)\]", t["path"]).group(1))
            r = doc["superintendent_contracts"][i]
            self.assertEqual(r["page_ref"], row)
            self.assertEqual(money(r["base_salary"]), self.parsed[L].big)
            self.assertIn(self.parsed[L].big, self.parsed[L].summary)
        # 3412690 shows $238,703 although another latest row holds more
        self.assertIn("$238,703", self.parsed["3412690"].summary)

    # AC 6
    def test_s1_equals_the_latest_figure_and_label_on_the_page(self):
        n_s1 = n_match = 0
        shows_not_reported = []
        for L, p in self.parsed.items():
            if "The latest superintendent base salary reported for" not in p.summary:
                continue
            n_s1 += 1
            m = re.search(r" is (\$[\d,]+), for (\d{4}-\d\d)\.", p.summary)
            if p.big.startswith("$"):
                self.assertEqual((m.group(1), m.group(2)), (p.big, p.label), L)
                n_match += 1
            else:
                shows_not_reported.append(L)  # the page's block shows a newer "Not reported" row; S1 states the latest reported year (History lists it)
                doc = doc_of(ROOT, L)
                ys = [r["salary_year"] for r in doc["superintendent_contracts"] if not r["salary_not_reported"]]
                self.assertEqual(m.group(2), max(ys))
                self.assertIn(f'<span class="hy num">{m.group(2)}</span><span class="hs num">{m.group(1)}</span>', self.parsed[L].main)
        self.assertEqual(n_s1, 575)
        self.assertEqual(n_match + len(shows_not_reported), 575)
        self.assertIn("3403660", shows_not_reported)

    # AC 7
    def test_branch_counts_equal_a_fresh_recount(self):
        c = collections.Counter()
        zero_days = []
        sh_ended = []
        for L in self.pages:
            doc = doc_of(ROOT, L)
            sal = [r for r in doc["superintendent_contracts"] if not r["salary_not_reported"] and r["base_salary"] not in ("", None)]
            hist = history(ROOT, L)
            s4 = False
            if hist:
                ly = max(r["school_year"] for r in hist if r["school_year"] not in ("", "ALL"))
                t = [r for r in hist if r["school_year"] == ly and r["staff_group"] == "teacher"]
                s4 = bool(t and t[0]["suppressed"] != "true" and t[0]["fte_sum"])
            c["S4"] += s4
            c["S5"] += bool(doc["salary_cells"])
            if sal:
                ys = sorted({r["salary_year"] for r in sal})
                lat = [r for r in sal if r["salary_year"] == ys[-1]]
                c["S1"] += 1
                c["S2"] += len(ys) >= 2
                shown = [r for r in lat if money(r["base_salary"]) == self.parsed[L].big]
                disp = (shown or lat)[0]  # the row the "Latest base salary" block displays
                if not disp["term_ends_before_year"]:
                    c["S3 dates branch"] += 1
                    if disp["ufb_work_days"] not in ("", "0"):
                        c["S3"] += 1
                    else:
                        zero_days.append(L)
                c["SH"] += any(r["ufb_shared"] == "Y" for r in lat)
                if any(r["ufb_shared"] == "Y" for r in lat) and disp["term_ends_before_year"]:
                    sh_ended.append(L)
            else:
                c["S0"] += 1
                c["S0b"] += not s4
        self.assertEqual(c["S1"], 575)
        self.assertEqual(c["S2"], 573)
        self.assertEqual(c["S3 dates branch"], 337)
        # two pages are in the dates branch but report 0 work days; the slot is omitted there (never print 0): 337 - 2
        self.assertEqual(zero_days, ["3400069", "3407200"])
        self.assertEqual(c["S3"], 335)
        for L in ("3401470", "3401860"):  # displayed row not term-ended: S3 present (even with another ended/shared latest row)
            self.assertIn("contract on file runs", self.parsed[L].summary, L)
        self.assertEqual(len(sh_ended), 14)  # shared-service pages without S3 because the displayed row is term-ended
        for L in sh_ended:
            self.assertNotIn("contract on file runs", self.parsed[L].summary, L)
        self.assertEqual(c["SH"], 40)
        self.assertEqual(c["S4"], 577)
        self.assertEqual(c["S5"], 8)
        self.assertEqual(c["S0"], 11)
        self.assertEqual(c["S0b"], 2)
        # the pages carry exactly those slots
        got = collections.Counter()
        for p in self.parsed.values():
            t = p.summary
            for k, needle in (("S1", self.copy["S1"].split("{")[0]), ("S2", self.copy["S2"].split("{")[0]),
                              ("S3", self.copy["S3"].split("{")[0]), ("SH", self.copy["SH"]), ("S4", self.copy["S4"].split("{")[0]),
                              ("S5", self.copy["S5"].split("{")[0]), ("S5", self.copy["S5_one"]), ("S0", self.copy["S0"].split("{county}")[1]), ("S0b", self.copy["S0b"])):
                got[k] += needle in t
        self.assertEqual({k: got[k] for k in ("S1", "S2", "S3", "SH", "S4", "S5", "S0", "S0b")},
                         {"S1": 575, "S2": 573, "S3": 335, "SH": 40, "S4": 577, "S5": 8, "S0": 11, "S0b": 2})
        # S0b only where S4 is absent, S0 pages: S4 follows S0
        for L, p in self.parsed.items():
            if self.copy["S0b"] in p.summary:
                self.assertNotIn("NJDOE staff records count", p.summary, L)
                self.assertIn(L, ("3414820", "3410170"))

    def test_single_guide_year_page_uses_the_s5_one_sentence(self):
        self.assertEqual(len({c["school_year"] for c in doc_of(ROOT, "3403000")["salary_cells"]}), 1)
        t = self.parsed["3403000"].summary
        self.assertTrue(t.endswith(" " + self.copy["S5_one"]), t)
        self.assertEqual(t.count(self.copy["S5_one"]), 1)
        self.assertNotIn("school years", t)
        self.assertEqual([x for x in self.trace["3403000"]["tokens"] if x["slot"].startswith("S5")], [])
        for L, p in self.parsed.items():
            self.assertNotIn("1 school years", p.summary, L)

    def test_slot_order_on_every_page(self):
        order = ["S0", "S1", "S2", "S3", "SH", "S4", "S0b", "S5"]
        needles = {"S1": "base salary reported for", "S2": "earliest salary on record", "S3": "contract on file runs",
                   "SH": SH_SENTENCE, "S4": "NJDOE staff records count", "S5": "teacher salary guide", "S0": "No superintendent base salary is reported", "S0b": self.copy["S0b"]}
        for L, p in self.parsed.items():
            pos = [(p.summary.find(needles[k]), k) for k in order if needles[k] in p.summary]
            self.assertEqual([k for _, k in pos], [k for _, k in sorted(pos)], L)
            self.assertEqual(pos[0][1], "S0" if "S0" in dict((k, 1) for _, k in pos) else "S1", L)

    def test_missing_values_omit_the_slot_never_zero_na_or_suppressed(self):
        for L, p in self.parsed.items():
            t = p.summary
            self.assertNotRegex(t, r"(?i)\bn/a\b|\bnone\b|\bnull\b|\bnan\b|suppress|\$0\b|\b0 work days|\b0\.0\b|\$\s|  ")
            self.assertFalse(re.search(r"\{|\}", t), L)
            self.assertNotRegex(t, r"(?<![\d.,-])0(?![\d.,-])")

    # AC 8
    def test_no_person_names_no_ufb_no_suppressed_values(self):
        from test_nj_history_privacy import FORBIDDEN  # the existing no-names / no-UFB guard
        guard = re.compile(FORBIDDEN.pattern.replace("|superintendent", ""), re.I)  # the role word is the page's subject, as on /nj/ and the hubs
        self.assertNotEqual(guard.pattern, FORBIDDEN.pattern)
        for L, p in self.parsed.items():
            self.assertIsNone(guard.search(p.summary), (L, guard.search(p.summary)))
            for r in doc_of(ROOT, L)["superintendent_contracts"]:
                for k in r:
                    if "name" in k:
                        self.fail(f"{L}: a name field {k} in the data would need review")
        # every word of a summary is a number, part of the district or county name, or a word of the copy file
        known = set(re.findall(r"[A-Za-z][A-Za-z'-]*", " ".join(v for k, v in self.copy.items() if k in S.SLOTS)))
        for L, p in self.parsed.items():
            names = set(re.findall(r"[A-Za-z'&.-]+", p.h1 + " " + (p.county or "")))
            for w in re.findall(r"[A-Za-z][A-Za-z'&.-]*", TOKEN.sub(" ", p.summary)):
                self.assertTrue(w in known or w in names or w.strip(".") in known or w.strip(".") in names, (L, w))

    def test_planted_name_canary_never_reaches_a_summary(self):
        plant = "Jane Plantedname"
        with tempfile.TemporaryDirectory(prefix="k12ds-canary-") as d:
            copy_site(d)
            L = "3416800"
            doc = doc_of(d, L)
            for r in doc["superintendent_contracts"]:
                r["superintendent_name"] = plant
                r["person_name"] = plant
            doc["contact"] = plant
            with open(os.path.join(d, "api", "v1", "nj", L + ".json"), "w", encoding="utf-8") as f:
                json.dump(doc, f, sort_keys=True)
            p = os.path.join(d, "data", "nj", "history", L + ".csv")
            with open(p, encoding="utf-8", newline="") as f:
                text = f.read().replace("Vineland Public School District", plant)
            with open(p, "w", encoding="utf-8", newline="") as f:
                f.write(text)
            self.assertEqual(run_tool(d, "--write")[0], 0)
            for rel in (self.pages[L],):
                t = rd(d, rel)
                self.assertNotIn("Plantedname", PARA.search(t).group(1))
                self.assertEqual(PARA.search(t).group(1), PARA.search(rd(ROOT, rel)).group(1))

    # AC 10
    def test_golden_summaries_match_the_fixtures_byte_for_byte(self):
        self.assertEqual(len(GOLDEN), 14)
        for L in GOLDEN:
            with open(os.path.join(FIX, L + ".html"), "rb") as f:
                want = f.read()
            got = (PARA.search(rd(ROOT, self.pages[L])).group(0) + "\n").encode("utf-8")
            self.assertEqual(got, want, L)
        self.assertEqual(sorted(os.listdir(FIX)), sorted(L + ".html" for L in GOLDEN))

    def test_shared_service_sentence_exact_on_goldens(self):
        sh = html.escape(SH_SENTENCE, quote=True)
        for L in ("3400990", "3401590"):  # ufb_shared Y; 3400990 has S3, 3401590 is term-ended (no S3)
            t = self.parsed[L].summary
            self.assertIn(SH_SENTENCE, t)
            self.assertEqual(t.count(SH_SENTENCE), 1)
            self.assertIn(sh, rd(ROOT, self.pages[L]))
        self.assertIn("contract on file runs", self.parsed["3400990"].summary)
        self.assertNotIn("contract on file runs", self.parsed["3401590"].summary)
        self.assertNotIn(SH_SENTENCE, self.parsed["3416800"].summary)  # Vineland: ufb_shared N
        self.assertNotIn("shared-service", self.parsed["3416800"].summary)
        # SH appears exactly on the 40 pages whose latest rows have ufb_shared Y, and the S3 sentence never carries the add-on
        n = 0
        for L, p in self.parsed.items():
            self.assertNotRegex(p.summary, r"runs [^.]*shared")
            n += SH_SENTENCE in p.summary
        self.assertEqual(n, 40)

    # AC 11
    def test_all_distinct_and_salary_pages_have_two_numbers(self):
        self.assertEqual(len({p.summary for p in self.parsed.values()}), 586)
        for L, p in self.parsed.items():
            if "reported a superintendent base salary" in p.summary:
                self.assertGreaterEqual(len(TOKEN.findall(p.summary)), 2, L)
                self.assertGreaterEqual(len({t for t in TOKEN.findall(p.summary) if t.startswith("$") or re.fullmatch(r"\d+\.\d+", t)}), 1, L)

    # AC 13
    def test_only_the_paragraph_changes_in_a_district_page_against_the_base(self):
        n = 0
        for L, rel in self.pages.items():
            base = subprocess.run(["git", "-C", ROOT, "show", f"{BASE}:{rel}"], capture_output=True, check=True).stdout
            with open(os.path.join(ROOT, *rel.split("/")), "rb") as f:
                now = f.read()
            self.assertNotEqual(now, base)
            self.assertEqual(Y.strip(now), base, rel)  # title, description, JSON-LD, charts markup and every <main> byte outside the paragraph
            n += 1
        self.assertEqual(n, 586)

    def test_changed_files_are_only_tools_tests_docs_district_pages_and_the_sitemap(self):
        ch = subprocess.run(["git", "-C", ROOT, "diff", "--name-only", BASE], capture_output=True, check=True, text=True).stdout.split()
        ch += subprocess.run(["git", "-C", ROOT, "ls-files", "--others", "--exclude-standard"], capture_output=True, check=True, text=True).stdout.split()
        bad = [f for f in ch if not (f.startswith(("tools/", "tests/", "docs/")) or DISTRICT.fullmatch(f) or f == "sitemap.xml")]
        self.assertEqual(bad, [])
        for f in ch:
            self.assertFalse(f.startswith(("api/", "data/", "charts/")), f)

    def test_sitemap_still_611_urls_with_the_release_date(self):
        sm = rd(ROOT, "sitemap.xml")
        self.assertEqual(sm.count("<url>"), 611)
        base = subprocess.run(["git", "-C", ROOT, "show", f"{BASE}:sitemap.xml"], capture_output=True, check=True).stdout.decode()
        self.assertEqual(re.findall(r"<loc>[^<]*</loc>", sm), re.findall(r"<loc>[^<]*</loc>", base))
        for loc, d in re.findall(r"<url><loc>([^<]*)</loc><lastmod>([^<]*)</lastmod>", sm):
            if "/nj/" in loc and not loc.endswith("/nj/history/"):
                self.assertEqual(d, "2026-11-24", loc)

    # AC 14
    def test_release_date_and_run_order_in_the_docs(self):
        import nj_indexing as I
        self.assertEqual(I.RELEASE_DATE, "2026-11-24")
        doc = rd(ROOT, "docs/nj-district-summaries.md")
        i = [doc.index(x) for x in ("1. The history build", "2. The existing rewrites", "3. `tools/nj_district_summaries.py --write`", "4. `tools/nj_indexing.py --write`")]
        self.assertEqual(i, sorted(i))
        self.assertIn("`nj_chart_label_edge`", doc)
        self.assertIn("2026-11-24", rd(ROOT, "docs/nj-indexing.md"))
        self.assertIn("nj_district_summaries", rd(ROOT, "docs/nj-indexing.md"))

    # AC 20
    def test_docs_name_the_tool_the_copy_file_and_every_slot(self):
        doc = rd(ROOT, "docs/nj-district-summaries.md")
        for s in ("tools/nj_district_summaries.py", "tools/nj_district_summaries_copy.json", "--trace", "--check", "--write", "max_words",
                  "RELEASE_DATE", "FORMULA", "shared-service", "Lindsay"):
            self.assertIn(s, doc)
        for slot in S.SLOTS:
            self.assertRegex(doc, rf"\*\*{slot}\*\*")
        self.assertIn(SH_SENTENCE, doc)
        self.assertIn("S5_one", doc)


class ScratchTree(unittest.TestCase):
    """AC 2 on temp copies of the committed tree."""

    @classmethod
    def setUpClass(cls):
        cls._d = tempfile.TemporaryDirectory(prefix="k12ds-")
        cls.d = cls._d.name
        copy_site(cls.d)
        cls.committed = sha_tree(cls.d)

    @classmethod
    def tearDownClass(cls):
        cls._d.cleanup()

    def fresh(self):
        t = tempfile.TemporaryDirectory(prefix="k12ds-s-")
        self.addCleanup(t.cleanup)
        copy_site(t.name)
        return t.name

    def test_committed_tree_is_final_and_write_twice_is_byte_identical(self):
        d = self.fresh()
        self.assertEqual(run_tool(d, "--check")[0], 0)
        self.assertEqual(run_tool(d, "--write")[0], 0)
        first = sha_tree(d)
        self.assertEqual(first, self.committed)
        self.assertEqual(run_tool(d, "--write")[0], 0)
        self.assertEqual(sha_tree(d), first)
        self.assertEqual(run_tool(d)[0], 0)  # the default mode writes
        self.assertEqual(sha_tree(d), first)
        self.assertEqual(run_tool(d, "--check")[0], 0)

    def test_rebuild_from_pages_without_the_paragraph_gives_the_committed_bytes(self):
        d = self.fresh()
        for rel in pages(d).values():
            p = os.path.join(d, *rel.split("/"))
            text = Y.strip(rd(d, rel))
            with open(p, "w", encoding="utf-8", newline="") as f:
                f.write(text)
        self.assertNotEqual(sha_tree(d), self.committed)
        self.assertEqual(run_tool(d, "--check")[0], 1)
        self.assertEqual(run_tool(d, "--write")[0], 0)
        self.assertEqual(sha_tree(d), self.committed)

    def test_runs_before_nj_indexing_on_pages_without_the_county_breadcrumb(self):
        """The chain runs this tool before nj_indexing, when the breadcrumb has no county yet: the /nj/ table's County cell gives the same text."""
        d = self.fresh()
        for rel in pages(d).values():
            p = os.path.join(d, *rel.split("/"))
            text = X.undo(rel, rd(d, rel))
            with open(p, "w", encoding="utf-8", newline="") as f:
                f.write(text)
        self.assertTrue(all(Page(rd(d, rel)).county is None and not Page(rd(d, rel)).paras for rel in list(pages(d).values())[:50]))
        self.assertEqual(run_tool(d, "--write")[0], 0)
        for L, rel in pages(d).items():
            self.assertEqual(Page(rd(d, rel)).paras, Page(rd(ROOT, rel)).paras, L)

    def test_check_is_1_on_a_stale_tree(self):
        for mutate in (lambda t: t.replace("The latest superintendent", "The latest superintendents", 1),  # changed wording
                       lambda t: PARA.sub("", t, count=1),  # missing
                       lambda t: PARA.sub(lambda m: m.group(0) * 2, t, count=1),  # twice
                       lambda t: re.sub(r"(<p class=\"disclaimer\">[^<]*</p>)(<p class=\"district-summary\".*?</p>)", r"\2\1", t, count=1)):  # moved
            d = self.fresh()
            rel = pages(d)["3416800"]
            p = os.path.join(d, *rel.split("/"))
            t = rd(d, rel)
            new = mutate(t)
            self.assertNotEqual(new, t)
            with open(p, "w", encoding="utf-8", newline="") as f:
                f.write(new)
            rc, out = run_tool(d, "--check")
            self.assertEqual(rc, 1, out)
            self.assertIn(rel, out)
            self.assertEqual(run_tool(d, "--write")[0], 0)
            self.assertEqual(sha_tree(d), self.committed)

    def test_a_changed_data_value_makes_the_tree_stale(self):
        d = self.fresh()
        L = "3416800"
        doc = doc_of(d, L)
        doc["superintendent_contracts"][0]["ufb_work_days"] = "261"
        with open(os.path.join(d, "api", "v1", "nj", L + ".json"), "w", encoding="utf-8") as f:
            json.dump(doc, f, sort_keys=True)
        self.assertEqual(run_tool(d, "--check")[0], 1)

    def test_trace_inside_the_site_is_refused(self):
        d = self.fresh()
        rc, _ = run_tool(d, "--check", "--trace", os.path.join(d, "trace.json"))
        self.assertEqual(rc, 2)
        self.assertFalse(os.path.exists(os.path.join(d, "trace.json")))

    def test_the_tool_reads_only_its_three_inputs(self):
        """Pages, per-district JSON and history CSV: deleting every other file the copy has changes nothing (the /nj/ table is the one extra page)."""
        d = self.fresh()
        for f in os.listdir(os.path.join(d, "api", "v1", "nj")):
            if not re.fullmatch(r"\d{7}\.json", f):
                os.remove(os.path.join(d, "api", "v1", "nj", f))
        self.assertEqual(run_tool(d, "--check")[0], 0)


if __name__ == "__main__":
    unittest.main()
