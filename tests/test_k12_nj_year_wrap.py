"""K12-NJ-YEAR-WRAP-001 (bundled in K12-CHART-LABEL-EDGE-001): the /nj/ Year cell stays on one line at every width by one CSS rule, with no HTML change."""
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def rt(rel):
    with open(os.path.join(ROOT, *rel.split("/")), encoding="utf-8", newline="") as fh:
        return fh.read()


class YearCell(unittest.TestCase):
    def test_year_is_column_4_and_the_nowrap_rule_is_in_the_css_once(self):
        page = rt("nj/index.html")
        head = re.search(r'<table id="districts">.*?</thead>', page, re.S).group(0)
        ths = re.findall(r"<th[^>]*>([^<]*)</th>", head)
        self.assertEqual(ths[3], "Year")  # th 4 is td:nth-of-type(3): the row's own th is the District cell
        css = rt("style.css")
        self.assertEqual(css.count("#districts td:nth-of-type(3){white-space:nowrap}"), 1)
        before = css[:css.index("#districts td:nth-of-type(3){white-space:nowrap}")]
        self.assertEqual(before.count("{") - before.count("}"), 0)  # top level, not inside a media query: at all widths


if __name__ == "__main__":
    unittest.main()
