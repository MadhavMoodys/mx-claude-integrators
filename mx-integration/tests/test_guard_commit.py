import unittest

from hookrunner import run_hook, write_event


def commit(command):
    return write_event("Bash", {"command": command})


class GuardCommitTest(unittest.TestCase):

    def assertAllowed(self, command):
        result = run_hook("guard_commit.py", commit(command))
        self.assertEqual(0, result.code, "expected allow for %r, got %r" % (command, result))

    def assertBlocked(self, command, because=None):
        result = run_hook("guard_commit.py", commit(command))
        self.assertEqual(2, result.code, "expected block for %r, got %r" % (command, result))
        if because:
            self.assertIn(because, result.stderr)

    def test_accepts_repo_convention(self):
        self.assertAllowed('git commit -m "[M3PDS-971] feat(filters): add cyber subjects"')

    def test_accepts_fix_and_scopeless_types(self):
        self.assertAllowed('git commit -m "[M3PDS-1] fix(newsedge): reject loudly at shutdown"')
        self.assertAllowed('git commit -m "[ABC-12] chore: bump dependency"')

    def test_accepts_multiline_body(self):
        self.assertAllowed('git commit -m "[M3PDS-971] docs(readme): explain plugin install\n\nLonger body here."')

    def test_rejects_missing_ticket(self):
        self.assertBlocked('git commit -m "fix stuff"', because="M3PDS-123")

    def test_rejects_missing_conventional_type(self):
        self.assertBlocked('git commit -m "[M3PDS-971] add cyber subjects"')

    def test_rejects_lowercase_project_key(self):
        self.assertBlocked('git commit -m "[m3pds-971] feat(filters): add subjects"')

    def test_rejects_overlong_subject(self):
        long_subject = "x" * 73
        self.assertBlocked('git commit -m "[M3PDS-971] feat(a): %s"' % long_subject, because="72")

    def test_allows_non_commit_bash(self):
        self.assertAllowed("git status")
        self.assertAllowed("mvn -q test")

    def test_allows_amend_no_edit(self):
        self.assertAllowed("git commit --amend --no-edit")

    def test_blocks_commit_without_message_flag(self):
        self.assertBlocked("git commit", because="-m")

    def test_handles_single_quoted_message(self):
        self.assertAllowed("git commit -m '[M3PDS-971] feat(filters): add cyber subjects'")
        self.assertBlocked("git commit -m 'nope'")

    def test_finds_commit_after_chained_command(self):
        self.assertBlocked('git add -A && git commit -m "wip"')

    def test_kill_switch_bypasses(self):
        result = run_hook("guard_commit.py", commit('git commit -m "wip"'),
                          env={"MX_HOOKS_DISABLED": "1"})
        self.assertEqual(0, result.code)


if __name__ == "__main__":
    unittest.main()
