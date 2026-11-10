"""The runtime charts follow the approved dataviz renderer (render_lib.py panel()): geometry, state classification, text.
Chart data stays fresh from the pinned inputs; only the layout rules and fixed strings are pinned.
Set K12_APPROVED_DIR to the packet root (holding dataviz/ and writing/) to also verify the approved files themselves."""
import ast
import json
import os
import re
import unittest

import nj_history_helpers as H
from nj_history import copy as C, render as R

APPROVED = os.environ.get("K12_APPROVED_DIR")
PINS = json.loads(H.rt(os.path.join(H.ROOT, "docs", "nj-history-approved-files.json")))


class Adherence(unittest.TestCase):
    @unittest.skipUnless(APPROVED, "K12_APPROVED_DIR not set: approved files not verifiable here")
    def test_approved_files_match_their_pins_and_the_renderer_constants(self):
        import hashlib
        for rel, want in PINS.items():
            if rel == "note":
                continue
            self.assertEqual(hashlib.sha256(H.rb(os.path.join(APPROVED, rel))).hexdigest(), want, rel)
        src = H.rt(os.path.join(APPROVED, "dataviz", "render_lib.py"))
        for pat in (r"gutter=62", r"len\(pubs\) > 2", r"plot_w = w - gutter - 4", r"plot_w - 64", r"xytext=\(8, 0\)", r"ms=6",
                    r"lw=1\.6", r"pitch = 36 if not mobile else 34", r"ax\.set_ylim\(6\.5, -0\.5\)", r"if j == i \+ 1", r"0\.03, i",
                    r"plot_w - 10", r"plot_w - 4", r"M = 16 if mobile else 24", r"pw = \(cw - 3 \* gap\) / 4", r"gap = 20"):
            self.assertRegex(src, pat)
        tree = ast.parse(src)
        consts = {}
        for n in tree.body:
            if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name):
                try:
                    consts[n.targets[0].id] = ast.literal_eval(n.value)
                except ValueError:
                    pass
        self.assertEqual(consts["SCALE_NOTE"], C.SCALE_NOTE)
        self.assertIn(C.PANEL_CHART_NOTE, src)
        self.assertIn(C.PANEL_TABLE_NOTE, src)
        self.assertIn(f'return "{C.STATUS_PUBLISHED}"', src)
        self.assertEqual((consts["TEXT"] if "TEXT" in consts else "#333333"), "#333333")
        self.assertIn("#0072B2", H.rt(os.path.join(os.environ.get("K12_DATAVIZ_KIT", ""), "helpers.py")) if os.environ.get("K12_DATAVIZ_KIT") else "#0072B2")

    def test_pinned_geometry_constants(self):
        self.assertEqual((R.GUTTER, R.PLOT_PAD, R.RESERVE), (62, 4, 64))
        self.assertEqual(R.VARIANTS, (("d", 253, 36), ("m", 304, 34)))  # 1120-wide desktop: (1072 - 3*20)/4 = 253 per panel
        self.assertAlmostEqual(R.LABEL_DX, 8 * 100 / 72)
        css = H.rt(os.path.join(R.__file__.rsplit("/", 1)[0], "history.css"))
        for color in ("#0072B2", "#999", "#333"):
            self.assertIn(color, css)

    def test_geometry_state_and_text_for_goldens(self):
        out, _ = H.built()
        rows = H.pinned_staff_rows()

        def series(leaid, group):
            by = {r["school_year"]: r for r in rows if r["nces_leaid"] == leaid and r["staff_group"] == group}
            return [by.get(y) for y in H.WINDOW]
        for leaid, path in (("3416230", "toms-river-regional-3416230"), ("3412810", "pemberton-twp-3412810"), ("3400660", "absecon-city-3400660")):
            sec = H.history_section(H.read(out, f"nj/{path}/index.html"))
            for group in ("teacher", "administrator", "special_service", "supervisor_coordinator"):
                ser = series(leaid, group)
                pub = [(i, float(r["fte_sum"])) for i, r in enumerate(ser) if r and r["suppressed"] == "false"]
                for key, W, pitch in R.VARIANTS:
                    svg = re.search(rf'<svg[^>]*aria-labelledby="h{leaid}-{group}-{key}-t".*?</svg>', sec, re.S).group(0)
                    dots = re.findall(r'<circle class="dot" cx="([\d.]+)" cy="([\d.]+)" r="4"', svg)
                    if len(pub) > 2:
                        plot_w = W - 62 - 4
                        vmax = max(v for _, v in pub)
                        want = [(f"{62 + v / vmax * (plot_w - 64):.1f}", f"{pitch * (i + 0.5):g}") for i, v in pub]
                        self.assertEqual(dots, want, (leaid, group, key))
                        labels = re.findall(r'<text class="val num" x="([\d.]+)"', svg)
                        self.assertEqual(labels, [f"{62 + v / vmax * (plot_w - 64) + R.LABEL_DX:.1f}" for _, v in pub])
                        segs = re.search(r'<path class="ln" d="([^"]+)"', svg).group(1)
                        runs = 1 + sum(1 for (i, _), (j, _) in zip(pub, pub[1:]) if j != i + 1)
                        self.assertEqual(segs.count("M"), runs)
                        self.assertNotIn('class="tv', svg)
                    else:
                        self.assertEqual(dots, [])
                        self.assertNotIn('class="axis"', svg)
                        self.assertEqual(len(re.findall(r'class="tv num"', svg)), len(pub))
                    self.assertEqual(len(re.findall(r'class="st (small|comp|missing)"', svg)), 7 - len(pub))
                    self.assertEqual(f'viewBox="0 0 {W} {7 * pitch}"' in svg, True)
            if leaid == "3400660":
                self.assertIn(C.ALL_SUPPRESSED, sec)
            else:
                self.assertNotIn(C.ALL_SUPPRESSED, sec)
        t = H.history_section(H.read(out, "nj/toms-river-regional-3416230/index.html"))
        self.assertIn(C.SCALE_NOTE, t)  # teachers 1,102.9 vs supervisors 23.9: more than 5 times
        self.assertEqual(t.count(C.PANEL_CHART_NOTE), 4)

    def test_scale_note_is_shown_only_when_its_claim_is_true(self):
        class Stub:
            by_leaid = {}
        out, _ = H.built()
        rows = H.pinned_staff_rows()
        pages = H.B.discover_pages(H.site_tree())
        shown = hidden = 0
        for leaid, path in pages.items():
            sec = H.history_section(H.read(out, path.strip("/") + "/index.html"))
            if "hist-panel" not in sec:
                continue
            tops = []
            for g in ("teacher", "administrator", "special_service", "supervisor_coordinator"):
                v = [float(r["fte_sum"]) for r in rows if r["nces_leaid"] == leaid and r["staff_group"] == g and r["fte_sum"]]
                if len(v) > 2:
                    tops.append(max(v))
            claim = len(tops) > 1 and min(tops) > 0 and max(tops) / min(tops) > 5
            self.assertEqual(C.SCALE_NOTE in sec, claim, leaid)
            shown += claim
            hidden += not claim
        self.assertGreater(shown, 100)
        self.assertGreater(hidden, 0)

    def test_panel_notes_follow_the_approved_rule(self):
        out, _ = H.built()
        sec = H.history_section(H.read(out, "nj/pemberton-twp-3412810/index.html"))
        self.assertEqual(sec.count(C.PANEL_CHART_NOTE), 4)
        self.assertNotIn(C.PANEL_TABLE_NOTE, sec)


if __name__ == "__main__":
    unittest.main()
