import json
import os
import shutil
import tempfile
import unittest

from hookrunner import run_hook, write_event

FAKE_MVN = """#!/bin/sh
echo "$@" >> "$MX_MVN_LOG"
if [ -f "$MX_MVN_FAIL" ]; then
  echo "[ERROR] /repo/Foo.java:[7,9] cannot find symbol"
  exit 1
fi
exit 0
"""


class CompileTouchedTest(unittest.TestCase):

    def setUp(self):
        self.repo = tempfile.mkdtemp(prefix="mxcompile-")
        self.addCleanup(shutil.rmtree, self.repo, ignore_errors=True)
        os.makedirs(os.path.join(self.repo, ".git"))
        self.module_dir = os.path.join(self.repo, "acme-api")
        os.makedirs(os.path.join(self.module_dir, "src", "main", "java"))
        self.write(os.path.join(self.module_dir, "pom.xml"), "<project/>")
        self.write(os.path.join(self.repo, "pom.xml"), "<project/>")

        self.bin_dir = os.path.join(self.repo, "fakebin")
        os.makedirs(self.bin_dir)
        mvn = os.path.join(self.bin_dir, "mvn")
        self.write(mvn, FAKE_MVN)
        os.chmod(mvn, 0o755)

        self.mvn_log = os.path.join(self.repo, "mvn.log")
        self.fail_marker = os.path.join(self.repo, "FAIL")
        self.state = os.path.join(self.repo, "state")

    def write(self, path, text):
        with open(path, "w") as handle:
            handle.write(text)

    def env(self):
        return {
            "PATH": self.bin_dir + os.pathsep + os.environ.get("PATH", ""),
            "MX_MVN_LOG": self.mvn_log,
            "MX_MVN_FAIL": self.fail_marker,
            "MX_HOOK_STATE_DIR": self.state,
        }

    def java_event(self, name="Foo.java"):
        path = os.path.join(self.module_dir, "src", "main", "java", name)
        self.write(path, "class Foo {}")
        return write_event("Edit", {"file_path": path, "new_string": "class Foo {}"},
                           cwd=self.repo)

    def mvn_calls(self):
        if not os.path.exists(self.mvn_log):
            return []
        with open(self.mvn_log) as handle:
            return [line.strip() for line in handle if line.strip()]

    def test_compiles_touched_module(self):
        result = run_hook("compile_touched.py", self.java_event(), env=self.env(), cwd=self.repo)
        self.assertEqual(0, result.code, result)
        calls = self.mvn_calls()
        self.assertEqual(1, len(calls), calls)
        self.assertIn("test-compile", calls[0])
        self.assertIn("-pl acme-api", calls[0])

    def test_blocks_on_compile_failure_with_output(self):
        self.write(self.fail_marker, "")
        result = run_hook("compile_touched.py", self.java_event(), env=self.env(), cwd=self.repo)
        self.assertEqual(2, result.code, result)
        self.assertIn("cannot find symbol", result.stderr)

    def test_ignores_non_java_files(self):
        event = write_event("Edit", {"file_path": os.path.join(self.repo, "README.md"),
                                     "new_string": "hi"}, cwd=self.repo)
        result = run_hook("compile_touched.py", event, env=self.env(), cwd=self.repo)
        self.assertEqual(0, result.code)
        self.assertEqual([], self.mvn_calls())

    def test_debounces_rapid_edits(self):
        env = self.env()
        run_hook("compile_touched.py", self.java_event("A.java"), env=env, cwd=self.repo)
        run_hook("compile_touched.py", self.java_event("B.java"), env=env, cwd=self.repo)
        self.assertEqual(1, len(self.mvn_calls()), self.mvn_calls())

    def test_records_module_for_stop_hook(self):
        run_hook("compile_touched.py", self.java_event(), env=self.env(), cwd=self.repo)
        with open(os.path.join(self.state, "touched.json")) as handle:
            self.assertIn("acme-api", json.load(handle))

    def test_missing_maven_does_not_block(self):
        env = self.env()
        env["PATH"] = "/nonexistent"
        result = run_hook("compile_touched.py", self.java_event(), env=env, cwd=self.repo)
        self.assertNotEqual(2, result.code, result)

    def test_kill_switch_bypasses(self):
        env = self.env()
        env["MX_HOOKS_DISABLED"] = "1"
        result = run_hook("compile_touched.py", self.java_event(), env=env, cwd=self.repo)
        self.assertEqual(0, result.code)
        self.assertEqual([], self.mvn_calls())


if __name__ == "__main__":
    unittest.main()
