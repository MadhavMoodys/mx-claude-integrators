"""The architectural rules are the ones a compiler cannot state: field injection
compiles fine and only hurts when someone tries to construct the class in a test,
and a JPA entity returned from a controller compiles fine and only hurts once the
persistence model becomes the public API."""

import os
import shutil
import tempfile
import unittest

from hookrunner import run_hook, write_event

CONTROLLER = "/repo/src/main/java/com/moodys/maxsight/acme/controller/AcmeController.java"
SERVICE = "/repo/src/main/java/com/moodys/maxsight/acme/service/AcmeClient.java"


def write(path, content, **extra):
    return write_event("Write", {"file_path": path, "content": content}, **extra)


def edit(path, new_string, **extra):
    return write_event(
        "Edit", {"file_path": path, "old_string": "x", "new_string": new_string}, **extra
    )


class GuardArchitectureTest(unittest.TestCase):

    def assertAllowed(self, event):
        result = run_hook("guard_architecture.py", event)
        self.assertEqual(0, result.code, "expected allow, got %r" % (result,))

    def assertBlocked(self, event, because=None):
        result = run_hook("guard_architecture.py", event)
        self.assertEqual(2, result.code, "expected block, got %r" % (result,))
        if because:
            self.assertIn(because, result.stderr)

    # Field injection.

    def test_blocks_autowired_field_in_controller(self):
        self.assertBlocked(
            edit(CONTROLLER, "    @Autowired\n    private AcmeClient client;\n"),
            because="constructor injection",
        )

    def test_blocks_autowired_field_with_annotation_between(self):
        self.assertBlocked(
            edit(CONTROLLER, "    @Autowired\n    @Qualifier(\"primary\")\n    private AcmeClient client;\n")
        )

    def test_allows_autowired_constructor_in_controller(self):
        self.assertAllowed(
            edit(CONTROLLER, "    @Autowired\n    public AcmeController(AcmeClient client) {\n        this.client = client;\n    }\n")
        )

    def test_allows_autowired_setter_in_controller(self):
        self.assertAllowed(
            edit(CONTROLLER, "    @Autowired\n    public void setClient(AcmeClient client) {\n        this.client = client;\n    }\n")
        )

    def test_allows_constructor_injected_final_field(self):
        self.assertAllowed(edit(CONTROLLER, "    private final AcmeClient client;\n"))

    def test_allows_autowired_field_outside_a_controller(self):
        # Scoped to controllers deliberately: widening it is a separate decision.
        self.assertAllowed(edit(SERVICE, "    @Autowired\n    private AcmeClient client;\n"))

    def test_recognises_controller_by_filename_outside_a_controller_package(self):
        self.assertBlocked(
            edit("/repo/src/main/java/com/moodys/HealthController.java",
                 "    @Autowired\n    private HealthService service;\n")
        )

    # Wildcard imports.

    def test_blocks_wildcard_import_in_main(self):
        self.assertBlocked(edit(SERVICE, "import java.util.*;\n"), because="java.util.*")

    def test_blocks_wildcard_import_in_a_controller(self):
        self.assertBlocked(edit(CONTROLLER, "import java.util.*;\n"))

    def test_allows_explicit_import(self):
        self.assertAllowed(edit(SERVICE, "import java.util.List;\n"))

    def test_allows_static_wildcard_import_in_tests(self):
        # Mockito and AssertJ are used this way by convention; blocking it is how
        # a hook gets switched off.
        self.assertAllowed(
            edit("/repo/src/test/java/com/moodys/AcmeClientTest.java",
                 "import static org.mockito.Mockito.*;\n")
        )

    def test_blocks_non_static_wildcard_import_in_tests(self):
        self.assertBlocked(
            edit("/repo/src/test/java/com/moodys/AcmeClientTest.java", "import java.util.*;\n")
        )

    def test_ignores_non_java_files(self):
        self.assertAllowed(write("/repo/README.md", "import java.util.*;\n"))

    def test_kill_switch_bypasses(self):
        result = run_hook(
            "guard_architecture.py",
            edit(CONTROLLER, "    @Autowired\n    private AcmeClient client;\n"),
            env={"MX_HOOKS_DISABLED": "1"},
        )
        self.assertEqual(0, result.code)


class RawEntityExposureTest(unittest.TestCase):
    """Entity names are read off the repo rather than guessed from package names,
    so a repo with no @Entity classes -- which is every -api module -- cannot
    produce a false positive here."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.root, ".git"))
        self.addCleanup(shutil.rmtree, self.root, True)

    def source(self, relative, text):
        path = os.path.join(self.root, relative)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as handle:
            handle.write(text)
        return path

    def entity(self, name):
        self.source(
            "acme-connector/src/main/java/com/moodys/entity/%s.java" % name,
            "@Entity\npublic class %s {\n    private Long id;\n}\n" % name,
        )

    def controller_edit(self, body):
        path = os.path.join(
            self.root, "acme-api/src/main/java/com/moodys/controller/AcmeController.java"
        )
        os.makedirs(os.path.dirname(path), exist_ok=True)
        return edit(path, body, cwd=self.root)

    def test_blocks_entity_as_a_controller_return_type(self):
        self.entity("InboxMessage")
        result = run_hook(
            "guard_architecture.py",
            self.controller_edit("    public InboxMessage get(String id) {\n        return repo.find(id);\n    }\n"),
        )
        self.assertEqual(2, result.code, result)
        self.assertIn("InboxMessage", result.stderr)

    def test_blocks_entity_nested_in_a_generic_return_type(self):
        self.entity("InboxMessage")
        result = run_hook(
            "guard_architecture.py",
            self.controller_edit("    public ResponseEntity<List<InboxMessage>> list() {\n        return null;\n    }\n"),
        )
        self.assertEqual(2, result.code, result)

    def test_blocks_entity_as_a_controller_parameter(self):
        self.entity("InboxMessage")
        result = run_hook(
            "guard_architecture.py",
            self.controller_edit("    public void save(InboxMessage message) {\n    }\n"),
        )
        self.assertEqual(2, result.code, result)

    def test_allows_a_dto_with_a_similar_name(self):
        self.entity("InboxMessage")
        result = run_hook(
            "guard_architecture.py",
            self.controller_edit("    public InboxMessageResponse get(String id) {\n        return null;\n    }\n"),
        )
        self.assertEqual(0, result.code, result)

    def test_allows_entity_use_in_a_private_helper(self):
        # Mapping an entity to a DTO inside the controller is legal; only the
        # exposed signature is the problem.
        self.entity("InboxMessage")
        result = run_hook(
            "guard_architecture.py",
            self.controller_edit("    private InboxMessageResponse toDto(InboxMessage message) {\n        return null;\n    }\n"),
        )
        self.assertEqual(0, result.code, result)

    def test_allows_any_type_when_the_repo_has_no_entities(self):
        result = run_hook(
            "guard_architecture.py",
            self.controller_edit("    public InboxMessage get(String id) {\n        return null;\n    }\n"),
        )
        self.assertEqual(0, result.code, result)


if __name__ == "__main__":
    unittest.main()
