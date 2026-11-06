"""Parses the real index.html and checks the newsletter signup markup."""
import pathlib
import re
import unittest
from html.parser import HTMLParser

ROOT = pathlib.Path(__file__).resolve().parent.parent
HTML = (ROOT / "index.html").read_text(encoding="utf-8")


class P(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack, self.els, self.text = [], [], []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        self.els.append((tag, a, list(self.stack)))
        if tag not in ("input", "meta", "link", "img", "source", "br"):
            self.stack.append((tag, a))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break

    def handle_data(self, d):
        self.text.append((d, [t for t, _ in self.stack]))


p = P()
p.feed(HTML)


def find(tag, **kw):
    return [e for e in p.els if e[0] == tag and all(e[1].get(k) == v for k, v in kw.items())]


class NewsletterMarkup(unittest.TestCase):
    def setUp(self):
        self.form = find("form", **{"class": "nl-form"})[0][1]

    def test_form_posts_cross_origin(self):
        self.assertEqual(self.form["action"], "https://hazeydata.ai/api/subscribe")
        self.assertEqual(self.form["method"].lower(), "post")

    def test_only_expected_fields(self):
        names = [e[1].get("name") for e in p.els
                 if e[0] == "input" and any(s[1].get("class") == "nl-form" for s in e[2])]
        self.assertEqual(sorted(names), ["email", "source", "website"])

    def test_source_hidden(self):
        s = find("input", name="source")[0][1]
        self.assertEqual((s["type"], s["value"]), ("hidden", "k12comp"))

    def test_honeypot_hidden_from_users_and_at(self):
        e = find("input", name="website")[0]
        self.assertEqual(e[1].get("tabindex"), "-1")
        self.assertEqual(e[1].get("autocomplete"), "off")
        self.assertTrue(any(s[1].get("aria-hidden") == "true" for s in e[2]))

    def test_email_required_and_labelled(self):
        e = find("input", name="email")[0]
        self.assertEqual(e[1]["type"], "email")
        self.assertIn("required", e[1])
        self.assertEqual(e[1].get("autocomplete"), "email")
        self.assertTrue(any(t == "label" for t, _ in e[2]))
        self.assertTrue(any(d == "Email address" and "label" in tags for d, tags in p.text))

    def test_status_live_region(self):
        s = find("p", **{"class": "nl-status"})[0][1]
        self.assertEqual(s["role"], "status")
        self.assertEqual(s["aria-live"], "polite")

    def test_preserved_copy(self):
        flat = " ".join(d for d, _ in p.text)
        for t in ("Know when the numbers change.",
                  "An email when we add new contracts, salary guides or corrections. Nothing else.",
                  "Get updates", "Unsubscribe anytime. See our", "Privacy page"):
            self.assertIn(t, flat)
        self.assertTrue(find("a", href="/privacy/"))
        self.assertEqual(find("button", type="submit", **{"class": "btn ghost"})[0][0], "button")

    def test_no_inert_or_placeholder(self):
        low = HTML.lower()
        for bad in ("coming soon", "data-inert", "placeholder:", "{{", "nothing was sent"):
            self.assertNotIn(bad, low)
        self.assertNotIn("provider", low.split("newsletter", 1)[1].split("</section>", 1)[0])

    def test_script_loaded(self):
        self.assertTrue(find("script", src="/newsletter.js"))
        self.assertTrue((ROOT / "newsletter.js").is_file())

    def test_no_inline_handlers_overwrite(self):
        sec = re.search(r'<section class="newsletter".*?</section>', HTML, re.S).group(0)
        self.assertNotIn("<script>", sec)


if __name__ == "__main__":
    unittest.main()
