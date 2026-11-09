"""Runs nj_history_browser.js against a local, unsigned-in headless Chrome and a local HTTP server (not Cloudflare).

    python3 tests/browser/run_browser_check.py --build build/site --out <dir> --playwright-core <dir> --chrome <exe>

One throwaway profile and TMPDIR live inside one TemporaryDirectory; every path this run creates is recorded in
<out>/created-paths.txt and only those are removed. The browser process group is killed in finally.
"""
import argparse
import functools
import http.server
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
PAGES = [("absecon", "/nj/absecon-city-3400660/"), ("pemberton", "/nj/pemberton-twp-3412810/"),
         ("seaside-park", "/nj/seaside-park-boro-3414820/"), ("toms-river", "/nj/toms-river-regional-3416230/"),
         ("bayonne", "/nj/bayonne-city-3401260/"), ("statewide", "/nj/history/")]
MIN_FREE = 5 * 1024 ** 3


class Quiet(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map, ".csv": "text/csv; charset=utf-8",
                      ".woff2": "font/woff2", ".svg": "image/svg+xml", ".json": "application/json"}

    def log_message(self, *a):
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--playwright-core", required=True)
    ap.add_argument("--chrome", required=True)
    ap.add_argument("--widths", default="[336,390,1280,1440]")
    a = ap.parse_args()
    if shutil.disk_usage(tempfile.gettempdir()).free < MIN_FREE:
        print("STOP: less than 5 GB free", file=sys.stderr)
        return 3
    out = os.path.abspath(a.out)
    for d in ("shots", "ax"):
        os.makedirs(os.path.join(out, d), exist_ok=True)
    created = []
    srv = proc = None
    try:
        with tempfile.TemporaryDirectory(prefix="k12nj-browser-") as tmp:
            profile, tdir = os.path.join(tmp, "profile"), os.path.join(tmp, "tmp")
            os.makedirs(profile)
            os.makedirs(tdir)
            created += [tmp, profile, tdir]
            handler = functools.partial(Quiet, directory=os.path.abspath(a.build))
            srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            env = dict(os.environ, TMPDIR=tdir, HOME=tmp, PLAYWRIGHT_CORE=a.playwright_core, CHROME_PATH=a.chrome,
                       BASE_URL=f"http://127.0.0.1:{srv.server_address[1]}", PROFILE_DIR=profile, OUT_DIR=out,
                       PAGES=json.dumps([{"name": n, "path": p} for n, p in PAGES]), WIDTHS=a.widths)
            proc = subprocess.Popen(["node", os.path.join(HERE, "nj_history_browser.js")], env=env,
                                    start_new_session=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                so, se = proc.communicate(timeout=900)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                so, se = proc.communicate()
                print("browser run timed out", file=sys.stderr)
            print(so)
            if se:
                print(se, file=sys.stderr)
            leftovers = sorted(os.path.join(dp, f) for dp, dn, fn in os.walk(tdir) for f in fn + dn)
            created += leftovers
            rc = proc.returncode
    finally:
        if proc is not None and proc.poll() is None:
            os.killpg(proc.pid, signal.SIGKILL)
        if srv is not None:
            srv.shutdown()
            srv.server_close()
    with open(os.path.join(out, "created-paths.txt"), "w") as f:
        f.write("\n".join(created[:3]) + f"\n(+{len(created) - 3} files/dirs inside, removed with the TemporaryDirectory)\n")
    print("temp dir removed:", not os.path.exists(created[0]))
    return rc


if __name__ == "__main__":
    sys.exit(main())
