import unittest

from hookrunner import run_hook, write_event


def write(path, content):
    return write_event("Write", {"file_path": path, "content": content})


def edit(path, new_string):
    return write_event("Edit", {"file_path": path, "old_string": "x", "new_string": new_string})


class GuardWriteTest(unittest.TestCase):

    def assertAllowed(self, event):
        result = run_hook("guard_write.py", event)
        self.assertEqual(0, result.code, "expected allow, got %r" % (result,))

    def assertBlocked(self, event, because=None):
        result = run_hook("guard_write.py", event)
        self.assertEqual(2, result.code, "expected block, got %r" % (result,))
        if because:
            self.assertIn(because, result.stderr)

    def test_allows_env_var_indirection(self):
        self.assertAllowed(write("/repo/src/main/resources/application.yml",
                                 "newsedge:\n  api-key: ${NEWSEDGE_API_KEY}\n"))

    def test_allows_defaulted_env_var(self):
        self.assertAllowed(write("/repo/application.yml",
                                 "  password: ${NEWSEDGE_PASSWORD:changeme}\n"))

    def test_blocks_literal_api_key_in_yaml(self):
        self.assertBlocked(write("/repo/application.yml", '  api-key: "abc123"\n'),
                           because="api-key")

    def test_blocks_literal_password_in_yaml(self):
        self.assertBlocked(write("/repo/application.yml", "  password: hunter2\n"))

    def test_blocks_literal_token_in_yaml(self):
        self.assertBlocked(write("/repo/application.yml", "  token: ey.JhbGciOi\n"))

    def test_blocks_literal_secret_in_java(self):
        self.assertBlocked(edit("/repo/src/main/java/Foo.java",
                                'private static final String API_KEY = "sk-live-123456789";'))

    def test_allows_java_reference_to_config(self):
        self.assertAllowed(edit("/repo/src/main/java/Foo.java",
                                'header("X-API-Key", config.getApiKey())'))

    def test_allows_spring_placeholder_in_java(self):
        self.assertAllowed(edit("/repo/src/main/java/Foo.java",
                                '@Value("${NEWSEDGE_API_KEY}") private String apiKey;'))

    def test_allows_parameters_yaml_pipeline_secret(self):
        self.assertAllowed(write("/repo/parameters.yaml",
                                 '      NEWSEDGE_API_KEY: "$(Secret.NEWSEDGE_API_KEY)"\n'))

    def test_blocks_write_to_target_dir(self):
        self.assertBlocked(write("/repo/newsedge-api/target/classes/App.class", "x"),
                           because="target/")

    def test_blocks_write_to_env_file(self):
        self.assertBlocked(write("/repo/.env", "NEWSEDGE_API_KEY=abc"))

    def test_blocks_write_to_jar(self):
        self.assertBlocked(write("/repo/libs/thing.jar", "x"))

    def test_allows_ordinary_java(self):
        self.assertAllowed(edit("/repo/src/main/java/Foo.java", "int total = a + b;"))

    def test_allows_test_fixture_placeholder(self):
        self.assertAllowed(write("/repo/src/test/resources/application-test.yml",
                                 "  api-key: test-api-key\n"))

    def test_kill_switch_bypasses(self):
        result = run_hook("guard_write.py", write("/repo/.env", "K=v"),
                          env={"MX_HOOKS_DISABLED": "1"})
        self.assertEqual(0, result.code)


if __name__ == "__main__":
    unittest.main()
