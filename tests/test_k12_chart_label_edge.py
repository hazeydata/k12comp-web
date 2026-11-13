"""K12-CHART-LABEL-EDGE-001 : every district chart has 4 units of top headroom (header only), the one desktop
value label on the x-axis (3414220 `$20,000`) sits above its dot and `tools/nj_chart_label_edge.py --check` is the failing gate. Comparisons with web main 8c6ad859 skip cleanly when git or that commit is missing."""
import contextlib
import glob
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import nj_chart_label_edge as E  # noqa: E402
import nj_mobile_chart_fit as F  # noqa: E402

MAIN = "8c6ad859f4b7aba9760c2771304fba318466523b"  # web main this ticket starts from
GIT = shutil.which("git") is not None and subprocess.run(["git", "-C", ROOT, "cat-file", "-e", MAIN + "^{commit}"], capture_output=True).returncode == 0
needs_main = unittest.skipUnless(GIT, "git and web main 8c6ad859 are needed")
RIGHT_OF_AXIS = ["3401020", "3401470", "3402400", "3407680", "3408190", "3418240"]  # desktop labels at baseline > 268, right of the axis end
HEADER = {"mobile": '<svg xmlns="http://www.w3.org/2000/svg" width="304" height="304" viewBox="0 -4 304 304" role="img"><rect y="-4" width="304" height="304" fill="#ffffff"/>',
          "desktop": '<svg xmlns="http://www.w3.org/2000/svg" width="1120" height="324" viewBox="0 -4 1120 324" role="img"><rect y="-4" width="1120" height="324" fill="#ffffff"/>'}
V = re.compile(r'<text class="v"[^>]*>[^<]*</text>')


def rd(path):
    with open(path, encoding="utf-8", newline="") as fh:
        return fh.read()


def rt(rel):
    return rd(os.path.join(ROOT, *rel.split("/")))


def put(path, text):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def run(argv, chars=None):
    with contextlib.redirect_stdout(io.StringIO()) as out:
        code = E.main(argv, chars=chars)
    return code, out.getvalue()


def chart_files():
    return sorted(glob.glob(os.path.join(ROOT, "charts", "d", "*.svg")))


class Header(unittest.TestCase):
    def test_every_chart_has_the_new_header(self):
        fs = chart_files()
        self.assertEqual(len(fs), 1146)
        for f in fs:
            kind = "mobile" if f.endswith("-mobile.svg") else "desktop"
            self.assertTrue(rd(f).startswith(HEADER[kind]), f)

    def test_converting_is_idempotent_and_reversible(self):
        for f in chart_files()[:40]:
            svg = rd(f)
            self.assertEqual(E.add_headroom(svg), svg)
            self.assertEqual(E.add_headroom(E.remove_headroom(svg)), svg, f)

    def test_check_exits_0_on_the_tree(self):
        r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "nj_chart_label_edge.py"), "--check"], capture_output=True, text=True)
        self.assertEqual((r.returncode, r.stdout.strip().splitlines()[-1]), (0, "1146 charts, 0 rewritten, 0 problems"))


