"""One-off generators for the committed name tables and the lock (pin.json).

    python3 tools/nj_history_postbuild.py --gen-lock --data-repo <k12comp clone> --commit <full sha>

Re-run only on a re-pin; the build then checks the tables and every input against the lock (AC 1, AC 3).
"""
import csv
import glob
import html
import io
import json
import os
import re

from . import data as D


def write_csv(path, header, rows):
    buf = io.StringIO(newline="")
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(header)
    w.writerows(rows)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(buf.getvalue())


def district_page_names(site_root):
    out = {}
    for f in sorted(glob.glob(os.path.join(site_root, "nj", "*", "index.html"))):
        m = re.search(r"-(\d{7})$", os.path.basename(os.path.dirname(f)))
        if not m:
            continue
        with open(f, encoding="utf-8") as fh:
            h1 = re.search(r"<h1>(.*?)</h1>", fh.read())
        out[m.group(1)] = html.unescape(h1.group(1))
    return out


def gen_lock(site_root, data_repo, commit, snapshot_date, copy_sha256=None):
    here = D.HERE
    lock = {"data_repo": "hazeydata/k12comp", "data_commit": commit, "snapshot_date": snapshot_date,
            "inputs": {}, "names": {}, "copy_sha256": copy_sha256}
    pre = dict(lock, inputs={p: "" for p in D.INPUT_PATHS})
    inputs = D.Inputs(pre, repo=data_repo)
    raws = {}
    for p in D.INPUT_PATHS:
        inputs.lock = dict(pre)
        raws[p] = inputs._git("show", f"{commit}:{p}")
        lock["inputs"][p] = D.sha256_hex(raws[p])
    names = district_page_names(site_root)
    write_csv(os.path.join(here, "district_names.csv"), ["nces_leaid", "district"], sorted(names.items()))
    staff = {}
    for y in D.WINDOW:  # latest school year's spelling wins for each county district code
        _, rows = D.read_csv_text(raws[f"data/nj_district_staff_{y}.csv"].decode("utf-8"), D.STAFF_FILE_COLS, y)
        for r in rows:
            staff[r["nj_county_district_code"]] = r["district"]
    write_csv(os.path.join(here, "nj_staff_district_names.csv"), ["nj_county_district_code", "district"],
              sorted(staff.items()))
    for fn in ("district_names.csv", "nj_staff_district_names.csv"):
        with open(os.path.join(here, fn), "rb") as f:
            lock["names"][fn] = D.sha256_hex(f.read())
    with open(os.path.join(here, "pin.json"), "w", encoding="utf-8") as f:
        json.dump(lock, f, indent=2, sort_keys=True)
        f.write("\n")
    return lock
