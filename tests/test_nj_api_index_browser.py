"""PR #5 fix list, QG round 1 nit (K12-SITE-NJ-HISTORY-001): on /api/v1/nj/ at 336 and 390 px no file name ("3400004.json") breaks
inside the name, no table cell breaks inside a word, the page does not scroll sideways and the table stays inside the content column.

The static part (table class, CSS rule, tool output) needs nothing. The browser part needs the Python `playwright` package and a local
Chrome (K12_CHROME, default /usr/bin/google-chrome) and is skipped otherwise: 127.0.0.1 server over the committed tree, throwaway profile,
every other request aborted.
"""
import functools
import http.server
import os
import re
import sys
import tempfile
import threading
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nj_api_index as A  # noqa: E402
from test_nj_guide_tables_browser import CHROME, Q, sync_playwright  # noqa: E402

RULE = ("@media (max-width:640px){.api-files th,.api-files td{overflow-wrap:break-word;padding:12px 6px}.api-files tr>:first-child{padding-left:0}"
        ".api-files tr>:last-child{padding-right:0}.api-files td:first-child{white-space:nowrap}}")

MEASURE = """() => {
  const vw = document.documentElement.clientWidth, r = document.createRange(), midWord = [];
  for (const c of document.querySelectorAll('main table td, main table th')) {
    const tw = document.createTreeWalker(c, NodeFilter.SHOW_TEXT); let n, prev = null, hit = false;
    while (!hit && (n = tw.nextNode())) for (let i = 0; i < n.length; i++) {
      r.setStart(n, i); r.setEnd(n, i + 1); const b = r.getClientRects()[0]; if (!b) continue;
      if (prev && b.top > prev.t + 4 && !/[\\s\\-\\/]/.test(prev.ch)) { midWord.push(c.textContent); hit = true; break; }
      prev = {t: b.top, ch: n.data[i]};
    }
  }
  const files = [...document.querySelectorAll('main tbody td:first-child a')];
  const main = document.querySelector('main'), ps = getComputedStyle(main);
  return {vw, docSw: document.documentElement.scrollWidth, midWord, files: files.length,
          fileLines: files.map(a => { r.selectNodeContents(a); return new Set([...r.getClientRects()].map(x => Math.round(x.top))).size; }),
          fileText: files.map(a => a.textContent), fileH: Math.min(...files.map(a => a.getBoundingClientRect().height)),
          tableRight: document.querySelector('main table').getBoundingClientRect().right,
          contentRight: main.getBoundingClientRect().right - parseFloat(ps.paddingRight)};
}"""


class StaticParts(unittest.TestCase):
    def test_table_class_and_rule(self):
        self.assertIn('<table class="api-files"><caption>NJ district JSON files (586)</caption>', A.render())
        with open(os.path.join(ROOT, "style.css"), encoding="utf-8") as f:
            self.assertIn(RULE, f.read())


@unittest.skipUnless(sync_playwright and os.path.exists(CHROME), "needs the playwright package and a local Chrome")
class ApiIndexInChrome(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Q, directory=ROOT))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{srv.server_address[1]}"
        cls.res = {}
        try:
            with tempfile.TemporaryDirectory(prefix="k12-api-browser-") as prof, sync_playwright() as p:
                ctx = p.chromium.launch_persistent_context(prof, executable_path=CHROME, headless=True, env=dict(os.environ, TMPDIR=prof))
                try:
                    ctx.route("**/*", lambda route: route.continue_() if route.request.url.startswith(base + "/") else route.abort())
                    pg = ctx.new_page()
                    for w in (336, 390, 1280):
                        pg.set_viewport_size({"width": w, "height": 900})
                        pg.goto(base + "/api/v1/nj/")
                        pg.evaluate("document.fonts.ready")
                        cls.res[w] = pg.evaluate(MEASURE)
                finally:
                    ctx.close()
        finally:
            srv.shutdown()
            srv.server_close()

    def test_file_names_whole_and_readable(self):
        for w, r in self.res.items():
            self.assertEqual(r["files"], 586, w)
            self.assertEqual(set(r["fileLines"]), {1}, w)
            self.assertTrue(all(re.fullmatch(r"\d{7}\.json", t) for t in r["fileText"]), w)
            self.assertGreaterEqual(r["fileH"], 43.5, w)

    def test_no_cell_breaks_inside_a_word(self):
        for w, r in self.res.items():
            self.assertEqual(r["midWord"], [], w)

    def test_no_sideways_scroll_and_table_inside_the_content_column(self):
        for w, r in self.res.items():
            self.assertLessEqual(r["docSw"], r["vw"], w)
            self.assertLessEqual(r["tableRight"], r["contentRight"] + 0.5, w)


if __name__ == "__main__":
    unittest.main()
