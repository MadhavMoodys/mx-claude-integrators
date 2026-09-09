#!/usr/bin/env python3
"""PreToolUse(Bash): enforce the JIRA commit-message convention locally.

CI already rejects bad messages in .github/workflows/jira_validation.yml, but it
does so after the push. Failing here costs a retry instead of a round trip, and
the project-key regex is deliberately the same one CI uses so the two cannot
drift into disagreeing about what is valid.
"""

import os
import re
import shlex
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
import mxhook  # noqa: E402

# Matches jira_validation.yml's projectKeys: "[A-Z][A-Z0-9_]+"
MESSAGE_RE = re.compile(
    r"^\[(?P<key>[A-Z][A-Z0-9_]+-\d+)\]\s+"
    r"(?P<type>build|chore|ci|docs|feat|fix|perf|refactor|revert|style|test)"
    r"(?:\((?P<scope>[^)]+)\))?"
    r"!?: (?P<subject>.+)$"
)

MAX_SUBJECT = 72

EXAMPLE = '[M3PDS-123] feat(filters): add cyber subjects to the supply chain list'

HELP = (
    "Commit message must be: [PROJECT-123] type(scope): subject\n"
    "  example: " + EXAMPLE + "\n"
    "  type is one of build|chore|ci|docs|feat|fix|perf|refactor|revert|style|test\n"
    "  scope is optional; subject is at most %d characters\n"
    "This matches .github/workflows/jira_validation.yml, which will reject the push otherwise."
) % MAX_SUBJECT


def split_commands(command):
    """Split a shell line on &&, ||, ; and | so a chained `git commit` is seen.

    Naive on purpose: operators inside quotes would split wrongly, but the only
    consequence is a fragment that no longer looks like `git commit`, which we
    ignore. Guarding is best-effort; CI is the real gate.
    """
    return re.split(r"&&|\|\||;|(?<!\|)\|(?!\|)", command)


def commit_message(tokens):
    """Message passed via -m/--message, or None if the flag is absent."""
    for index, token in enumerate(tokens):
        if token in ("-m", "--message") and index + 1 < len(tokens):
            return tokens[index + 1]
        if token.startswith("--message="):
            return token.split("=", 1)[1]
        if token.startswith("-m") and len(token) > 2:
            return token[2:]
    return None


def is_git_commit(tokens):
    return len(tokens) >= 2 and os.path.basename(tokens[0]) == "git" and "commit" in tokens[1:3]


def check(command):
    for fragment in split_commands(command):
        fragment = fragment.strip()
        if not fragment:
            continue
        try:
            tokens = shlex.split(fragment)
        except ValueError:
            continue
        if not is_git_commit(tokens):
            continue

        # --amend --no-edit and -F/--file reuse a message this hook cannot see;
        # let them through rather than block on a message that may well be valid.
        if "--no-edit" in tokens or "-F" in tokens or "--file" in tokens:
            continue

        message = commit_message(tokens)
        if message is None:
            raise mxhook.Block(
                "git commit without -m opens an editor this session cannot drive.\n" + HELP
            )

        first_line = message.strip().splitlines()[0] if message.strip() else ""
        match = MESSAGE_RE.match(first_line)
        if not match:
            raise mxhook.Block("Rejected commit message: %r\n%s" % (first_line, HELP))
        if len(match.group("subject")) > MAX_SUBJECT:
            raise mxhook.Block(
                "Commit subject is %d characters; the limit is %d.\n%s"
                % (len(match.group("subject")), MAX_SUBJECT, HELP)
            )


def handler(event):
    command = mxhook.tool_input(event).get("command") or ""
    if "commit" in command:
        check(command)
    return None


if __name__ == "__main__":
    sys.exit(mxhook.main(handler))
