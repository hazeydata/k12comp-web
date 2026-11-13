"""K12-CHART-LABEL-EDGE-001 in a real browser: every text node of every district chart (all 1146) has its em box inside its SVG, and no
desktop value label sits on the x-axis line, at the gated content widths: mobile charts at 304 and 358 px (336 and 390 viewports), desktop
charts at 1072 px (1280 viewport). Em box = getBoundingClientRect of the <text>, as in the spec's measurement script.

Needs the Python `playwright` package and a local Chrome (K12_CHROME, default /usr/bin/google-chrome); skipped otherwise. The charts are
inlined into one local page (no network, no server), one throwaway profile that is removed and the browser closed in `finally`.
"""
import glob
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_nj_guide_tables_browser import CHROME, sync_playwright  # noqa: E402

WIDTHS = {"mobile": (304, 358), "desktop": (1072,)}
JS = """() => {
  const over = [], axis = [];
  for (const s of document.querySelectorAll('svg[data-id]')) {
    const sr = s.getBoundingClientRect(), vb = s.viewBox.baseVal, k = sr.width / vb.width;
    const ax = [...s.querySelectorAll('line')].find(l => l.getAttribute('stroke') === '#999999');
    const ay = ax ? sr.top + (+ax.getAttribute('y1') - vb.y) * k : null, x1 = ax ? sr.left + (+ax.getAttribute('x1') - vb.x) * k : 0;
    const x2 = ax ? sr.left + (+ax.getAttribute('x2') - vb.x) * k : 0, half = 0.5 * k;
    for (const t of s.querySelectorAll('text')) {
      const e = t.getBoundingClientRect();
      if (e.top < sr.top - 0.01 || e.bottom > sr.bottom + 0.01 || e.left < sr.left - 0.01 || e.right > sr.right + 0.01)
        over.push(s.dataset.id + ' ' + t.textContent + ' top ' + (sr.top - e.top).toFixed(2));
      if (ax && t.classList.contains('v') && e.top < ay + half && e.bottom > ay - half && e.left < x2 && e.right > x1)
        axis.push(s.dataset.id + ' ' + t.textContent);
    }
  }
  return {n: document.querySelectorAll('svg[data-id]').length, over, axis};
}"""


def page(kind, width):
    svgs = []
    for f in sorted(glob.glob(os.path.join(ROOT, "charts", "d", f"*-{kind}.svg"))):
        with open(f, encoding="utf-8") as fh:
            svg = fh.read()
        svgs.append(svg.replace("<svg ", f'<svg data-id="{os.path.basename(f)}" style="display:block;width:100%;height:auto" ', 1))
    return f'<!doctype html><meta charset="utf-8"><body style="margin:0"><div style="width:{width}px">' + "".join(svgs) + "</div>"


@unittest.skipUnless(sync_playwright and os.path.exists(CHROME), "needs the playwright package and a local Chrome")
class ChartsInChrome(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.res = {}
        with tempfile.TemporaryDirectory(prefix="k12-label-edge-browser-") as prof, sync_playwright() as p:
            ctx = p.chromium.launch_persistent_context(prof, executable_path=CHROME, headless=True, env=dict(os.environ, TMPDIR=prof))
            try:
                pg = ctx.new_page()
                for kind, widths in WIDTHS.items():
                    for w in widths:
                        pg.set_viewport_size({"width": w + 32, "height": 900})
                        pg.set_content(page(kind, w))
                        pg.evaluate("document.fonts.ready")
                        cls.res[(kind, w)] = pg.evaluate(JS)
            finally:
                ctx.close()

    def test_no_text_box_leaves_its_chart_and_no_value_label_is_on_the_axis(self):
        for (kind, w), r in self.res.items():
            self.assertEqual(r["n"], 573, (kind, w))
            self.assertEqual(r["over"], [], (kind, w))
            self.assertEqual(r["axis"], [], (kind, w))


if __name__ == "__main__":
    unittest.main()
