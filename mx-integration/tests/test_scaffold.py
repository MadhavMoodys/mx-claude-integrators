"""Unit tests for scripts/scaffold.py.

The end-to-end gate (generate, then `mvn test-compile`) lives in the plan's
verification steps because it needs Maven and a warm ~/.m2. These tests cover the
parts that decide *what* gets written, which is where a silent mistake would ship a
repo that compiles but is wrong -- a dropped connector tree, a half-substituted
package name, an overwritten file.
"""

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))

import scaffold  # noqa: E402


class ParseSpecTest(unittest.TestCase):

    def test_reads_scalars_comments_and_blanks(self):
        spec = scaffold.parse_spec(
            "# leading comment\n"
            "vendor: acme\n"
            "\n"
            'display_name: "Acme Corp"   # trailing comment\n'
        )
        self.assertEqual({"vendor": "acme", "display_name": "Acme Corp"}, spec)

    def test_coerces_booleans(self):
        spec = scaffold.parse_spec("connector: true\nverbose: no\n")
        self.assertIs(True, spec["connector"])
        self.assertIs(False, spec["verbose"])

    def test_reads_lists(self):
        spec = scaffold.parse_spec("endpoints:\n  - /search\n  - /entities\n")
        self.assertEqual(["/search", "/entities"], spec["endpoints"])

    def test_rejects_a_list_item_with_no_key(self):
        with self.assertRaises(scaffold.SpecError):
            scaffold.parse_spec("  - orphan\n")

    def test_rejects_a_line_that_is_not_a_pair(self):
        with self.assertRaises(scaffold.SpecError):
            scaffold.parse_spec("vendor acme\n")


class BuildContextTest(unittest.TestCase):

    def test_derives_the_three_cases(self):
        context = scaffold.build_context({"vendor": "acme", "display_name": "Acme", "ticket": "M3PDS-1"})
        self.assertEqual("acme", context["tokens"]["{{vendor}}"])
        self.assertEqual("Acme", context["tokens"]["{{Vendor}}"])
        self.assertEqual("ACME", context["tokens"]["{{VENDOR}}"])
        self.assertEqual("M3PDS-1", context["tokens"]["TICKET-000"])

    def test_display_name_defaults_to_the_capitalised_vendor(self):
        context = scaffold.build_context({"vendor": "acme", "ticket": "M3PDS-1"})
        self.assertEqual("Acme", context["tokens"]["{{Vendor}}"])

    def test_rejects_a_vendor_that_is_not_a_java_package_segment(self):
        for bad in ("Acme", "acme-corp", "acme_corp", "1acme", ""):
            with self.subTest(vendor=bad), self.assertRaises(scaffold.SpecError):
                scaffold.build_context({"vendor": bad, "ticket": "M3PDS-1"})

    def test_rejects_a_ticket_the_commit_hook_would_reject(self):
        for bad in ("m3pds-1", "M3PDS", "M3PDS-", "fix stuff"):
            with self.subTest(ticket=bad), self.assertRaises(scaffold.SpecError):
                scaffold.build_context({"vendor": "acme", "ticket": bad})

    def test_connector_defaults_to_false(self):
        self.assertFalse(scaffold.build_context({"vendor": "acme"})["flags"]["connector"])


class ApplyBlocksTest(unittest.TestCase):

    def render(self, text, **flags):
        return scaffold.apply_blocks(text, flags)

    def test_keeps_the_body_and_drops_the_markers(self):
        out = self.render("a\n{{#connector}}\nb\n{{/connector}}\nc\n", connector=True)
        self.assertEqual("a\nb\nc\n", out)

    def test_drops_the_body_when_the_flag_is_off(self):
        out = self.render("a\n{{#connector}}\nb\n{{/connector}}\nc\n", connector=False)
        self.assertEqual("a\nc\n", out)

    def test_a_nested_block_stays_dropped_inside_a_dropped_one(self):
        text = "{{#connector}}\nouter\n{{#extra}}\ninner\n{{/extra}}\n{{/connector}}\n"
        self.assertEqual("", self.render(text, connector=False, extra=True))
        self.assertEqual("outer\ninner\n", self.render(text, connector=True, extra=True))

    def test_rejects_an_unknown_flag(self):
        with self.assertRaises(scaffold.SpecError):
            self.render("{{#nosuchflag}}\nx\n{{/nosuchflag}}\n", connector=True)

    def test_rejects_an_unclosed_block(self):
        with self.assertRaises(scaffold.SpecError):
            self.render("{{#connector}}\nx\n", connector=True)

    def test_rejects_a_close_with_no_open(self):
        with self.assertRaises(scaffold.SpecError):
            self.render("x\n{{/connector}}\n", connector=True)

    def test_ignores_a_marker_that_is_not_alone_on_its_line(self):
        # Whole-line markers only. An inline one is left for substitution to handle,
        # which is what surfaced the README table-row bug.
        text = "{{#connector}}| row |\n"
        self.assertEqual(text, self.render(text, connector=False))


