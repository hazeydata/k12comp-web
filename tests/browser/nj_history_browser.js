// Real-browser checks for the NJ history pages (AC 5, 8, 9, 14, 26 and the layout/AX evidence).
// Driven by tests/browser/run_browser_check.py: it owns the temp profile, the server and the cleanup.
// Env: PLAYWRIGHT_CORE (dir of playwright-core), CHROME_PATH, BASE_URL, PROFILE_DIR, OUT_DIR, PAGES (json), WIDTHS (json)
const path = require('path');
const fs = require('fs');
const { chromium } = require(process.env.PLAYWRIGHT_CORE);

const base = process.env.BASE_URL;
const out = process.env.OUT_DIR;
const pages = JSON.parse(process.env.PAGES);
const widths = JSON.parse(process.env.WIDTHS || '[336,390,1280,1440]');

function pageFn() {
  // runs in the page: layout facts for the history section
  const root = document.querySelector('.nj-hist') || document.body;
  const vw = window.innerWidth;
  const res = { vw, scrollWidth: document.documentElement.scrollWidth, bodyScrollWidth: document.body.scrollWidth,
    overflowX: document.documentElement.scrollWidth > vw + 0.5, outOfView: [], clipped: [], textOverlaps: [], textDotOverlaps: [],
    svgTextOutside: [], tapSmall: [], smallText: [], fonts: {}, svgCount: root.querySelectorAll('svg.hist-svg').length };
  root.querySelectorAll('*').forEach(el => {
    const r = el.getBoundingClientRect();
    if (r.width === 0 && r.height === 0) return;
    if (el.closest('svg') && el.tagName.toLowerCase() !== 'svg') return;
    if (r.right > vw + 0.5 || r.left < -0.5) res.outOfView.push({ tag: el.tagName, cls: el.className && el.className.baseVal === undefined ? String(el.className) : '', l: r.left, r: r.right });
    const cs = getComputedStyle(el);
    if ((cs.overflowX !== 'visible' || cs.overflowY !== 'visible') && el.tagName !== 'HTML' && el.tagName !== 'BODY') {
      if (el.scrollWidth > el.clientWidth + 1 && !el.classList.contains('sr-only') && el.clientWidth > 1) res.clipped.push({ tag: el.tagName, sw: el.scrollWidth, cw: el.clientWidth });
    }
  });
  root.querySelectorAll('a, summary, button').forEach(el => {
    const r = el.getBoundingClientRect();
    if (r.width === 0 && r.height === 0) return;
    if (r.height < 43.5 || r.width < 43.5) res.tapSmall.push({ text: el.textContent.slice(0, 50), w: r.width, h: r.height });
  });
  root.querySelectorAll('svg.hist-svg').forEach(svg => {
    const sr = svg.getBoundingClientRect();
    const texts = [...svg.querySelectorAll('text')].map(t => ({ el: t, r: t.getBoundingClientRect() }));
    const dots = [...svg.querySelectorAll('circle')].map(c => ({ el: c, r: c.getBoundingClientRect() }));
    const scale = sr.width / svg.viewBox.baseVal.width;
    texts.forEach(t => {
      if (t.r.left < sr.left - 0.5 || t.r.right > sr.right + 0.5 || t.r.top < sr.top - 0.5 || t.r.bottom > sr.bottom + 0.5)
        res.svgTextOutside.push({ text: t.el.textContent.slice(0, 40) });
      const fs = parseFloat(getComputedStyle(t.el).fontSize) * scale;
      if (fs < 12) res.smallText.push({ text: t.el.textContent.slice(0, 30), px: fs });
    });
    const inter = (a, b) => Math.min(a.right, b.right) - Math.max(a.left, b.left) > 1 && Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > 1;
    for (let i = 0; i < texts.length; i++) for (let j = i + 1; j < texts.length; j++)
      if (inter(texts[i].r, texts[j].r)) res.textOverlaps.push([texts[i].el.textContent.slice(0, 30), texts[j].el.textContent.slice(0, 30)]);
    texts.forEach(t => dots.forEach(d => { if (inter(t.r, d.r)) res.textDotOverlaps.push(t.el.textContent.slice(0, 30)); }));
  });
  document.querySelectorAll('.nj-hist p, .nj-hist li, .nj-hist td, .nj-hist th, .nj-hist figcaption').forEach(el => {
    const px = parseFloat(getComputedStyle(el).fontSize);
    if (px < 14 - 0.01 && el.getBoundingClientRect().height > 0) res.smallText.push({ text: el.textContent.slice(0, 30), px });
  });
  res.fonts.spaceGrotesk = document.fonts.check('16px "Space Grotesk"');
  res.fonts.loaded = [...document.fonts].filter(f => f.status === 'loaded').map(f => f.family + ' ' + f.weight);
  return res;
}

