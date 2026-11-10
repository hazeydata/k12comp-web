"""NJ history post-build (K12-SITE-NJ-HISTORY-001). Run from the repo root:

    K12_DATA_REPO=<k12comp clone> python3 tools/nj_history_postbuild.py --out ../k12comp-web-site

Reads the pinned inputs (tools/nj_history/pin.json) with git show; writes the site plus history to --out.
See docs/nj-history.md.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nj_history import build, data, gen  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--site", default=".", help="site tree to extend (default: current directory)")
    ap.add_argument("--out", help="output directory, outside the repo (must be new or empty)")
    ap.add_argument("--data-repo", default=os.environ.get("K12_DATA_REPO"), help="k12comp data repo clone (read-only)")
    ap.add_argument("--fixture-dir", help="test-only inputs; needs K12_FIXTURE_MODE=1")
    ap.add_argument("--names-dir", help="test-only name tables; needs --fixture-dir")
    ap.add_argument("--lock", help="lock file (default tools/nj_history/pin.json)")
    ap.add_argument("--report", help="write a JSON build report here")
    ap.add_argument("--gen-lock", action="store_true", help="re-pin: regenerate name tables and the lock")
    ap.add_argument("--commit", help="full data commit sha for --gen-lock")
    ap.add_argument("--snapshot-date", help="YYYY-MM-DD (America/Toronto) for --gen-lock")
    ap.add_argument("--copy-sha256", help="sha256 of the approved copy for --gen-lock")
    a = ap.parse_args(argv)
    if not a.out and not a.gen_lock:
        ap.error("--out is required")
    if a.names_dir and not a.fixture_dir:
        ap.error("--names-dir is test-only and needs --fixture-dir")
    try:
        if a.gen_lock:
            if not (a.commit and a.snapshot_date and a.data_repo):
                ap.error("--gen-lock needs --commit, --snapshot-date and --data-repo")
            lock = gen.gen_lock(a.site, a.data_repo, a.commit, a.snapshot_date, a.copy_sha256)
            print("lock written:", a.commit, len(lock["names"]), "name tables")
            return 0
        rep = build.run(a.site, a.out, a.data_repo, a.fixture_dir, a.names_dir, a.lock, a.report)
    except data.BuildError as e:
        print("BUILD FAILED:", e, file=sys.stderr)
        return 1
    print("built", rep["district_pages"], "district pages,", rep["district_csvs"], "district CSVs,",
          rep["staff_rows"], "staff rows ->", a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
