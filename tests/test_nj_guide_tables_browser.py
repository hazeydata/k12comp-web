"""PR #5 fix list, fix 1 (K12-SITE-NJ-HISTORY-001), in a real browser: all 8 guide pages, all 40 guide tables, at 336, 390 and 1280 px.

- The caption is outside the horizontal scroller, fully inside the viewport and not clipped, before and after scrolling right,
  and it is still the table's accessible name (Chrome's own accessibility tree).
- The swipe cue shows above the scroller at 336/390 exactly on the tables that overflow, and is hidden at 1280.
- The Step column stays at the scroller's left edge after scrolling right, and the last column becomes fully visible beside it.
- Salary cells keep every digit on one line at 16 px; the page itself never scrolls sideways.
- The guide source line wraps with its sentence: the link starts on the "Source:" line, the page reference follows the link
  without breaking, the link keeps a 44 px target, and the whole line stays inside the viewport.

Needs the Python `playwright` package and a local Chrome (K12_CHROME, default /usr/bin/google-chrome); skipped otherwise.
Local only: a 127.0.0.1 server over the committed tree, a throwaway profile, and every other request aborted.

    /path/to/venv/bin/python -m unittest tests/test_nj_guide_tables_browser.py
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
import nj_guide_tables as G  # noqa: E402

CHROME = os.environ.get("K12_CHROME", "/usr/bin/google-chrome")
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

PAGES = ["/" + os.path.dirname(os.path.relpath(p, ROOT)).replace(os.sep, "/") + "/" for p in G.guide_pages()]

MEASURE = """() => {
  const vw = document.documentElement.clientWidth, out = [];
  document.querySelectorAll('details.year').forEach(d => d.open = true);
  const box = el => { const r = el.getBoundingClientRect(); return {l: r.left, r: r.right, t: r.top, b: r.bottom, w: r.width, h: r.height}; };
  document.querySelectorAll('section.grid').forEach(sec => {
    const wrap = sec.querySelector('.table-wrap'), table = wrap.querySelector('table');
    const cap = document.getElementById(table.getAttribute('aria-labelledby')) || table.querySelector('caption') || sec.querySelector('.guide-caption');
    const cue = sec.querySelector('.guide-cue');
    const tds = [...table.querySelectorAll('td.num')];
    const lastCol = [...table.querySelectorAll('tr')].map(tr => tr.lastElementChild);
    const firstCol = [...table.querySelectorAll('tr')].map(tr => tr.firstElementChild);
    const state = () => ({
      wrap: box(wrap), cap: box(cap), capSw: cap.scrollWidth, capCw: cap.clientWidth,
      cueShown: !!cue && getComputedStyle(cue).display !== 'none', cue: cue ? box(cue) : null,
      first: firstCol.map(box), last: lastCol.map(box),
    });
    const s0 = state();
    wrap.scrollLeft = wrap.scrollWidth;
    const s1 = state();
    const scrolled = wrap.scrollLeft;
    wrap.scrollLeft = 0;
    const src = sec.querySelector('.src-short'), a = src.querySelector('a');
    const trail = a.nextSibling, rng = document.createRange();
    rng.selectNodeContents(trail);
    const trailRects = [...rng.getClientRects()];
    out.push({
      caption: cap.textContent, capInWrap: !!cap.closest('.table-wrap'), cueInWrap: !!(cue && cue.closest('.table-wrap')),
      cueText: cue ? cue.textContent : null, cols: table.querySelectorAll('thead th').length,
      sw: wrap.scrollWidth, cw: wrap.clientWidth, scrolled, s0, s1,
      cells: tds.map(td => ({sw: td.scrollWidth, cw: td.clientWidth, lines: td.getClientRects().length, h: td.getBoundingClientRect().height,
                              fs: getComputedStyle(td).fontSize, ws: getComputedStyle(td).whiteSpace, text: td.textContent})),
      src: {box: box(src), text: src.textContent, aRects: [...a.getClientRects()].map(r => ({l: r.left, r: r.right, t: r.top, h: r.height})),
            srcTop: box(src).t, trail: trail.data, trailRects: trailRects.map(r => ({l: r.left, t: r.top, r: r.right}))},
    });
  });
  return {vw, docSw: document.documentElement.scrollWidth, tables: out};
}"""


class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


@unittest.skipUnless(sync_playwright and os.path.exists(CHROME), "needs the playwright package and a local Chrome")
class GuideTablesInChrome(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Q, directory=ROOT))
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.srv.server_address[1]}"
        cls.blocked, cls.res, cls.names = [], {}, {}
        try:
            with tempfile.TemporaryDirectory(prefix="k12-guide-browser-") as prof, sync_playwright() as p:
                ctx = p.chromium.launch_persistent_context(prof, executable_path=CHROME, headless=True,
                                                           env=dict(os.environ, TMPDIR=prof))  # Chrome's own temp files go with the profile
                try:
                    ctx.route("**/*", cls.local_only)
                    pg = ctx.new_page()
                    cdp = ctx.new_cdp_session(pg)
                    for w in (336, 390, 1280):
                        pg.set_viewport_size({"width": w, "height": 900})
                        for path in PAGES:
                            pg.goto(cls.base + path)
                            pg.evaluate("document.fonts.ready")
                            cls.res[(w, path)] = pg.evaluate(MEASURE)
                            if w == 390:
                                cls.names[path] = cls.table_names(cdp)
                finally:
                    ctx.close()
        finally:
            cls.srv.shutdown()
            cls.srv.server_close()

    @classmethod
    def local_only(cls, route):
        if route.request.url.startswith(cls.base + "/"):
            route.continue_()
        else:
            cls.blocked.append(route.request.url)
            route.abort()

    @staticmethod
    def table_names(cdp):
        doc = cdp.send("DOM.getDocument", {"depth": 0})
        ids = cdp.send("DOM.querySelectorAll", {"nodeId": doc["root"]["nodeId"], "selector": "section.grid table"})["nodeIds"]
        out = []
        for i in ids:
            node = cdp.send("Accessibility.getPartialAXTree", {"nodeId": i, "fetchRelatives": False})["nodes"][0]
            out.append((node["role"]["value"], node["name"]["value"]))
        return out

    def each(self, widths):
        for w in widths:
            for path in PAGES:
                r = self.res[(w, path)]
                for i, t in enumerate(r["tables"]):
                    yield w, path, i, r, t

    def test_forty_tables_on_eight_pages_and_no_external_request_left_the_box(self):
        self.assertEqual(len(PAGES), 8)
        self.assertEqual(sum(len(self.res[(336, p)]["tables"]) for p in PAGES), 40)
        self.assertTrue(all(u.startswith("http") for u in self.blocked))

    def test_page_never_scrolls_sideways(self):
        for (w, path), r in self.res.items():
            self.assertLessEqual(r["docSw"], r["vw"], (w, path))

    def test_caption_outside_the_scroller_and_fully_visible_initially_and_scrolled_right(self):
        for w, path, i, r, t in self.each((336, 390, 1280)):
            self.assertFalse(t["capInWrap"], (w, path, i))
            for s in (t["s0"], t["s1"]):
                self.assertLessEqual(s["capSw"], s["capCw"], (w, path, i))
                self.assertGreaterEqual(s["cap"]["l"], -0.5)
                self.assertLessEqual(s["cap"]["r"], r["vw"] + 0.5, (w, path, i))
                self.assertLessEqual(s["cap"]["b"], s["wrap"]["t"] + 0.5, (w, path, i))  # above the scroller, not in it
            self.assertEqual(t["s0"]["cap"], t["s1"]["cap"])  # scrolling the table does not move or cut the caption

    def test_caption_is_still_the_tables_accessible_name(self):
        for path in PAGES:
            caps = [t["caption"] for t in self.res[(390, path)]["tables"]]
            self.assertEqual(self.names[path], [("table", c) for c in caps], path)

    def test_cue_shows_above_the_scroller_at_336_and_390_exactly_where_columns_are_hidden(self):
        shown = 0
        for w, path, i, r, t in self.each((336, 390)):
            overflow = t["sw"] > t["cw"] + 1
            self.assertEqual((t["s0"]["cueShown"], t["s1"]["cueShown"]), (overflow, overflow), (w, path, i, t["cols"]))
            if overflow:
                shown += 1
                self.assertEqual(t["cueText"], G.SCROLL_CUE)
                self.assertFalse(t["cueInWrap"])
                for s in (t["s0"], t["s1"]):
                    self.assertGreater(s["cue"]["h"], 0)
                    self.assertGreaterEqual(s["cue"]["t"], s["cap"]["b"] - 0.5)
                    self.assertLessEqual(s["cue"]["b"], s["wrap"]["t"] + 0.5)
                    self.assertLessEqual(s["cue"]["r"], r["vw"] + 0.5)
        self.assertEqual(shown, 46)  # 23 tables at each width

    def test_cue_hidden_and_nothing_scrolls_at_1280(self):
        for w, path, i, r, t in self.each((1280,)):
            self.assertFalse(t["s0"]["cueShown"], (path, i))
            self.assertEqual(t["s0"]["cue"]["h"] if t["s0"]["cue"] else 0, 0)
            self.assertLessEqual(t["sw"], t["cw"] + 1, (path, i))

    def test_step_column_sticks_when_scrolled_right_and_the_last_column_is_reachable(self):
        for w, path, i, r, t in self.each((336, 390)):
            if t["sw"] <= t["cw"] + 1:
                continue
            self.assertGreater(t["scrolled"], 0)
            left = t["s0"]["wrap"]["l"]
            for s in (t["s0"], t["s1"]):
                for c in s["first"]:
                    self.assertLessEqual(abs(c["l"] - (left + 1)), 1.5, (w, path, i, c))  # 1 px region border
            for first, last in zip(t["s1"]["first"], t["s1"]["last"]):
                self.assertGreaterEqual(last["l"], first["r"] - 0.5, (w, path, i))
                self.assertLessEqual(last["r"], t["s1"]["wrap"]["r"] + 0.5, (w, path, i))

    def test_salary_cells_keep_every_digit_on_one_line_at_full_size(self):
        for w, path, i, r, t in self.each((336, 390, 1280)):
            for c in t["cells"]:
                self.assertRegex(c["text"], r"^\$\d{1,3}(,\d{3})*$")
                self.assertEqual(c["fs"], "16px")
                self.assertLessEqual(c["sw"], c["cw"] + 1, (w, path, c))
                self.assertEqual(c["lines"], 1)
                self.assertLess(c["h"], 2 * 24 + 24, (w, path, c))  # one 24 px line plus 2 x 12 px padding
                if w < 641:
                    self.assertEqual(c["ws"], "nowrap")

    def test_source_line_wraps_with_its_sentence(self):
        for w, path, i, r, t in self.each((336, 390)):
            s = t["src"]
            self.assertTrue(s["text"].startswith("Source: "))
            self.assertRegex(s["trail"], r"^, pages? \d+(–\d+)?$")
            a = s["aRects"]
            self.assertLessEqual(abs(a[0]["t"] - s["srcTop"]), 12, (w, path, s))  # the link starts on the "Source:" line
            for x in a:
                self.assertGreaterEqual(x["h"], 43.5, (w, path))
                self.assertLessEqual(x["r"], r["vw"] + 0.5)
            tr = s["trailRects"]
            self.assertEqual(len(tr), 1, (w, path, s["trail"], tr))  # ", pages 58–62" stays on one line ...
            self.assertLessEqual(abs(tr[0]["t"] - (a[-1]["t"] + 12)), 3, (w, path, tr, a))  # ... the link's last line
            self.assertLessEqual(s["box"]["r"], r["vw"] + 0.5)


if __name__ == "__main__":
    unittest.main()