class RenderPathTest(unittest.TestCase):

    def setUp(self):
        self.tokens = scaffold.build_context({"vendor": "acme", "ticket": "M3PDS-1"})["tokens"]

    def test_substitutes_every_segment(self):
        rendered = scaffold.render_path(
            Path("{{vendor}}-api/src/main/java/com/moodys/maxsight/{{vendor}}/{{Vendor}}Client.java"),
            self.tokens,
        )
        self.assertEqual(
            Path("acme-api/src/main/java/com/moodys/maxsight/acme/AcmeClient.java"), rendered
        )

    def test_renames_gitignore_on_the_way_out(self):
        self.assertEqual(Path(".gitignore"), scaffold.render_path(Path("gitignore"), self.tokens))


class ShouldSkipTest(unittest.TestCase):

    def test_drops_the_connector_tree_when_not_requested(self):
        path = Path("{{vendor}}-connector/pom.xml")
        self.assertTrue(scaffold.should_skip(path, {"connector": False}))
        self.assertFalse(scaffold.should_skip(path, {"connector": True}))

    def test_keeps_the_api_tree_either_way(self):
        path = Path("{{vendor}}-api/pom.xml")
        self.assertFalse(scaffold.should_skip(path, {"connector": False}))


class GenerateTest(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.templates = self.tmp / "templates"
        self.out = self.tmp / "out"
        (self.templates / "{{vendor}}-api").mkdir(parents=True)
        (self.templates / "{{vendor}}-connector").mkdir(parents=True)
        (self.templates / "{{vendor}}-api" / "{{Vendor}}Client.java").write_text(
            "package com.moodys.maxsight.{{vendor}};\n"
            "// TODO(TICKET-000): fill in\n"
            "class {{Vendor}}Client {}\n"
        )
        (self.templates / "{{vendor}}-connector" / "pom.xml").write_text("<artifactId>{{vendor}}-connector</artifactId>\n")
        (self.templates / "gitignore").write_text("target/\n")

    def context(self, connector):
        return scaffold.build_context({"vendor": "acme", "ticket": "M3PDS-1", "connector": connector})

    def test_writes_substituted_content_and_paths(self):
        scaffold.generate(self.templates, self.out, self.context(False), force=False)
        client = self.out / "acme-api" / "AcmeClient.java"
        self.assertEqual(
            "package com.moodys.maxsight.acme;\n// TODO(M3PDS-1): fill in\nclass AcmeClient {}\n",
            client.read_text(),
        )
        self.assertTrue((self.out / ".gitignore").exists())
        self.assertFalse((self.out / "acme-connector").exists())

    def test_includes_the_connector_when_requested(self):
        scaffold.generate(self.templates, self.out, self.context(True), force=False)
        self.assertEqual(
            "<artifactId>acme-connector</artifactId>\n",
            (self.out / "acme-connector" / "pom.xml").read_text(),
        )

    def test_refuses_to_overwrite_without_force(self):
        scaffold.generate(self.templates, self.out, self.context(False), force=False)
        with self.assertRaises(scaffold.SpecError):
            scaffold.generate(self.templates, self.out, self.context(False), force=False)

    def test_force_rewrites_in_place(self):
        scaffold.generate(self.templates, self.out, self.context(False), force=False)
        client = self.out / "acme-api" / "AcmeClient.java"
        client.write_text("hand edited\n")
        scaffold.generate(self.templates, self.out, self.context(False), force=True)
        self.assertIn("class AcmeClient", client.read_text())

    def test_names_the_file_when_a_template_has_a_bad_marker(self):
        (self.templates / "broken.md").write_text("{{/connector}}\n")
        with self.assertRaises(scaffold.SpecError) as caught:
            scaffold.generate(self.templates, self.out, self.context(True), force=False)
        self.assertIn("broken.md", str(caught.exception))


class MainTest(unittest.TestCase):

    def test_copies_the_spec_into_the_generated_repo(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        spec = tmp / "integration.yaml"
        spec.write_text("vendor: acme\nticket: M3PDS-1\nconnector: false\n")
        templates = tmp / "templates"
        templates.mkdir()
        (templates / "README.md").write_text("# mx-{{vendor}}\n")
        out = tmp / "out"

        code = scaffold.main(
            ["--spec", str(spec), "--out", str(out), "--templates", str(templates), "--skip-compile"]
        )

        self.assertEqual(0, code)
        self.assertEqual("# mx-acme\n", (out / "README.md").read_text())
        self.assertEqual(spec.read_text(), (out / "integration.yaml").read_text())

    def test_reports_a_bad_spec_without_a_traceback(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        spec = tmp / "integration.yaml"
        spec.write_text("vendor: Acme Corp\n")
        self.assertEqual(1, scaffold.main(["--spec", str(spec), "--out", str(tmp / "out"), "--skip-compile"]))


if __name__ == "__main__":
    unittest.main()
