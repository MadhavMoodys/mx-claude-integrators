import os
import shutil
import subprocess
import tempfile
import unittest

from hookrunner import run_hook


class ContextTest(unittest.TestCase):

    def setUp(self):
        self.repo = tempfile.mkdtemp(prefix="mxctx-")
        self.addCleanup(shutil.rmtree, self.repo, ignore_errors=True)
        subprocess.run(["git", "init", "-q", "-b", "M3PDS-999"], cwd=self.repo, check=True)

    def module(self, name):
        path = os.path.join(self.repo, name)
        os.makedirs(os.path.join(path, "src", "main", "java"))
        self.write("%s/pom.xml" % name, "<project/>")

    def write(self, relative, text):
        with open(os.path.join(self.repo, relative), "w") as handle:
            handle.write(text)

    def run_context(self):
        return run_hook("context.py", {"cwd": self.repo, "hook_event_name": "SessionStart"},
                        cwd=self.repo)

    def test_reports_modules(self):
        self.module("acme-api")
        self.module("acme-connector")
        result = self.run_context()
        self.assertEqual(0, result.code, result)
        self.assertIn("acme-api", result.stdout)
        self.assertIn("acme-connector", result.stdout)

    def test_reports_branch_jira_key(self):
        result = self.run_context()
        self.assertIn("M3PDS-999", result.stdout)

    def test_includes_integration_spec_when_present(self):
        self.write("integration.yaml",
                   "vendor: acme\nbase_url: https://api.acme.test\nauth: api_key\n")
        result = self.run_context()
        self.assertIn("integration.yaml", result.stdout)
        self.assertIn("api.acme.test", result.stdout)

    def test_survives_repo_without_spec_or_modules(self):
        result = self.run_context()
        self.assertEqual(0, result.code, result)
        self.assertTrue(result.stdout.strip())

    def test_never_blocks(self):
        result = run_hook("context.py", {"cwd": "/nonexistent-path-xyz"})
        self.assertNotEqual(2, result.code, result)

    def test_kill_switch_bypasses(self):
        result = run_hook("context.py", {"cwd": self.repo}, env={"MX_HOOKS_DISABLED": "1"})
        self.assertEqual(0, result.code)
        self.assertEqual("", result.stdout.strip())


if __name__ == "__main__":
    unittest.main()
