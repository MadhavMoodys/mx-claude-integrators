#!/usr/bin/env python3
"""SessionStart: tell the agent where it is before it starts guessing.

Emits the Maven module layout, the ticket key from the branch name, and the
integration spec if the repo has one. All of this is discoverable, but only
after several tool calls, and the ticket key in particular is needed by the very
first commit -- which is exactly when the agent has least context.

Output goes to stdout, which Claude Code injects as session context.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
import mxhook  # noqa: E402

SPEC_NAMES = ("integration.yaml", "integration.yml")

SPEC_EXCERPT_LINES = 40

ARCHITECTURE = """\
Integration shape (see the mx-integration-architecture skill for detail):
  <vendor>-api        Controller -> Client -> RestClient. Transformer is pure.
                      Credentials arrive as ${ENV_VAR}; literals belong in parameters.yaml.
                      HTTP status maps to typed exceptions: 401/403 auth, 400/422 validation,
                      429 rate limit, 5xx server, timeouts timeout.
  <vendor>-connector  Kafka -> inbox -> worker -> handler -> facade -> outbox -> Kafka.
                      5xx wraps in RetriableException (framework retries); 4xx rethrows.

Comment policy: comment the why, never the what. Javadoc public types and public
methods of controllers, clients, configs and services. TODOs carry a ticket key.
No commented-out code."""


def branch_name(root):
    head = os.path.join(root, ".git", "HEAD")
    try:
        with open(head) as handle:
            content = handle.read().strip()
    except OSError:
        return None
    if content.startswith("ref: refs/heads/"):
        return content[len("ref: refs/heads/"):]
    return None


def ticket_key(branch):
    if not branch:
        return None
    import re
    match = re.search(r"[A-Z][A-Z0-9_]+-\d+", branch)
    return match.group(0) if match else None


def modules(root):
    found = []
    try:
        entries = sorted(os.listdir(root))
    except OSError:
        return found
    for entry in entries:
        if entry.startswith("."):
            continue
        if os.path.isfile(os.path.join(root, entry, "pom.xml")):
            found.append(entry)
    return found


def spec_excerpt(root):
    for name in SPEC_NAMES:
        path = os.path.join(root, name)
        if not os.path.isfile(path):
            continue
        try:
            with open(path) as handle:
                lines = handle.read().splitlines()
        except OSError:
            return None
        body = "\n".join(lines[:SPEC_EXCERPT_LINES])
        if len(lines) > SPEC_EXCERPT_LINES:
            body += "\n  ...(%d more lines)" % (len(lines) - SPEC_EXCERPT_LINES)
        return "%s:\n%s" % (name, body)
    return None


def handler(event):
    root = mxhook.repo_root(mxhook.project_dir(event))
    sections = ["## mx-integration context", "Repo root: %s" % root]

    found = modules(root)
    if found:
        sections.append("Maven modules: %s" % ", ".join(found))

    key = ticket_key(branch_name(root))
    if key:
        sections.append(
            "Branch ticket: %s -- commit messages must start [%s]." % (key, key)
        )

    excerpt = spec_excerpt(root)
    if excerpt:
        sections.append(excerpt)
    else:
        sections.append(
            "No integration.yaml found. Use the new-vendor-integration skill to create one."
        )

    sections.append(ARCHITECTURE)
    return "\n\n".join(sections)


if __name__ == "__main__":
    sys.exit(mxhook.main(handler))
