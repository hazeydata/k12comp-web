"""K12-INDEXING-001 (Ann's 304px fix): at <=640px the .hist-panels grid is one column that can shrink (minmax(0,1fr)), so the
304px minimum column no longer overflows a 272px content box. The rule must be in the fresh build's /history.css and the committed copy
must equal the source file."""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nj_history_helpers as H  # noqa: E402

SRC = os.path.join(H.ROOT, "tools", "nj_history", "history.css")


def has_rule(css):
    """True when a max-width:640px @media block has a .hist-panels rule whose grid-template-columns is minmax(0,1fr) (whitespace-loose)."""
    for m in re.finditer(r"@media\s*\(\s*max-width\s*:\s*640px\s*\)\s*\{", css):
        depth, i = 1, m.end()
        while i < len(css) and depth:
            depth += {"{": 1, "}": -1}.get(css[i], 0)
            i += 1
        body = css[m.end():i - 1]
        for sel, decls in re.findall(r"([^{}]+)\{([^{}]*)\}", body):
            if sel.strip() == ".hist-panels" and re.search(r"(?:^|;)\s*grid-template-columns\s*:\s*minmax\(\s*0\s*,\s*1fr\s*\)\s*(?:;|$)", decls.strip()):
                return True
    return False


class HistPanelsMobile(unittest.TestCase):
    def test_source_and_committed_css_have_the_rule_and_are_identical(self):
        self.assertEqual(H.rb(SRC), H.rb(os.path.join(H.ROOT, "history.css")))
        self.assertTrue(has_rule(H.rt(SRC)))

    def test_matcher_rejects_copies_without_the_rule(self):
        css = H.rt(SRC)
        self.assertTrue(has_rule(css))
        self.assertFalse(has_rule(css.replace("minmax(0, 1fr)", "minmax(304px, 358px)")))
        self.assertFalse(has_rule(css.replace("@media (max-width: 640px) {\n  .hist-panels", "@media (min-width: 641px) {\n  .hist-panels")))
        self.assertFalse(has_rule(css.replace(".hist-panels { grid-template-columns", ".hist-other { grid-template-columns")))
        self.assertFalse(has_rule(css.replace("@media (max-width: 640px) {\n  .hist-panels { grid-template-columns: minmax(0, 1fr); }\n}\n", "")))

    @unittest.skipUnless(H.DATA_REPO, "K12_DATA_REPO is needed for the fresh build")
    def test_fresh_build_output_has_the_rule(self):
        out, _ = H.built()
        built = H.read(out, "history.css")
        self.assertTrue(has_rule(built))
        self.assertEqual(built.encode("utf-8"), H.rb(os.path.join(H.ROOT, "history.css")))
        self.assertFalse(has_rule(built.replace("minmax(0, 1fr)", "1fr")))


if __name__ == "__main__":
    unittest.main()
