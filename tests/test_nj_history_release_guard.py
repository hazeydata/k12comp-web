"""AC 29: the release guard fails closed on every missing, stale or untrusted input, and passes only when all gates hold at the exact head."""
import copy
import io
import json
import os
import subprocess
import unittest
from contextlib import redirect_stderr, redirect_stdout

import nj_history_helpers as H

import nj_history_release_guard as G  # noqa: E402  (tools/ is on sys.path via the helpers)

FAKE_SECRET = "fake-secret-value-for-tests-only"
GIT_ID = ["-c", "user.name=test", "-c", "user.email=test@example.invalid"]


def mkrepo(files=None, tree=None):
    d = H.tmpdir("k12nj-guard-")
    repo = os.path.join(d, "repo")
    if tree:
        os.makedirs(repo)
        subprocess.run(["cp", "-a", tree + "/.", repo], check=True)
    else:
        os.makedirs(repo)
        H.wt(os.path.join(repo, "a.txt"), "x\n")
    for rel, text in (files or {}).items():
        os.makedirs(os.path.dirname(os.path.join(repo, rel)) or repo, exist_ok=True)
        H.wt(os.path.join(repo, rel), text)
    subprocess.run(["git", "-C", repo, "init", "-q"], check=True)
    # the guard builds from an archive of the base commit, so the throwaway repo must contain it
    subprocess.run(["git", "-C", repo, "fetch", "-q", H.ROOT, H.BASE_COMMIT], check=True)
    subprocess.run(["git", "-C", repo, "add", "-A"], check=True)
    subprocess.run(["git", "-C", repo, *GIT_ID, "commit", "-q", "-m", "t"], check=True)
    head = subprocess.run(["git", "-C", repo, "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    return repo, head


def gates_for(head):
    return {"test_run": {"status": "PASS", "head": head}, "weatherman": {"status": "SHIP", "head": head},
            "pre_deploy_check": {"status": "PASS", "head": head}, "fred_go": {"status": "GO", "relayed_by": "chief", "head": head},
            "prepush_scan": {"findings": 0, "head": head}}


def gates_file(g):
    p = os.path.join(H.tmpdir("k12nj-gates-"), "gates.json")
    H.wt(p, g if isinstance(g, str) else json.dumps(g))
    return p


def run_main(argv, env):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = G.main(argv, env)
    return rc, out.getvalue(), err.getvalue()


class Gates(unittest.TestCase):
    def setUp(self):
        self.head = "a" * 40

    def test_all_gates_at_the_exact_head_pass(self):
        G.check_gates(gates_for(self.head), self.head)

    def test_each_gate_is_required_and_exact(self):
        for name in gates_for(self.head):
            g = gates_for(self.head)
            del g[name]
            with self.assertRaisesRegex(G.GuardError, name):
                G.check_gates(g, self.head)
        for name, key, bad in (("test_run", "status", "FAIL"), ("weatherman", "status", "HOLD"), ("pre_deploy_check", "status", "PENDING"),
                               ("fred_go", "status", "WAIT"), ("prepush_scan", "findings", 2)):
            g = gates_for(self.head)
            g[name][key] = bad
            with self.assertRaisesRegex(G.GuardError, name):
                G.check_gates(g, self.head)

    def test_stale_head_is_refused_per_gate(self):
        for name in gates_for(self.head):
            g = gates_for(self.head)
            g[name]["head"] = "b" * 40
            with self.assertRaisesRegex(G.GuardError, f"{name}: recorded for head"):
                G.check_gates(g, self.head)

    def test_go_must_be_relayed_by_chief_and_head_must_be_full_sha(self):
        g = gates_for(self.head)
        g["fred_go"]["relayed_by"] = "someone"
        with self.assertRaisesRegex(G.GuardError, "chief"):
            G.check_gates(g, self.head)
        for bad in ("", "abc", "A" * 40, None):
            with self.assertRaises(G.GuardError):
                G.check_gates(gates_for(self.head), bad)
        with self.assertRaises(G.GuardError):
            G.check_gates([], self.head)


class RepoAndSecret(unittest.TestCase):
    def test_missing_secret_fails_closed_in_ci_with_an_actionable_message(self):
        with self.assertRaises(G.GuardError) as cm:
            G.check_secret({"CI": "true"})
        self.assertIn("K12_DATA_READ_TOKEN", str(cm.exception))
        self.assertIn("chief / Fred", str(cm.exception))
        G.check_secret({"CI": "true", G.SECRET: FAKE_SECRET})
        G.check_secret({})  # on the box the data repo clone is the input; the secret is a CI concern

    def test_repo_head_clean_tree_and_nothing_generated(self):
        repo, head = mkrepo()
        self.assertEqual(G.check_repo(repo, head), head)
        with self.assertRaisesRegex(G.GuardError, "not the head"):
            G.check_repo(repo, "c" * 40)
        H.wt(os.path.join(repo, "a.txt"), "dirty\n")
        with self.assertRaisesRegex(G.GuardError, "not clean"):
            G.check_repo(repo, head)
        big, bh = mkrepo({"big.bin": "x" * (G.MAX_TRACKED + 1)})
        with self.assertRaisesRegex(G.GuardError, "over 1 MB"):
            G.check_repo(big, bh)
        sw, sh = mkrepo({"data/nj/nj-district-staff-history.csv": "a\n"})
        self.assertEqual(G.check_repo(sw, sh), sh)  # the statewide CSV is tracked and allowed
        swbig, swh = mkrepo({"data/nj/nj-district-staff-history.csv": "x" * (G.MAX_TRACKED + 1)})
        self.assertEqual(G.check_repo(swbig, swh), swh)  # and may exceed 1 MB
        self.assertEqual(G.MAX_STATEWIDE, 50 * 1024 * 1024)
        other, oth = mkrepo({"data/nj/other.csv": "x" * (G.MAX_TRACKED + 1)})
        with self.assertRaisesRegex(G.GuardError, "over 1 MB"):
            G.check_repo(other, oth)
        ok, oh = mkrepo({"data/nj/history/3400001.csv": "a\n", "data/nj/nj-history-coverage.csv": "a\n"})
        self.assertEqual(G.check_repo(ok, oh), oh)  # the small committed CSVs are allowed
        bld, bh = mkrepo({"build/x.html": "a\n"})
        with self.assertRaisesRegex(G.GuardError, "generated output is tracked"):
            G.check_repo(bld, bh)

    def test_inputs_must_exist_and_match_the_lock(self):
        with self.assertRaisesRegex(G.GuardError, "data repo clone not found"):
            G.check_inputs(os.path.join(H.tmpdir(), "nope"))
        with self.assertRaisesRegex(G.GuardError, "missing or untrusted"):
            G.check_inputs(H.tmpdir())  # not a git repo
        lock = json.loads(H.rt(os.path.join(G.data.HERE, "pin.json")))
        lock["inputs"]["sources/nj_cs_manifest.csv"] = "0" * 64
        lp = os.path.join(H.tmpdir(), "lock.json")
        H.wt(lp, json.dumps(lock))
        with self.assertRaisesRegex(G.GuardError, "missing or untrusted"):
            G.check_inputs(H.DATA_REPO, lp)


class Release(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo, cls.head = mkrepo(tree=H.site_tree())
        cls.env = {"CI": "true", G.SECRET: FAKE_SECRET}

    def out(self):
        return os.path.join(H.tmpdir("k12nj-guard-out-"), "site")

    def fails(self, gates, env=None, head=None, out=None, repo=None, data_repo=None):
        out = out or self.out()
        argv = ["release", "--repo", repo or self.repo, "--head", head or self.head, "--out", out,
                "--data-repo", data_repo or H.DATA_REPO]
        if gates is not None:
            argv += ["--gates", gates]
        rc, so, se = run_main(argv, self.env if env is None else env)
        self.assertEqual(rc, 1, so)
        self.assertTrue(se.startswith("GUARD FAILED:"), se)
        self.assertNotIn(FAKE_SECRET, so + se)
        self.assertFalse(os.path.exists(os.path.join(out, "nj", "history", "index.html")), "no build output after a refusal")
        return se

    def test_negative_cases_all_fail_closed(self):
        good = gates_for(self.head)
        self.assertIn("no gates", self.fails(None))
        self.assertIn("not found", self.fails(os.path.join(H.tmpdir(), "missing.json")))
        self.assertIn("not valid JSON", self.fails(gates_file("{nope")))
        inside = os.path.join(self.repo, "gates.json")
        H.wt(inside, json.dumps(good))
        self.assertIn("outside the repo", self.fails(inside))
        os.remove(inside)
        bad = copy.deepcopy(good)
        bad["weatherman"]["status"] = "HOLD"
        self.assertIn("weatherman", self.fails(gates_file(bad)))
        stale = copy.deepcopy(good)
        stale["test_run"]["head"] = "d" * 40
        self.assertIn("exact head", self.fails(gates_file(stale)))
        self.assertIn("not the head", self.fails(gates_file(gates_for("e" * 40)), head="e" * 40))
        self.assertIn("K12_DATA_READ_TOKEN", self.fails(gates_file(good), env={"CI": "true"}))
        self.assertIn("data repo clone not found", self.fails(gates_file(good), data_repo=os.path.join(H.tmpdir(), "none")))
        self.assertIn("--out must be outside", self.fails(gates_file(good), out=os.path.join(self.repo, "out")))

    def test_positive_release_builds_and_deploys_nothing(self):
        out = self.out()
        rc, so, se = run_main(["release", "--repo", self.repo, "--head", self.head, "--gates", gates_file(gates_for(self.head)),
                               "--out", out, "--data-repo", H.DATA_REPO], self.env)
        self.assertEqual((rc, se), (0, ""))
        self.assertTrue(so.startswith(f"GUARD OK: build for {self.head}"))
        self.assertIn("Nothing was deployed", so)
        self.assertNotIn(FAKE_SECRET, so)
        for rel in ("nj/history/index.html", "data/nj/nj-district-staff-history.csv", "data/nj/nj-history-coverage.csv"):
            self.assertTrue(os.path.exists(os.path.join(out, *rel.split("/"))), rel)
        status = subprocess.run(["git", "-C", self.repo, "status", "--porcelain"], capture_output=True, text=True).stdout
        self.assertEqual(status, "")  # the 4.7 MB CSV is generated outside the repo, never tracked

    def test_release_succeeds_when_working_tree_already_has_history_pages(self):
        built = H.built()[0]
        files = {}
        for rel in ("nj/history/index.html", "data/nj/nj-history-coverage.csv"):
            files[rel] = H.rt(os.path.join(built, *rel.split("/")))
        page = sorted(n for n in os.listdir(os.path.join(built, "nj")) if n != "history")[0]
        files[f"nj/{page}/index.html"] = H.rt(os.path.join(built, "nj", page, "index.html"))
        repo, head = mkrepo(tree=H.site_tree(), files=files)
        out = self.out()
        rc, so, se = run_main(["release", "--repo", repo, "--head", head, "--gates", gates_file(gates_for(head)),
                               "--out", out, "--data-repo", H.DATA_REPO], self.env)
        self.assertEqual((rc, se), (0, ""), so)
        self.assertTrue(os.path.exists(os.path.join(out, "nj", "history", "index.html")))

    def test_base_commit_constant_matches_ci_and_helpers(self):
        self.assertEqual(G.SITE_BASE_COMMIT, H.BASE_COMMIT)
        self.assertIn(G.SITE_BASE_COMMIT, H.rt(os.path.join(H.ROOT, ".github", "workflows", "ci.yml")))

    def test_archive_failure_is_a_guard_error(self):
        d = H.tmpdir("k12nj-guard-")
        with self.assertRaises(G.GuardError) as cm:
            G.extract_base(os.path.join(d, "not-a-repo"), d)
        self.assertIn("git archive", str(cm.exception))

    def test_gates_from_env_json_are_accepted_and_checked(self):
        env = dict(self.env, K12_RELEASE_GATES=json.dumps(gates_for("f" * 40)))
        rc, so, se = run_main(["release", "--repo", self.repo, "--head", self.head, "--out", self.out(), "--data-repo", H.DATA_REPO], env)
        self.assertEqual(rc, 1)
        self.assertIn("exact head", se)

    def test_preflight_cli(self):
        rc, so, se = run_main(["preflight", "--repo", self.repo, "--data-repo", H.DATA_REPO], self.env)
        self.assertEqual((rc, so.strip()), (0, "PREFLIGHT OK"))
        rc, so, se = run_main(["preflight", "--repo", self.repo, "--data-repo", H.DATA_REPO], {"CI": "true"})
        self.assertEqual(rc, 1)
        self.assertIn("K12_DATA_READ_TOKEN", se)


class Workflows(unittest.TestCase):
    def test_workflows_fail_closed_and_never_deploy(self):
        for name in ("ci.yml", "release-build.yml"):
            y = H.rt(os.path.join(H.ROOT, ".github", "workflows", name))
            self.assertIn("K12_DATA_READ_TOKEN", y)
            self.assertIn("exit 1", y)
            self.assertIn("is not set", y)
            for word in ("wrangler", "pages-deploy", "gh-pages", "rsync", "scp ", "git push", "cloudflare", "deploy-pages"):
                self.assertNotIn(word, y.lower(), (name, word))
            self.assertIn("mv k12comp-data", y)  # the data clone must not sit inside the tree that is copied to the output
        rel = H.rt(os.path.join(H.ROOT, ".github", "workflows", "release-build.yml"))
        self.assertIn("K12_RELEASE_GATES", rel)
        self.assertIn("release --head", rel)
        self.assertIn("-W error::ResourceWarning", H.rt(os.path.join(H.ROOT, ".github", "workflows", "ci.yml")))


if __name__ == "__main__":
    unittest.main()
