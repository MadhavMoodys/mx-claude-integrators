#!/usr/bin/env python3
"""PreToolUse(Edit|Write|MultiEdit): keep secrets and build output out of git.

Two rules, both learned from how mx-newsedge is wired:

1. Credentials reach the code as `${ENV_VAR}` in application.yml and exist as
   literals only in parameters.yaml, as `$(Secret.NAME)` pipeline references.
   Anything else is a credential heading for version control.
2. target/, .env and *.jar are build or local artefacts. Writing them means the
   agent is editing generated output instead of its source.

Only the text being *added* is inspected, so an agent reading past an existing
line is never blocked by it.
"""

import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
import mxhook  # noqa: E402

SECRET_KEYS = r"(?:api[-_]?key|password|passwd|secret|token|client[-_]?secret|private[-_]?key)"

# YAML: `api-key: <value>` where value is not a ${...} placeholder.
YAML_SECRET_RE = re.compile(
    r"^\s*(?:-\s*)?(?P<key>%s)\s*:\s*(?P<value>.+?)\s*$" % SECRET_KEYS,
    re.IGNORECASE,
)

# Java: assigning a string literal to a secret-looking name.
JAVA_SECRET_RE = re.compile(
    r"(?P<key>%s)\w*\s*=\s*\"(?P<value>[^\"]{6,})\"" % SECRET_KEYS,
    re.IGNORECASE,
)

# Placeholders that are indirection, not secrets: Spring ${..}, pipeline $(..),
# Azure/GitHub $(( )) and {{ }} template tokens used by the scaffolder.
INDIRECTION_RE = re.compile(r"^[\"']?(?:\$\{[^}]+\}|\$\([^)]+\)|\{\{[^}]+\}\}|@!.+)[\"']?$")

BLOCKED_PATH_RULES = (
    (re.compile(r"(^|/)target/"), "target/ holds Maven build output; edit the source instead."),
    (re.compile(r"(^|/)\.env(\.|$)"), ".env files hold local credentials and must not be written by an agent."),
    (re.compile(r"\.jar$"), "*.jar is a build artefact, not source."),
    (re.compile(r"(^|/)\.git/"), ".git/ is repository internals; use git commands instead."),
)

SECRET_HELP = (
    "Credentials must not appear as literals.\n"
    "  application.yml -> api-key: ${VENDOR_API_KEY}\n"
    "  parameters.yaml -> VENDOR_API_KEY: \"$(Secret.VENDOR_API_KEY)\"\n"
    "  Java            -> inject via @ConfigurationProperties, never a string constant.\n"
    "If this value is genuinely a non-secret placeholder, put it under src/test/."
)


def is_indirection(value):
    return bool(INDIRECTION_RE.match(value.strip()))


def is_placeholder(value):
    """Obvious non-secrets: empty, a comment, or a documented dummy."""
    value = value.strip().strip("\"'")
    if not value or value.startswith("#"):
        return True
    return value.lower() in ("", "null", "~", "changeme", "todo", "placeholder", "none")


def check_path(path):
    for pattern, reason in BLOCKED_PATH_RULES:
        if pattern.search(path.replace(os.sep, "/")):
            raise mxhook.Block("Refusing to write %s\n  %s" % (path, reason))


def check_secrets(path, text):
    normalised = path.replace(os.sep, "/")

    # Test fixtures legitimately carry fake credentials -- blocking them would
    # push people to disable the hook, which costs more than it saves.
    if "/src/test/" in normalised or "/tests/" in normalised:
        return

    lower = normalised.lower()
    if lower.endswith((".yml", ".yaml", ".properties")):
        for line in text.splitlines():
            match = YAML_SECRET_RE.match(line)
            if not match:
                continue
            value = match.group("value")
            if is_indirection(value) or is_placeholder(value):
                continue
            raise mxhook.Block(
                "Literal secret in %s:\n  %s\n%s" % (path, line.strip(), SECRET_HELP)
            )

    if lower.endswith(".java"):
        for match in JAVA_SECRET_RE.finditer(text):
            value = match.group("value")
            if is_indirection(value) or is_placeholder(value):
                continue
            raise mxhook.Block(
                "Literal secret assigned in %s:\n  %s\n%s"
                % (path, match.group(0).strip(), SECRET_HELP)
            )


def handler(event):
    path = mxhook.file_path(event)
    if not path:
        return None
    check_path(path)
    check_secrets(path, mxhook.edited_text(event))
    return None


if __name__ == "__main__":
    sys.exit(mxhook.main(handler))
