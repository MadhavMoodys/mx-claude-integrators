"""The wiring is data, so nothing else catches a typo in it -- a hook named
wrongly in hooks.json simply never runs, silently."""

import json
import os
import re
import unittest

from hookrunner import HOOKS_DIR

PLUGIN_ROOT = os.path.dirname(HOOKS_DIR)
# The marketplace sits one level above the plugin: <repo>/.claude-plugin/marketplace.json
# alongside <repo>/mx-integration/. Counting levels is only safe because that layout is
# fixed by the relative `source` in marketplace.json.
REPO_ROOT = os.path.dirname(PLUGIN_ROOT)

COMMAND_RE = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/(?P<relative>[\w/.-]+)")

VALID_EVENTS = {
    "SessionStart", "SessionEnd", "UserPromptSubmit", "PreToolUse",
    "PostToolUse", "Notification", "Stop", "SubagentStop", "PreCompact",
}


def load(path):
    with open(path) as handle:
        return json.load(handle)


class ManifestTest(unittest.TestCase):

    def setUp(self):
        self.hooks = load(os.path.join(HOOKS_DIR, "hooks.json"))

    def entries(self):
        for event, matchers in self.hooks["hooks"].items():
            for matcher in matchers:
                for entry in matcher["hooks"]:
                    yield event, matcher, entry

    def test_plugin_json_is_valid(self):
        plugin = load(os.path.join(PLUGIN_ROOT, ".claude-plugin", "plugin.json"))
        self.assertEqual("mx-integration", plugin["name"])
        self.assertTrue(plugin["description"])
        self.assertTrue(plugin["version"])

    def test_marketplace_lists_this_plugin(self):
        marketplace = load(os.path.join(REPO_ROOT, ".claude-plugin", "marketplace.json"))
        names = [entry["name"] for entry in marketplace["plugins"]]
        self.assertIn("mx-integration", names)
        for entry in marketplace["plugins"]:
            source = os.path.join(REPO_ROOT, entry["source"])
            self.assertTrue(os.path.isdir(source), "missing plugin source %s" % source)

    def test_events_are_recognised(self):
        for event in self.hooks["hooks"]:
            self.assertIn(event, VALID_EVENTS)

    def test_every_referenced_hook_exists(self):
        for _, _, entry in self.entries():
            match = COMMAND_RE.search(entry["command"])
            self.assertIsNotNone(match, entry["command"])
            path = os.path.join(PLUGIN_ROOT, match.group("relative"))
            self.assertTrue(os.path.isfile(path), "missing hook %s" % path)

    def test_every_hook_has_a_timeout(self):
        for event, _, entry in self.entries():
            self.assertIsInstance(entry.get("timeout"), int, event)
            self.assertGreater(entry["timeout"], 0)

    def test_stop_timeout_exceeds_the_test_run_budget(self):
        # A Stop hook killed mid-`mvn test` reports nothing, which reads as a
        # pass. Its timeout must outlast the run it supervises.
        stop = [e for event, _, e in self.entries() if event == "Stop"]
        self.assertTrue(stop)
        for entry in stop:
            self.assertGreater(entry["timeout"], 900)

    def test_every_hook_file_is_wired(self):
        wired = set()
        for _, _, entry in self.entries():
            match = COMMAND_RE.search(entry["command"])
            wired.add(os.path.basename(match.group("relative")))
        on_disk = {
            name for name in os.listdir(HOOKS_DIR)
            if name.endswith(".py")
        }
        self.assertEqual(set(), on_disk - wired, "hook present but never registered")

    def test_pre_tool_use_matchers_cover_the_guarded_tools(self):
        matchers = {
            m.get("matcher") for event, m, _ in self.entries() if event == "PreToolUse"
        }
        self.assertIn("Bash", matchers)
        self.assertIn("Edit|Write|MultiEdit", matchers)


class SkillAndCommandTest(unittest.TestCase):
    """Frontmatter is what makes a skill discoverable. A missing or mismatched
    `name` leaves the file on disk and the skill absent from the session."""

    SKILLS_DIR = os.path.join(PLUGIN_ROOT, "skills")
    COMMANDS_DIR = os.path.join(PLUGIN_ROOT, "commands")

    def frontmatter(self, path):
        with open(path) as handle:
            text = handle.read()
        self.assertTrue(text.startswith("---\n"), "%s has no frontmatter" % path)
        block = text.split("---\n", 2)[1]
        fields = {}
        for line in block.splitlines():
            if ":" in line and not line.startswith(" "):
                key, _, value = line.partition(":")
                fields[key.strip()] = value.strip()
        return fields

    def test_every_skill_declares_a_matching_name_and_a_description(self):
        found = sorted(os.listdir(self.SKILLS_DIR))
        self.assertEqual(
            ["integration-release-checklist", "mx-integration-architecture", "new-vendor-integration"],
            found,
        )
        for skill in found:
            path = os.path.join(self.SKILLS_DIR, skill, "SKILL.md")
            self.assertTrue(os.path.isfile(path), path)
            fields = self.frontmatter(path)
            self.assertEqual(skill, fields.get("name"))
            self.assertTrue(fields.get("description"), path)

    def test_skill_references_exist(self):
        for skill in os.listdir(self.SKILLS_DIR):
            path = os.path.join(self.SKILLS_DIR, skill, "SKILL.md")
            with open(path) as handle:
                text = handle.read()
            for name in re.findall(r"`references/([\w.-]+\.md)`", text):
                target = os.path.join(self.SKILLS_DIR, skill, "references", name)
                self.assertTrue(os.path.isfile(target), "missing %s" % target)

    def test_commands_declare_a_description(self):
        commands = [n for n in os.listdir(self.COMMANDS_DIR) if n.endswith(".md")]
        self.assertIn("new-integration.md", commands)
        for name in commands:
            fields = self.frontmatter(os.path.join(self.COMMANDS_DIR, name))
            self.assertTrue(fields.get("description"), name)

    def test_plugin_root_is_used_for_script_paths(self):
        # A bare relative path resolves against the user's cwd, which is the vendor
        # repo, not the plugin -- it works in testing and breaks on install.
        for name in os.listdir(self.COMMANDS_DIR):
            with open(os.path.join(self.COMMANDS_DIR, name)) as handle:
                text = handle.read()
            if "scaffold.py" in text:
                self.assertIn("${CLAUDE_PLUGIN_ROOT}/scripts/scaffold.py", text)


if __name__ == "__main__":
    unittest.main()
