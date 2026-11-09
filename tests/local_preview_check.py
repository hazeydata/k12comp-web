"""Local HTTP check of a build directory (AC 16, AC 23 responses). This is a LOCAL server, not the Cloudflare preview.

    python3 tests/local_preview_check.py --build build/site [--out results.json]
"""
import argparse
import functools
import http.server
import json
import re
import sys
import threading
import urllib.request


class Quiet(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map, ".csv": "text/csv; charset=utf-8",
                      ".json": "application/json", ".txt": "text/plain; charset=utf-8"}

    def log_message(self, *a):
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", required=True)
    ap.add_argument("--out")
    a = ap.parse_args()
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=a.build))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        def get(path):
            with urllib.request.urlopen(base + path) as r:
                return r.status, r.headers.get("Content-Type", ""), r.read()
        sm = get("/sitemap.xml")[2].decode()
        urls = [re.sub(r"^https://k12comp.com", "", u) for u in re.findall(r"<loc>(.*?)</loc>", sm)]
        paths = urls + ["/privacy/", "/terms/", "/llms.txt", "/robots.txt", "/CNAME", "/history.css"]
        paths += [f"/api/v1/nj/{m}.json" for m in sorted(set(re.findall(r"-(\d{7})/", " ".join(urls))))]
        paths += ["/data/nj/nj-district-staff-history.csv", "/data/nj/nj-history-coverage.csv", "/data/nj/history/3416230.csv"]
        bad, res = [], {"sitemap_urls": len(urls), "checked": 0, "csv_content_types": {}}
        for p in paths:
            try:
                st, ct, _ = get(p)
            except Exception as e:  # noqa: BLE001
                bad.append((p, str(e)))
                continue
            res["checked"] += 1
            if st != 200:
                bad.append((p, st))
            if p.endswith(".csv"):
                res["csv_content_types"][p] = ct
                if not ct.startswith("text/csv"):
                    bad.append((p, ct))
        res["failures"] = bad
        res["note"] = "local http.server over the build directory; not the Cloudflare preview"
    finally:
        srv.shutdown()
        srv.server_close()
    print(json.dumps(res, indent=1))
    if a.out:
        open(a.out, "w").write(json.dumps(res, indent=1) + "\n")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
