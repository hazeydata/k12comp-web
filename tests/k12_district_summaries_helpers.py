"""K12-DISTRICT-SUMMARIES-001: tools/nj_district_summaries.py added one <p class="district-summary" id="district-summary"> after the disclaimer of
every district page, after the base commits other tests compare against. `strip(text)` takes exactly that paragraph out (str or bytes in, same type
out), so older byte-diff tests keep comparing the rest of the page unchanged. tests/test_k12_district_summaries.py checks the paragraph itself.
The regex is written here, not taken from the tool."""
import re

PARA = re.compile(r'<p class="district-summary" id="district-summary">[^<]*</p>')


def strip(text):
    raw = isinstance(text, bytes)
    t = text.decode("utf-8") if raw else text
    t = PARA.sub("", t)
    return t.encode("utf-8") if raw else t
