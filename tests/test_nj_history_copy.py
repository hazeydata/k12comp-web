"""The approved copy is pinned: every string in tools/nj_history/copy.py occurs verbatim in docs/nj-history-copy.md,
and the rendered pages carry the bound strings."""
import hashlib
import os
import re
import unittest

import nj_history_helpers as H
from nj_history import copy as C

MD = H.rt(os.path.join(H.ROOT, "docs", "nj-history-copy.md"))
LAYOUT = H.rt(os.path.join(H.ROOT, "docs", "nj-history-layout-notes.md"))
MD_SHA256 = "bb20b40955546c553b88a33f3d5872dfda02b1688ccf2ae0b02c1305ec31e662"
DATAVIZ_OWNED = {"PANEL_CHART_NOTE", "PANEL_TABLE_NOTE", "SCALE_NOTE", "STATUS_PUBLISHED"}  # approved dataviz strings; pinned in test_nj_history_dataviz.py
NOT_COPY = {"S_PATH"}


def strings():
    for name, v in vars(C).items():
        if not name.isupper() or name in DATAVIZ_OWNED | NOT_COPY:
            continue
        if isinstance(v, str):
            yield name, v
        elif isinstance(v, tuple):
            for i, s in enumerate(v):
                yield f"{name}[{i}]", s
        elif isinstance(v, dict):
            for k, s in v.items():
                yield f"{name}[{k}]", s


class Copy(unittest.TestCase):
    def test_copy_file_is_pinned(self):
        self.assertEqual(hashlib.sha256(MD.encode("utf-8")).hexdigest(), MD_SHA256)

    def test_every_string_is_verbatim_in_the_approved_copy(self):
        flat = re.sub(r"\s+", " ", MD + " " + LAYOUT)
        missing = []
        n = 0
        for name, s in strings():
            for chunk in re.split(r"\{[a-z_]+\}", s):
                chunk = re.sub(r"\s+", " ", chunk).strip(" .:,;()%")
                if len(chunk) < 3:
                    continue
                n += 1
                if chunk not in flat:
                    missing.append((name, chunk))
        self.assertGreater(n, 80)
        self.assertEqual(missing, [])

    def test_rendered_pages_carry_the_bound_strings(self):
        out, _ = H.built()
        t = H.text_of(H.history_section(H.read(out, "nj/toms-river-regional-3416230/index.html")))
        for s in (C.D_HEADING, C.D_INTRO, "Salary-guide coverage: 2 of 7 school years (28.6%).", "partial history",
                  C.D_COV_EXPLAIN.format(k=2, n=7), C.D_STATE_LINK, C.D_STAFF_HEAD, C.D_FTE_DEF, C.TABLE_TOGGLE,
                  C.GUIDE_LABEL, C.GUIDE_EXPLAIN, "View 2024-25 salary guide.",
                  "View 2025-26 salary guide.", C.DL_DISTRICT, C.DL_ALL, C.DL_COV, C.AS_IS,
                  C.STAFF_CAPTION.format(district="Toms River Regional", first="2019-20", last="2025-26"),
                  C.GUIDE_CAPTION.format(district="Toms River Regional"), C.SUPPRESSED_EXPLAIN, C.MISSING_EXPLAIN):
            self.assertIn(s, t)
        for g in C.GROUP_LABELS.values():
            self.assertIn(g, t)
        for h in C.TABLE_HEADS:
            self.assertIn(h, t)
        a = H.text_of(H.history_section(H.read(out, "nj/absecon-city-3400660/index.html")))
        self.assertIn(C.ALL_SUPPRESSED, a)
        self.assertIn(C.STATUS_SMALL, a)
        s = H.text_of(H.read(out, "nj/history/index.html"))
        for x in (C.S_H1, C.S_INTRO, C.S_BROWSE, C.S_COV_HEAD, C.S_COV_DEF, C.S_COV_CAPTION, *C.S_COV_HEADS, C.S_ALL_LABEL, C.S_ROWS_HEAD,
                  C.S_ROWS_INTRO, C.S_ROWS_CAPTION, *C.S_ROWS_HEADS, C.S_GUIDES_HEAD, C.S_GUIDES_INTRO, C.S_DL_HEAD, C.DL_ALL, C.DL_COV,
                  C.S_CREDITS_HEAD, C.AS_IS):
            self.assertIn(x, s)
        self.assertIn("As of 2026-11-09 (America/Toronto), published teacher salary guides cover 14 of 4,676 district-years (0.3%) "
                      "for 2019-20 to 2025-26: partial history.", s)
        self.assertNotIn("NJ PERC", s)  # the PERC template is conditional and no in-window guide is a PERC document
        self.assertNotRegex(s, r"\{[a-z_]+\}")

    def test_no_unbound_placeholders_on_any_page(self):
        out, _ = H.built()
        import glob
        for f in glob.glob(os.path.join(out, "nj", "*-[0-9][0-9][0-9][0-9][0-9][0-9][0-9]", "index.html")):
            sec = H.history_section(H.rt(f))
            self.assertNotRegex(H.text_of(sec), r"\{[a-z_]+\}", f)

    def test_ac5_wording_distinguishes_the_two_reasons(self):
        self.assertEqual(C.STATUS_SMALL, "Suppressed: fewer than 10.")
        self.assertEqual(C.STATUS_COMP, "Suppressed: hidden to protect a small group.")
        self.assertEqual(C.GUIDE_LABEL, "salary guide (negotiated)")


if __name__ == "__main__":
    unittest.main()
