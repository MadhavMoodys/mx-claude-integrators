import os
import subprocess
import sys
import unittest

from hookrunner import HOOKS_DIR, run_hook, write_event


def edit(new_string, path="/repo/src/main/java/Foo.java"):
    return write_event("Edit", {"file_path": path, "old_string": "x", "new_string": new_string})


class CommentLintTest(unittest.TestCase):

    def assertAllowed(self, text):
        result = run_hook("comment_lint.py", edit(text))
        self.assertEqual(0, result.code, "expected allow for %r, got %r" % (text, result))

    def assertBlocked(self, text, because=None):
        result = run_hook("comment_lint.py", edit(text))
        self.assertEqual(2, result.code, "expected block for %r, got %r" % (text, result))
        if because:
            self.assertIn(because, result.stderr)

    # -- commented-out code -------------------------------------------------

    def test_blocks_commented_out_statement(self):
        self.assertBlocked("        // int total = a + b;", because="commented-out")

    def test_blocks_commented_out_method_call(self):
        self.assertBlocked("        // log.info(\"hi\");")

    def test_blocks_commented_out_annotation(self):
        self.assertBlocked("    // @Transactional")

    def test_blocks_commented_out_block_start(self):
        self.assertBlocked("        // if (x > 1) {")

    def test_allows_prose_about_code(self):
        self.assertAllowed("        // No @Transactional -- deliberately.")
        self.assertAllowed("        // REQUIRES_NEW: always its own independent transaction")
        self.assertAllowed("        // Prevent instantiation")
        self.assertAllowed("        // Check if token is null or expired")

    def test_allows_prose_ending_in_abbreviation(self):
        self.assertAllowed("        // Retry with backoff, e.g. 1s, 2s, 4s.")

    def test_allows_code_examples_inside_javadoc(self):
        self.assertAllowed(
            "/**\n"
            " * <p>Example JSON:\n"
            " * <pre>{@code\n"
            " * {\n"
            " *   \"input_version\": 1\n"
            " * }\n"
            " * }</pre>\n"
            " */"
        )

    def test_allows_arrange_act_assert_markers(self):
        result = run_hook("comment_lint.py",
                          edit("        // Assert\n        assertNotNull(result);"))
        self.assertEqual(0, result.code, result)
        self.assertNotIn("restate", result.stdout + result.stderr)

    # -- TODOs --------------------------------------------------------------

    def test_blocks_bare_todo(self):
        self.assertBlocked("        // TODO: fix later", because="TODO")

    def test_blocks_bare_fixme(self):
        self.assertBlocked("        // FIXME handle the 429 case")

    def test_allows_ticketed_todo(self):
        self.assertAllowed("        // TODO(M3PDS-123): map the vendor error body")

    # -- filler javadoc -----------------------------------------------------

    def test_blocks_tautological_param(self):
        self.assertBlocked("     * @param subscriptionId the subscriptionId", because="restates")

    def test_blocks_getter_comment(self):
        self.assertBlocked("    // Getter")
        self.assertBlocked("    // Setter for name")

    def test_allows_param_with_content(self):
        self.assertAllowed("     * @param expiresAt Token expiry time, never null")

    def test_allows_javadoc_prose(self):
        self.assertAllowed("     * Manages access tokens with automatic scheduled refresh.")

    # -- fuzzy redundancy is advisory only ----------------------------------

    def test_warns_but_allows_redundant_comment(self):
        text = "        // fetch and schedule refresh\n        fetchAndScheduleRefresh();"
        result = run_hook("comment_lint.py", edit(text))
        self.assertEqual(0, result.code, result)
        self.assertIn("restate", result.stdout + result.stderr)

    def test_does_not_warn_when_comment_adds_a_word(self):
        text = "        // Retry the fetchNewToken method\n        retry.executeSupplier(this::fetchNewToken);"
        result = run_hook("comment_lint.py", edit(text))
        self.assertEqual(0, result.code, result)
        self.assertNotIn("restate", result.stdout + result.stderr)

    # -- scope --------------------------------------------------------------

    def test_ignores_non_java(self):
        self.assertAllowed("# TODO: fix later")
        result = run_hook("comment_lint.py", edit("// TODO: fix later", path="/repo/notes.md"))
        self.assertEqual(0, result.code)

    def test_ignores_string_literals_containing_slashes(self):
        self.assertAllowed('        String url = "https://api.example.com/v1/news";')

    def test_allows_licence_and_url_comments(self):
        self.assertAllowed("        // See https://docs.example.com/api#rate-limits")

    def test_kill_switch_bypasses(self):
        result = run_hook("comment_lint.py", edit("// TODO: fix later"),
                          env={"MX_HOOKS_DISABLED": "1"})
        self.assertEqual(0, result.code)


class CommentLintCliTest(unittest.TestCase):
    """The --check mode used to sweep existing files for false positives."""

    def run_cli(self, *paths):
        return subprocess.run(
            [sys.executable, os.path.join(HOOKS_DIR, "comment_lint.py"), "--check"] + list(paths),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )

    def test_reports_findings_per_file(self):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".java", delete=False) as handle:
            handle.write("class A {\n    // TODO: later\n}\n")
            path = handle.name
        self.addCleanup(os.unlink, path)
        proc = self.run_cli(path)
        self.assertEqual(1, proc.returncode)
        self.assertIn("TODO", proc.stdout)
        self.assertIn(":2:", proc.stdout)

    def test_clean_file_exits_zero(self):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".java", delete=False) as handle:
            handle.write("class A {\n    // Prevent instantiation\n    private A() {}\n}\n")
            path = handle.name
        self.addCleanup(os.unlink, path)
        proc = self.run_cli(path)
        self.assertEqual(0, proc.returncode, proc.stdout)


if __name__ == "__main__":
    unittest.main()
