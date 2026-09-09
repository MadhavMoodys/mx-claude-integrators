import json
import os
import shutil
import tempfile
import time
import unittest

from hookrunner import run_hook, write_event

FAKE_MVN = """#!/bin/sh
echo "$@" >> "$MX_MVN_LOG"
cat "$MX_MVN_OUT" 2>/dev/null
exit $(cat "$MX_MVN_CODE" 2>/dev/null || echo 0)
"""

VULN_OUTPUT = """[ERROR] Failed to execute goal org.owasp:dependency-check-maven:check
One or more dependencies were identified with vulnerabilities that have a CVSS score greater than or equal to '7.0':
netty-common-4.1.100.Final.jar: CVE-2024-29025(7.5)
"""


class VulnCheckTest(unittest.TestCase):

    def setUp(self):
        self.repo = tempfile.mkdtemp(prefix="mxvuln-")
        self.addCleanup(shutil.rmtree, self.repo, ignore_errors=True)
        os.makedirs(os.path.join(self.repo, ".git"))
        self.state = os.path.join(self.repo, "state")
        os.makedirs(self.state)

        self.bin_dir = os.path.join(self.repo, "fakebin")
        os.makedirs(self.bin_dir)
        mvn = os.path.join(self.bin_dir, "mvn")
        self.write(mvn, FAKE_MVN)
        os.chmod(mvn, 0o755)

        self.mvn_log = os.path.join(self.repo, "mvn.log")
        self.mvn_out = os.path.join(self.repo, "mvn.out")
        self.mvn_code = os.path.join(self.repo, "mvn.code")

        self.pom = os.path.join(self.repo, "pom.xml")
        self.write(self.pom, "<project><artifactId>acme</artifactId></project>")

    def write(self, path, text):
        with open(path, "w") as handle:
            handle.write(text)

    def env(self, **extra):
        base = {
            "PATH": self.bin_dir + os.pathsep + os.environ.get("PATH", ""),
            "MX_MVN_LOG": self.mvn_log,
            "MX_MVN_OUT": self.mvn_out,
            "MX_MVN_CODE": self.mvn_code,
            "MX_HOOK_STATE_DIR": self.state,
            "MX_VULN_SYNC_BUDGET": "60",
        }
        base.update(extra)
        return base

    def pom_event(self):
        return write_event("Edit", {"file_path": self.pom, "new_string": "<dependency/>"},
                           cwd=self.repo)

    def mvn_calls(self):
        if not os.path.exists(self.mvn_log):
            return []
        with open(self.mvn_log) as handle:
            return [line.strip() for line in handle if line.strip()]

    def test_runs_dependency_check_on_pom_edit(self):
        result = run_hook("vuln_check.py", self.pom_event(), env=self.env(), cwd=self.repo)
        self.assertEqual(0, result.code, result)
        calls = self.mvn_calls()
        self.assertEqual(1, len(calls), calls)
        self.assertIn("dependency-check", calls[0])
        self.assertIn("failBuildOnCVSS=7", calls[0])

    def test_blocks_on_high_severity_finding(self):
        self.write(self.mvn_out, VULN_OUTPUT)
        self.write(self.mvn_code, "1")
        result = run_hook("vuln_check.py", self.pom_event(), env=self.env(), cwd=self.repo)
        self.assertEqual(2, result.code, result)
        self.assertIn("CVE-2024-29025", result.stderr)

    def test_ignores_non_pom_files(self):
        event = write_event("Edit", {"file_path": os.path.join(self.repo, "Foo.java"),
                                     "new_string": "class Foo {}"}, cwd=self.repo)
        result = run_hook("vuln_check.py", event, env=self.env(), cwd=self.repo)
        self.assertEqual(0, result.code)
        self.assertEqual([], self.mvn_calls())

    def test_caches_clean_result_by_pom_hash(self):
        env = self.env()
        run_hook("vuln_check.py", self.pom_event(), env=env, cwd=self.repo)
        run_hook("vuln_check.py", self.pom_event(), env=env, cwd=self.repo)
        self.assertEqual(1, len(self.mvn_calls()), self.mvn_calls())

    def test_changed_pom_invalidates_cache(self):
        env = self.env()
        run_hook("vuln_check.py", self.pom_event(), env=env, cwd=self.repo)
        self.write(self.pom, "<project><artifactId>acme</artifactId><dependencies/></project>")
        run_hook("vuln_check.py", self.pom_event(), env=env, cwd=self.repo)
        self.assertEqual(2, len(self.mvn_calls()), self.mvn_calls())

    def test_expired_cache_reruns(self):
        env = self.env()
        run_hook("vuln_check.py", self.pom_event(), env=env, cwd=self.repo)
        cache_path = os.path.join(self.state, "vuln_cache.json")
        with open(cache_path) as handle:
            cache = json.load(handle)
        for entry in cache.values():
            entry["at"] = time.time() - (25 * 3600)
        with open(cache_path, "w") as handle:
            json.dump(cache, handle)
        run_hook("vuln_check.py", self.pom_event(), env=env, cwd=self.repo)
        self.assertEqual(2, len(self.mvn_calls()), self.mvn_calls())

    def test_nvd_sync_reports_instead_of_blocking(self):
        self.write(self.mvn_out, "Download started: NVD CVE ... updating the NVD CVE data")
        self.write(self.mvn_code, "1")
        env = self.env(MX_VULN_SYNC_BUDGET="0")
        result = run_hook("vuln_check.py", self.pom_event(), env=env, cwd=self.repo)
        self.assertEqual(0, result.code, result)
        self.assertIn("JFrog", result.stdout)

    def test_does_not_cache_a_sync_result(self):
        self.write(self.mvn_out, "updating the NVD CVE data")
        self.write(self.mvn_code, "1")
        env = self.env(MX_VULN_SYNC_BUDGET="0")
        run_hook("vuln_check.py", self.pom_event(), env=env, cwd=self.repo)
        run_hook("vuln_check.py", self.pom_event(), env=env, cwd=self.repo)
        self.assertEqual(2, len(self.mvn_calls()), self.mvn_calls())

    def test_missing_maven_does_not_block(self):
        env = self.env(PATH="/nonexistent")
        result = run_hook("vuln_check.py", self.pom_event(), env=env, cwd=self.repo)
        self.assertNotEqual(2, result.code, result)

    def test_kill_switch_bypasses(self):
        env = self.env(MX_HOOKS_DISABLED="1")
        result = run_hook("vuln_check.py", self.pom_event(), env=env, cwd=self.repo)
        self.assertEqual(0, result.code)
        self.assertEqual([], self.mvn_calls())


if __name__ == "__main__":
    unittest.main()
