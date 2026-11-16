"""K12-NJ-UPKEEP-001: the chart3 mobile "districts" y-axis title moved from x="4" to x="6" (its x and rotate centre, one node) after the
base commits other tests compare against. `undo_chart3` maps the current file back to its pre-ticket text so those comparisons stay exact."""
CHART3_MOBILE = "charts/chart3-nj-salary-distribution-mobile.svg"
OLD = 'x="4" y="213.7856" transform="rotate(-90 4 213.7856)">districts</text>'
NEW = 'x="6" y="213.7856" transform="rotate(-90 6 213.7856)">districts</text>'


def undo_chart3(text):
    assert text.count(NEW) == 1, "chart3 mobile: expected exactly one moved districts label"
    return text.replace(NEW, OLD)
