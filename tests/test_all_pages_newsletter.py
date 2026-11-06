"""Every rendered newsletter form in the site must be live, not an inert preview."""
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from html.parser import HTMLParser

ROOT = pathlib.Path(__file__).resolve().parent.parent
DISTRICT = re.compile(r"^nj/[a-z0-9-]+-\d{7}/index\.html$")
SAFE_PLACEHOLDER = "you@example.org"


class Forms(HTMLParser):
    def __init__(self):
        super().__init__()
        self.forms, self.scripts, self.inert, self.in_nl = [], [], 0, False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "data-inert" in a:
            self.inert += 1
        if tag == "section" and a.get("data-slot") == "newsletter":
            self.in_nl = True
        if tag == "form":
            self.forms.append({"attrs": a, "inputs": {}, "newsletter": self.in_nl or "nl-form" in a.get("class", "")})
        elif tag == "input" and self.forms:
            self.forms[-1]["inputs"][a.get("name")] = a
        elif tag == "script":
            self.scripts.append(a)

    def handle_endtag(self, tag):
        if tag == "section":
            self.in_nl = False


def parse(text):
    p = Forms()
    p.feed(text)
    return p


def site_pages(root):
    return sorted(f for f in root.rglob("*.html") if ".git" not in f.relative_to(root).parts)


class AllNewsletterForms(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pages = {str(f.relative_to(ROOT)): parse(f.read_text(encoding="utf-8")) for f in site_pages(ROOT)}
        cls.nl = [(k, f, p) for k, p in cls.pages.items() for f in p.forms if f["newsletter"]]

    def test_expected_pages_have_exactly_one_form(self):
        expected = {k for k in self.pages if k == "index.html" or DISTRICT.match(k)}
        self.assertGreater(len(expected), 500)
        for k in expected:
            self.assertEqual(sum(1 for f in self.pages[k].forms if f["newsletter"]), 1, k)
        self.assertEqual({k for k, _, _ in self.nl}, expected)

    def test_no_inert_marker_anywhere(self):
        self.assertEqual([k for k, p in self.pages.items() if p.inert], [])

    def test_action_method_and_source(self):
        for k, f, _ in self.nl:
            self.assertEqual(f["attrs"].get("action"), "https://hazeydata.ai/api/subscribe", k)
            self.assertEqual(f["attrs"].get("method", "").lower(), "post", k)
            src = f["inputs"].get("source", {})
            self.assertEqual((src.get("type"), src.get("value")), ("hidden", "k12comp"), k)

    def test_fields_and_accessibility(self):
        for k, f, _ in self.nl:
            self.assertEqual(sorted(f["inputs"]), ["email", "source", "website"], k)
            em, hp = f["inputs"]["email"], f["inputs"]["website"]
            self.assertEqual(em.get("type"), "email", k)
            self.assertIn("required", em, k)
            self.assertEqual(em.get("autocomplete"), "email", k)
            self.assertEqual((hp.get("tabindex"), hp.get("autocomplete")), ("-1", "off"), k)

    def test_newsletter_js_included(self):
        for k, _, p in self.nl:
            js = [s for s in p.scripts if s.get("src") == "/newsletter.js"]
            self.assertEqual(len(js), 1, k)
            self.assertIn("defer", js[0], k)
        self.assertTrue((ROOT / "newsletter.js").is_file())

    def test_no_placeholder_or_fake_success_copy(self):
        for f in site_pages(ROOT):
            low = f.read_text(encoding="utf-8").lower()
            for bad in ("coming soon", "nothing was sent", "{{placeholder", "provider form action"):
                self.assertNotIn(bad, low, f"{f}: {bad}")

    def test_email_placeholder_is_exact_safe_value(self):
        for k, f, _ in self.nl:
            self.assertEqual(f["inputs"]["email"].get("placeholder"), SAFE_PLACEHOLDER, k)

    def test_other_pages_have_no_newsletter_form(self):
        for k in ("404.html", "about/index.html", "nj/index.html", "privacy/index.html", "terms/index.html"):
            self.assertEqual([f for f in self.pages[k].forms if f["newsletter"]], [], k)


class GeneratorOutput(unittest.TestCase):
    def test_generator_template_uses_safe_placeholder(self):
        text = (ROOT / "tools" / "seo_postbuild.py").read_text(encoding="utf-8")
        self.assertEqual(re.findall(r'placeholder="([^"]*)"', text), [SAFE_PLACEHOLDER])

    def test_generator_rewrites_inert_leftover_and_is_idempotent(self):
        src = ROOT / "nj" / "edison-twp-3404500" / "index.html"
        with tempfile.TemporaryDirectory() as d:
            tmp = pathlib.Path(d) / "site"
            (tmp / "nj" / "edison-twp-3404500").mkdir(parents=True)
            html = src.read_text(encoding="utf-8")
            inert = re.sub(r'<section class="newsletter".*?</section>',
                           lambda _: '<section class="newsletter" data-slot="newsletter" aria-labelledby="nl-h">'
                                     '<form class="nl-form" novalidate data-inert="true"><input type="email" name="email"></form></section>',
                           html, count=1, flags=re.S)
            self.assertIn("data-inert", inert)
            page = tmp / "nj" / "edison-twp-3404500" / "index.html"
            page.write_text(inert, encoding="utf-8")
            tool = str(ROOT / "tools" / "seo_postbuild.py")
            for _ in range(2):
                subprocess.run([sys.executable, "-I", tool, str(tmp)], check=True, capture_output=True)
                self.assertEqual(page.read_text(encoding="utf-8"), html)


if __name__ == "__main__":
    unittest.main()