function axSummary(nodes) {
  const by = new Map(nodes.map(n => [n.nodeId, n]));
  const v = x => (x ? x.value : undefined);
  const items = [];
  for (const n of nodes) {
    if (n.ignored) continue;
    const role = v(n.role);
    if (!['heading', 'table', 'figure', 'group', 'img', 'columnheader', 'rowheader', 'caption', 'list', 'DisclosureTriangle', 'link', 'region', 'main', 'navigation', 'contentinfo'].includes(role)) continue;
    const props = Object.fromEntries((n.properties || []).map(p => [p.name, p.value.value]));
    items.push({ role, name: v(n.name), description: v(n.description), level: props.level, expanded: props.expanded });
  }
  return items;
}

(async () => {
  const results = [];
  const ctx = await chromium.launchPersistentContext(process.env.PROFILE_DIR, {
    executablePath: process.env.CHROME_PATH, headless: true,
    args: ['--no-first-run', '--no-default-browser-check', '--disable-sync', '--disable-extensions', '--disable-background-networking'],
    viewport: { width: 1280, height: 900 }, deviceScaleFactor: 1 });
  try {
    // nothing leaves the machine: any non-local request is aborted and recorded (allowed hosts are the live ones only)
    const blocked = [];
    await ctx.route(u => !u.href.startsWith(base) && !u.href.startsWith('data:'), r => { blocked.push(r.request().url()); return r.abort(); });
    const allowedHosts = ['k12comp.goatcounter.com', 'gc.zgo.at', 'hazeydata.ai'];
    for (const mode of ['fonts', 'nofonts']) {
      await ctx.unroute('**/fonts/**').catch(() => {});
      if (mode === 'nofonts') await ctx.route('**/fonts/**', r => r.abort());
      for (const p of pages) for (const w of widths) {
        const page = await ctx.newPage();
        const external = [];
        page.on('request', rq => { if (!rq.url().startsWith(base)) external.push(rq.url()); });
        await page.setViewportSize({ width: w, height: 900 });
        const resp = await page.goto(base + p.path, { waitUntil: 'networkidle' });
        await page.evaluate(() => document.fonts.ready);
        await page.evaluate(() => document.querySelectorAll('details.hist-table').forEach(d => { d.open = true; }));
        await page.waitForTimeout(150);
        const r = await page.evaluate(pageFn);
        r.name = p.name; r.path = p.path; r.width = w; r.mode = mode; r.status = resp.status(); r.externalRequests = external.filter(u => !u.startsWith('data:') && !allowedHosts.includes(new URL(u).hostname));
        r.blockedAllowedHostRequests = external.filter(u => allowedHosts.includes(new URL(u).hostname));
        const shot = `${p.name}-${w}-${mode}.png`;
        await page.screenshot({ path: path.join(out, 'shots', shot), fullPage: true });
        r.screenshot = shot;
        if (mode === 'fonts' && w === 1280) {
          const cdp = await ctx.newCDPSession(page);
          await cdp.send('Accessibility.enable');
          let tree = await cdp.send('Accessibility.getFullAXTree');
          for (let i = 0; i < 5 && tree.nodes.length < 20; i++) { await page.waitForTimeout(400); tree = await cdp.send('Accessibility.getFullAXTree'); }
          r.axNodes = tree.nodes.length;
          fs.writeFileSync(path.join(out, 'ax', `${p.name}.ax-full.json`), JSON.stringify(tree.nodes));
          fs.writeFileSync(path.join(out, 'ax', `${p.name}.ax-summary.json`), JSON.stringify(axSummary(tree.nodes), null, 1));
          r.ax = `ax/${p.name}.ax-summary.json`;
          await cdp.detach();
        }
        results.push(r);
        await page.close();
      }
    }
  } finally {
    await ctx.close();
  }
  fs.writeFileSync(path.join(out, 'browser-results.json'), JSON.stringify(results, null, 1));
  const bad = results.filter(r => r.overflowX || r.outOfView.length || r.clipped.length || r.svgTextOutside.length || r.textOverlaps.length || r.textDotOverlaps.length || r.tapSmall.length || r.externalRequests.length || r.status !== 200);
  console.log(JSON.stringify({ checks: results.length, failing: bad.map(r => ({ n: r.name, w: r.width, m: r.mode, overflowX: r.overflowX, out: r.outOfView.length, clip: r.clipped.length, svgOut: r.svgTextOutside.length, ov: r.textOverlaps.length, dot: r.textDotOverlaps.length, tap: r.tapSmall.length, ext: r.externalRequests.length, st: r.status })) }));
})().catch(e => { console.error(String(e && e.stack || e)); process.exit(2); });
