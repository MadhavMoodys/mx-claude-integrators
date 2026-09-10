"""An entity change without a migration is the failure that only shows up on the
next environment: it works locally against a schema Hibernate already grew, and
breaks on deploy where Flyway is the only thing that touches the database.

These tests drive a real git repository because the check is "is there a migration
in the working tree", which is a question only git can answer.
"""

import os
import shutil
import subprocess
import tempfile
import unittest

from hookrunner import run_hook, write_event

ENTITY_SOURCE = """\
package com.moodys.maxsight.acme.connector.entity;

@Entity
@Table(name = "inbox_message")
public class InboxMessage {

    @Id
    private Long id;
}
"""

MIGRATION_DIR = "acme-connector/src/main/resources/db/migration"


def git(root, *args):
    subprocess.run(
        ["git"] + list(args), cwd=root,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True,
    )


class GuardMigrationTest(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        git(self.root, "init", "-q")
        git(self.root, "config", "user.email", "test@example.com")
        git(self.root, "config", "user.name", "test")
        self.entity_path = self.write_file(
            "acme-connector/src/main/java/com/moodys/entity/InboxMessage.java",
            ENTITY_SOURCE,
        )
        self.write_file("%s/V1__initial_schema.sql" % MIGRATION_DIR, "create table inbox_message ();\n")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "initial")

    def write_file(self, relative, text):
        path = os.path.join(self.root, relative)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as handle:
            handle.write(text)
        return path

    def edit_entity(self, new_string):
        return write_event(
            "Edit",
            {"file_path": self.entity_path, "old_string": "x", "new_string": new_string},
            cwd=self.root,
        )

    def run_guard(self, event):
        return run_hook("guard_migration.py", event)

    def assertAllowed(self, event):
        result = self.run_guard(event)
        self.assertEqual(0, result.code, "expected allow, got %r" % (result,))

    def assertBlocked(self, event, because=None):
        result = self.run_guard(event)
        self.assertEqual(2, result.code, "expected block, got %r" % (result,))
        if because:
            self.assertIn(because, result.stderr)
        return result

    # Schema-affecting changes require a migration.

    def test_blocks_added_column_without_a_migration(self):
        self.assertBlocked(
            self.edit_entity("    @Column(name = \"received_at\")\n    private Instant receivedAt;\n"),
            because="db/migration",
        )

    def test_blocks_added_field_without_a_migration(self):
        self.assertBlocked(self.edit_entity("    private String correlationId;\n"))

    def test_blocks_added_relationship_without_a_migration(self):
        self.assertBlocked(
            self.edit_entity("    @ManyToOne\n    private Subscription subscription;\n")
        )

    def test_names_the_next_free_migration_version(self):
        result = self.assertBlocked(self.edit_entity("    private String correlationId;\n"))
        self.assertIn("V2__", result.stderr)

    # An accompanying migration satisfies it.

    def test_allows_when_a_new_migration_is_untracked(self):
        self.write_file("%s/V2__add_correlation_id.sql" % MIGRATION_DIR,
                        "alter table inbox_message add column correlation_id varchar(64);\n")
        self.assertAllowed(self.edit_entity("    private String correlationId;\n"))

    def test_allows_when_an_existing_migration_is_modified(self):
        self.write_file("%s/V1__initial_schema.sql" % MIGRATION_DIR,
                        "create table inbox_message (correlation_id varchar(64));\n")
        self.assertAllowed(self.edit_entity("    private String correlationId;\n"))

    def test_allows_when_the_migration_is_staged(self):
        self.write_file("%s/V2__add_correlation_id.sql" % MIGRATION_DIR, "alter table inbox_message;\n")
        git(self.root, "add", "-A")
        self.assertAllowed(self.edit_entity("    private String correlationId;\n"))

    # Changes that cannot affect the schema.

    def test_allows_a_javadoc_change_to_an_entity(self):
        self.assertAllowed(self.edit_entity("    /** The message as received from the vendor. */\n"))

    def test_allows_a_method_body_change_to_an_entity(self):
        self.assertAllowed(
            self.edit_entity("    public String describe() {\n        return \"inbox \" + id;\n    }\n")
        )

    def test_allows_a_transient_field(self):
        # @Transient is the annotation that says "this one is not persisted".
        self.assertAllowed(
            self.edit_entity("    @Transient\n    private String scratch;\n")
        )

    def test_allows_a_field_on_a_non_entity_class(self):
        path = self.write_file(
            "acme-api/src/main/java/com/moodys/dto/AcmeResponse.java",
            "public class AcmeResponse {\n}\n",
        )
        self.assertAllowed(write_event(
            "Edit", {"file_path": path, "old_string": "x", "new_string": "    private String id;\n"},
            cwd=self.root,
        ))

    def test_allows_non_java_files(self):
        path = os.path.join(self.root, "README.md")
        self.assertAllowed(write_event(
            "Write", {"file_path": path, "content": "@Entity private String id;\n"}, cwd=self.root,
        ))

    # Detection sources.

    def test_detects_an_entity_from_the_incoming_content(self):
        # A brand new entity file is not on disk yet, so the annotation can only
        # come from the content being written.
        path = os.path.join(self.root, "acme-connector/src/main/java/com/moodys/entity/Outbox.java")
        self.assertBlocked(write_event(
            "Write", {"file_path": path, "content": ENTITY_SOURCE}, cwd=self.root,
        ))

    def test_detects_an_entity_from_the_file_on_disk(self):
        # The Edit fragment carries no @Entity annotation; only the file does.
        self.assertBlocked(self.edit_entity("    private String correlationId;\n"))

    def test_kill_switch_bypasses(self):
        result = run_hook(
            "guard_migration.py",
            self.edit_entity("    private String correlationId;\n"),
            env={"MX_HOOKS_DISABLED": "1"},
        )
        self.assertEqual(0, result.code)


class OutsideAGitRepoTest(unittest.TestCase):
    """Without git there is no way to tell whether a migration was added, and a
    guard that cannot judge must not block."""

    def test_allows_when_the_tree_is_not_a_git_repo(self):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, True)
        path = os.path.join(root, "InboxMessage.java")
        with open(path, "w") as handle:
            handle.write(ENTITY_SOURCE)
        result = run_hook("guard_migration.py", write_event(
            "Edit", {"file_path": path, "old_string": "x", "new_string": "    private String id;\n"},
            cwd=root,
        ))
        self.assertEqual(0, result.code, result)


if __name__ == "__main__":
    unittest.main()
