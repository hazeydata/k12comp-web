"""Fail-closed release guard for the NJ history build (AC 29). It never deploys.

    python3 tools/nj_history_release_guard.py preflight [--repo .]
        CI preflight: needs the data-repo read secret (K12_DATA_READ_TOKEN, only checked for presence, never printed) when CI is set,
        a data repo clone at the pinned commit with every input matching its lock hash, and a clean tree with no build/ output, no tracked statewide CSV and no tracked file over 1 MB.
    python3 tools/nj_history_release_guard.py release --head <40-hex sha> --gates <file outside the repo> --out <dir outside the repo>
        Requires, for that exact head: test-run PASS, Weatherman SHIP, pre-deploy-check PASS, Fred's go relayed by chief, and a
        pre-push scan with 0 findings. Then runs the preflight checks, builds the site into --out and checks the output.
        Success only means "a build for this head may go to a preview or deploy step"; the deploy itself is not part of this tool.

Any missing, malformed, stale or untrusted input exits non-zero with the reason. There is no skip mode.
Gates file: JSON {"test_run": {"status": "PASS", "head": sha}, "weatherman": {"status": "SHIP", "head": sha},
"pre_deploy_check": {"status": "PASS", "head": sha}, "fred_go": {"status": "GO", "relayed_by": "chief", "head": sha},
"prepush_scan": {"findings": 0, "head": sha}}. It is produced by chief outside this repo and is never committed.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nj_history import build, data  # noqa: E402

# Pristine site the history build starts from; must equal the sha in .github/workflows/ci.yml and tests/nj_history_helpers.py.
SITE_BASE_COMMIT = "3b50ce10b88e80188e6c8265634b68b482c1a81f"
SECRET = "K12_DATA_READ_TOKEN"
MAX_TRACKED = 1024 * 1024
HEAD_RE = re.compile(r"[0-9a-f]{40}")
REQUIRED = (("test_run", "status", "PASS"), ("weatherman", "status", "SHIP"), ("pre_deploy_check", "status", "PASS"),
            ("fred_go", "status", "GO"), ("prepush_scan", "findings", 0))


class GuardError(Exception):
    pass


def git(repo, *args):
    p = subprocess.run(["git", "-C", repo, *args], capture_output=True)
    if p.returncode != 0:
        raise GuardError(f"git {args[0]} failed in {repo}")
    return p.stdout.decode()


def extract_base(repo, dest):
    """Extract a git archive of SITE_BASE_COMMIT from repo into the empty directory dest."""
    git_p = subprocess.Popen(["git", "-C", repo, "archive", SITE_BASE_COMMIT], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        tar_p = subprocess.run(["tar", "-x", "-C", dest], stdin=git_p.stdout, capture_output=True)
    finally:
        git_p.stdout.close()
        git_err = git_p.stderr.read()
        git_p.stderr.close()
        git_rc = git_p.wait()
    if git_rc != 0:
        raise GuardError(f"git archive of base commit {SITE_BASE_COMMIT[:12]} failed (is the full history checked out?): "
                         + git_err.decode(errors="replace").strip()[:200])
    if tar_p.returncode != 0:
        raise GuardError(f"extracting the base commit archive failed: {tar_p.stderr.decode(errors='replace').strip()[:200]}")


def check_gates(gates, head):
    if not HEAD_RE.fullmatch(head or ""):
        raise GuardError("--head must be a full 40-character commit sha")
    if not isinstance(gates, dict):
        raise GuardError("gates file must be a JSON object")
    bad = []
    for name, key, want in REQUIRED:
        g = gates.get(name)
        if not isinstance(g, dict):
            bad.append(f"{name}: missing")
        elif g.get(key) != want:
            bad.append(f"{name}: {key} is {g.get(key)!r}, need {want!r}")
        elif g.get("head") != head:
            bad.append(f"{name}: recorded for head {str(g.get('head'))[:12]!r}, not the exact head {head[:12]}")
    if isinstance(gates.get("fred_go"), dict) and gates["fred_go"].get("relayed_by") != "chief":
        bad.append("fred_go: must be relayed by chief")
    if bad:
        raise GuardError("release gates not satisfied: " + "; ".join(bad))


def load_gates(path, text, repo):
    if text is None:
        if not path:
            raise GuardError("no gates: pass --gates <file> or set K12_RELEASE_GATES (JSON)")
        real, root = os.path.realpath(path), os.path.realpath(repo)
        if real == root or real.startswith(root + os.sep):
            raise GuardError("the gates file must live outside the repo (a committed gates file proves nothing)")
        if not os.path.isfile(real):
            raise GuardError(f"gates file not found: {path}")
        with open(real, encoding="utf-8") as f:
            text = f.read()
    try:
        return json.loads(text)
    except ValueError as e:
        raise GuardError(f"gates are not valid JSON: {e}")


def check_repo(repo, head=None):
    actual = git(repo, "rev-parse", "HEAD").strip()
    if head is not None and actual != head:
        raise GuardError(f"checked-out HEAD {actual[:12]} is not the head being released {head[:12]}")
    if git(repo, "status", "--porcelain").strip():
        raise GuardError("working tree is not clean")
    tracked = git(repo, "ls-files", "-z").split("\0")
    for t in filter(None, tracked):
        # The small built files (data/nj/history/*.csv, data/nj/nj-history-coverage.csv) are committed so GitHub Pages can serve them.
        if t.startswith("build/") or t.endswith("nj-district-staff-history.csv"):
            raise GuardError(f"generated output is tracked in git: {t}")
        fp = os.path.join(repo, t)
        if os.path.isfile(fp) and os.path.getsize(fp) > MAX_TRACKED:
            raise GuardError(f"tracked file over 1 MB: {t}")
    return actual


def check_secret(env):
    if env.get("CI") and not env.get(SECRET):
        raise GuardError(f"{SECRET} is not set. Provision a read-only token for the data repo as the CI secret {SECRET} "
                         "(owner: chief / Fred); the build cannot read its pinned inputs without it and will not skip.")


def check_inputs(data_repo, lock_path=None):
    if not data_repo or not os.path.isdir(data_repo):
        raise GuardError("data repo clone not found: set K12_DATA_REPO to a clone of hazeydata/k12comp at the pinned commit")
    lock = data.load_lock(lock_path)
    try:
        inp = data.Inputs(lock, repo=data_repo)
        for p in data.INPUT_PATHS:
            inp.read(p)  # verifies the sha256 of every input against the lock
    except data.BuildError as e:
        raise GuardError(f"pinned inputs are missing or untrusted: {e}")
    return lock


def check_output(out, lock):
    need = ["nj/history/index.html", "data/nj/nj-district-staff-history.csv", "data/nj/nj-history-coverage.csv", "sitemap.xml", "CNAME", "robots.txt"]
    missing = [n for n in need if not os.path.exists(os.path.join(out, *n.split("/")))]
    if missing:
        raise GuardError(f"build output is incomplete: {missing}")
    with open(os.path.join(out, "sitemap.xml"), encoding="utf-8") as f:
        if "https://k12comp.com/nj/history/" not in f.read():
            raise GuardError("sitemap lacks /nj/history/")


def release(repo, head, gates_path, out, data_repo, env, lock_path=None):
    repo_real, out_real = os.path.realpath(repo), os.path.realpath(out)
    if out_real == repo_real or out_real.startswith(repo_real + os.sep):
        raise GuardError("--out must be outside the repo (generated files are never committed)")
    gates = load_gates(gates_path, env.get("K12_RELEASE_GATES"), repo)
    check_gates(gates, head)
    check_repo(repo, head)
    check_secret(env)
    lock = check_inputs(data_repo, lock_path)
    with tempfile.TemporaryDirectory(prefix="k12nj-base-") as base:
        extract_base(repo, base)
        try:
            build.run(site_root=base, out_dir=out, data_repo=data_repo, lock_path=lock_path)
        except data.BuildError as e:
            raise GuardError(f"build failed: {e}")
    check_output(out, lock)
    return f"GUARD OK: build for {head} written to {out}. Nothing was deployed; deploy needs its own approval."


def main(argv=None, env=None):
    env = os.environ if env is None else env
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    pf = sub.add_parser("preflight")
    pf.add_argument("--repo", default=".")
    pf.add_argument("--data-repo", default=env.get("K12_DATA_REPO"))
    rl = sub.add_parser("release")
    rl.add_argument("--repo", default=".")
    rl.add_argument("--head", required=True)
    rl.add_argument("--gates")
    rl.add_argument("--out", required=True)
    rl.add_argument("--data-repo", default=env.get("K12_DATA_REPO"))
    a = ap.parse_args(argv)
    try:
        if a.cmd == "preflight":
            check_secret(env)
            check_inputs(a.data_repo)
            check_repo(a.repo)
            print("PREFLIGHT OK")
        else:
            print(release(a.repo, a.head, a.gates, a.out, a.data_repo, env))
    except GuardError as e:
        print(f"GUARD FAILED: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
