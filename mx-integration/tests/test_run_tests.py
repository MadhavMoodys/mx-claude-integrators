import json
import os
import shutil
import tempfile
import unittest

from hookrunner import run_hook

FAKE_MVN = """#!/bin/sh
echo "$@" >> "$MX_MVN_LOG"
if [ -f "$MX_MVN_FAIL" ]; then
  echo "[ERROR] Failures: AcmeClientTest.mapsUnauthorized:41 expected:<401> but was:<500>"
  exit 1
fi
exit 0
"""


class RunTestsTest(unittest.TestCase):

    def setUp(self):
        self.repo = tempfile.mkdtemp(prefix="mxstop-")
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
        self.fail_marker = os.path.join(self.repo, "FAIL")

    def write(self, path, text):
        with open(path, "w") as handle:
            handle.write(text)

    def touched(self, modules):
        self.write(os.path.join(self.state, "touched.json"), json.dumps(modules))

    def env(self):
        return {
            "PATH": self.bin_dir + os.pathsep + os.environ.get("PATH", ""),
            "MX_MVN_LOG": self.mvn_log,
            "MX_MVN_FAIL": self.fail_marker,
            "MX_HOOK_STATE_DIR": self.state,
        }

    def event(self, **extra):
        payload = {"cwd": self.repo, "hook_event_name": "Stop"}
        payload.update(extra)
        return payload

    def mvn_calls(self):
        if not os.path.exists(self.mvn_log):
            return []
        with open(self.mvn_log) as handle:
            return [line.strip() for line in handle if line.strip()]

    def test_runs_tests_for_touched_modules(self):
        self.touched(["acme-api", "acme-connector"])
        result = run_hook("run_tests.py", self.event(), env=self.env(), cwd=self.repo)
        self.assertEqual(0, result.code, result)
        calls = self.mvn_calls()
        self.assertEqual(1, len(calls), calls)
        self.assertIn("test", calls[0])
        self.assertIn("acme-api,acme-connector", calls[0])

    def test_no_touched_modules_is_a_noop(self):
        result = run_hook("run_tests.py", self.event(), env=self.env(), cwd=self.repo)
        self.assertEqual(0, result.code)
        self.assertEqual([], self.mvn_calls())

    def test_blocks_when_tests_fail(self):
        self.touched(["acme-api"])
        self.write(self.fail_marker, "")
        result = run_hook("run_tests.py", self.event(), env=self.env(), cwd=self.repo)
        self.assertEqual(2, result.code, result)
        self.assertIn("expected:<401>", result.stderr)

    def test_clears_touched_modules_after_success(self):
        self.touched(["acme-api"])
        run_hook("run_tests.py", self.event(), env=self.env(), cwd=self.repo)
        with open(os.path.join(self.state, "touched.json")) as handle:
            self.assertEqual([], json.load(handle))

    def test_does_not_recurse_when_already_stopping(self):
        self.touched(["acme-api"])
        result = run_hook("run_tests.py", self.event(stop_hook_active=True),
                          env=self.env(), cwd=self.repo)
        self.assertEqual(0, result.code)
        self.assertEqual([], self.mvn_calls())

    def test_missing_maven_does_not_block(self):
        self.touched(["acme-api"])
        env = self.env()
        env["PATH"] = "/nonexistent"
        result = run_hook("run_tests.py", self.event(), env=env, cwd=self.repo)
        self.assertNotEqual(2, result.code, result)

    def test_kill_switch_bypasses(self):
        self.touched(["acme-api"])
        env = self.env()
        env["MX_HOOKS_DISABLED"] = "1"
        result = run_hook("run_tests.py", self.event(), env=env, cwd=self.repo)
        self.assertEqual(0, result.code)
        self.assertEqual([], self.mvn_calls())


if __name__ == "__main__":
    unittest.main()
