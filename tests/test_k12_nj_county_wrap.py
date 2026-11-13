"""K12-NJ-COUNTY-WRAP-001: the /nj/ County cell stays on one line at every width by one CSS rule, with no HTML change (same pattern as the Year rule)."""
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULE = "#districts td:nth-of-type(1){white-space:nowrap}"


def rt(rel):
    with open(os.path.join(ROOT, *rel.split("/")), encoding="utf-8", newline="") as fh:
        return fh.read()


class CountyCell(unittest.TestCase):
    def test_county_is_column_2_and_the_nowrap_rule_is_in_the_css_once(self):
        page = rt("nj/index.html")
        head = re.search(r'<table id="districts">.*?</thead>', page, re.S).group(0)
        ths = re.findall(r"<th[^>]*>([^<]*)</th>", head)
        self.assertEqual(ths[1], "County")  # th 2 is td:nth-of-type(1): the row's own th is the District cell
        css = rt("style.css")
        self.assertEqual(css.count(RULE), 1)
        before = css[:css.index(RULE)]
        self.assertEqual(before.count("{") - before.count("}"), 0)  # top level, not inside a media query: at all widths


if __name__ == "__main__":
    unittest.main()