@needs_main
class AgainstMain(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="k12-label-edge-main-")
        tar = subprocess.run(["git", "-C", ROOT, "archive", MAIN, "charts/d"], capture_output=True, check=True).stdout
        subprocess.run(["tar", "-x", "-C", cls.tmp.name], input=tar, check=True)
        cls.main = os.path.join(cls.tmp.name, "charts", "d")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_only_the_header_and_the_one_label_differ(self):
        """AC 7-9: header-normalised, every chart equals main, except 3414220's desktop `$20,000` x/y (the axis rule)."""
        moved = []
        for f in chart_files():
            name = os.path.basename(f)
            old, new = rd(os.path.join(self.main, name)), E.remove_headroom(rd(f))
            if new != old:
                moved.append(name)
                self.assertEqual(new, old.replace('<text class="v" x="840.0" y="285.0">$20,000</text>', '<text class="v" x="840.0" y="270.0">$20,000</text>'), name)
        self.assertEqual(moved, ["3414220-desktop.svg"])

    def test_labels_right_of_the_axis_end_did_not_move(self):
        for leaid in RIGHT_OF_AXIS:
            name = f"{leaid}-desktop.svg"
            old, new = rd(os.path.join(self.main, name)), rd(os.path.join(ROOT, "charts", "d", name))
            self.assertEqual(V.findall(new), V.findall(old), leaid)
            self.assertTrue(any(float(m) > 268 for m in re.findall(r'<text class="v" x="[\d.]+" y="([\d.]+)"', old)), leaid)

    def test_3414220_label_is_above_its_dot_and_its_mobile_twin_only_changed_header(self):
        new = rt("charts/d/3414220-desktop.svg")
        self.assertIn('<circle cx="832.0" cy="280.0" r="4" fill="#fff" stroke="#458699" stroke-width="1.5" class="pt" data-fte="0.2"/>', new)
        self.assertIn('<text class="v" x="840.0" y="270.0">$20,000</text>', new)  # dot x + 8, dot y - 10: the first (LIFT) candidate was clear
        self.assertEqual(E.remove_headroom(rt("charts/d/3414220-mobile.svg")), rd(os.path.join(self.main, "3414220-mobile.svg")))
        self.assertEqual(E.axis_problems(new), [])
        self.assertEqual(E.axis_problems(rd(os.path.join(self.main, "3414220-desktop.svg"))), ["value label '$20,000' at (840.0, 285.0) sits on the x-axis"])

    def test_the_old_3414220_chart_fails_the_gate_and_write_fixes_it(self):
        with tempfile.TemporaryDirectory(prefix="k12-label-edge-fx-") as tmp:
            shutil.copy(os.path.join(self.main, "3414220-desktop.svg"), tmp)
            code, out = run(["--check"], tmp)
            self.assertEqual(code, 1, out)
            self.assertIn("sits on the x-axis", out)
            self.assertEqual(run(["--write"], tmp)[0], 0)
            self.assertEqual(rd(os.path.join(tmp, "3414220-desktop.svg")), rt("charts/d/3414220-desktop.svg"))

    def test_write_on_a_temp_copy_of_main_reproduces_the_tree_and_is_idempotent(self):
        with tempfile.TemporaryDirectory(prefix="k12-label-edge-copy-") as tmp:
            for f in glob.glob(os.path.join(self.main, "*.svg")):
                shutil.copy(f, tmp)
            code, out = run(["--write"], tmp)
            self.assertEqual((code, out.strip().splitlines()[-1]), (0, "1146 charts, 1146 rewritten, 0 problems"))
            self.assertEqual(run(["--write"], tmp)[1].strip().splitlines()[-1], "1146 charts, 0 rewritten, 0 problems")
            for f in chart_files():
                self.assertEqual(rd(os.path.join(tmp, os.path.basename(f))), rd(f), f)

    def test_mobile_fit_leaves_either_header_as_found(self):
        """The chain's order: nj_mobile_chart_fit --write is a no-op on the new header and keeps the old header on an old-header build."""
        for leaid in ("3414220", "3416230", "3406600"):
            new, desk = rt(f"charts/d/{leaid}-mobile.svg"), rt(f"charts/d/{leaid}-desktop.svg")
            self.assertEqual(F.fit(new, desk), new)
            old = rd(os.path.join(self.main, f"{leaid}-mobile.svg"))
            self.assertEqual(F.fit(old, E.remove_headroom(desk)), E.remove_headroom(new))


class GateFixtures(unittest.TestCase):
    """AC 10: `--check` exits 1 on each fixture."""

    def check(self, name, svg):
        with tempfile.TemporaryDirectory(prefix="k12-label-edge-fx-") as tmp:
            put(os.path.join(tmp, name), svg)
            return run(["--check"], tmp)

    def test_mobile_value_label_at_baseline_14_with_the_old_header(self):
        svg = E.remove_headroom(rt("charts/d/3400720-mobile.svg"))
        self.assertIn('<text class="v" x="298.0" y="14.0" text-anchor="end">$180,000</text>', svg)
        code, out = self.check("3400720-mobile.svg", svg)
        self.assertEqual(code, 1)
        self.assertIn("'$180,000' at (298.0, 14.0) leaves the viewBox (top)", out)

    def test_desktop_key_at_baseline_12_with_the_old_header(self):
        svg = E.remove_headroom(rt("charts/d/3400810-desktop.svg"))
        self.assertIn('<text class="key" x="76.8" y="12.0">Part-time</text>', svg)
        code, out = self.check("3400810-desktop.svg", svg)
        self.assertEqual(code, 1)
        self.assertIn("'Part-time' at (76.8, 12.0) leaves the viewBox (top)", out)

    def test_new_header_does_not_excuse_a_label_too_high(self):
        svg = rt("charts/d/3400810-desktop.svg").replace('<text class="key" x="76.8" y="12.0">', '<text class="key" x="76.8" y="9.0">')
        code, out = self.check("3400810-desktop.svg", svg)
        self.assertEqual(code, 1)
        self.assertIn("leaves the viewBox (top)", out)
        self.assertEqual(self.check("3400810-desktop.svg", rt("charts/d/3400810-desktop.svg"))[0], 0)

    def test_a_desktop_label_on_the_axis_fails(self):
        svg = rt("charts/d/3414220-desktop.svg").replace('x="840.0" y="270.0">$20,000', 'x="840.0" y="285.0">$20,000')
        code, out = self.check("3414220-desktop.svg", svg)
        self.assertEqual(code, 1)
        self.assertIn("sits on the x-axis", out)

    def test_a_label_right_of_the_axis_end_does_not(self):
        self.assertEqual(E.axis_problems(rt("charts/d/3401020-desktop.svg")), [])

    def test_no_axis_candidate_fails_the_write(self):
        """A label that cannot leave the axis stops the build instead of being left on it: here lines cross every spot above and below the dot."""
        old = E.remove_headroom(rt("charts/d/3414220-desktop.svg")).replace('x="840.0" y="270.0">$20,000', 'x="840.0" y="285.0">$20,000')
        lines = "".join(f'<polyline fill="none" stroke="#458699" stroke-width="3" points="700.0,{y}.0 1000.0,{y}.0"/>' for y in range(0, 281, 6))
        with self.assertRaises(ValueError):
            E.move_axis_labels(old.replace("<circle", lines + "<circle", 1))


if __name__ == "__main__":
    unittest.main()
