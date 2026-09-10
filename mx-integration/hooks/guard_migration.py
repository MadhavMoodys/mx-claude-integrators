#!/usr/bin/env python3
"""PreToolUse(Edit|Write|MultiEdit): an entity change needs a migration beside it.

Hibernate will happily run against a schema it grew itself locally, so an entity
that gained a column without a matching Flyway script passes every local check
and fails on the first deploy, where migrations are the only thing that touch the
database. The gap is invisible exactly where it is cheapest to close.

The check is deliberately narrow. It fires only on *schema-affecting* edits --
a new persistent field, or a mapping annotation -- so a javadoc fix or a method
body change to an entity is not blocked. It is satisfied by any added or modified
file under db/migration/ in the working tree, staged or not, which is the state
git can report without guessing at intent.
"""

import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
import mxhook  # noqa: E402

TIMEOUT_SECONDS = 10

MIGRATION_SEGMENT = "db/migration/"

ENTITY_RE = re.compile(r"^\s*@(?:Entity|Table)\b", re.MULTILINE)

# Annotations that describe how a field maps onto a column or a join.
MAPPING_RE = re.compile(
    r"@(?:Column|Id|GeneratedValue|JoinColumn|JoinTable|ManyToOne|OneToMany"
    r"|OneToOne|ManyToMany|Enumerated|Lob|Embedded|EmbeddedId|Table)\b"
)

# A field declaration: a modifier, a type, a name, and a terminating semicolon.
# Requiring the modifier keeps `return "inbox " + id;` out, and requiring the
# semicolon at end of line keeps method signatures out.
FIELD_RE = re.compile(
    r"^\s*(?:private|protected|public)\s+"
    r"(?:static\s+|final\s+|transient\s+|volatile\s+)*"
    r"[\w.$]+(?:<[^>]*>)?(?:\[\])?\s+\w+\s*(?:=[^;]*)?;\s*$",
    re.MULTILINE,
)

# @Transient is the annotation that says "this field is not persisted", so an
# edit carrying one is asserting the change has no schema consequence.
TRANSIENT_RE = re.compile(r"@Transient\b")

VERSION_RE = re.compile(r"^V(?P<number>\d+)__", re.IGNORECASE)

SKIP_DIRS = {".git", "target", "build", "node_modules", ".idea"}


def file_contains_entity(path):
    try:
        with open(path) as handle:
            return bool(ENTITY_RE.search(handle.read()))
    except (OSError, UnicodeDecodeError):
        return False


def is_schema_affecting(text):
    if TRANSIENT_RE.search(text):
        return False
    return bool(MAPPING_RE.search(text) or FIELD_RE.search(text))


def migration_in_working_tree(root):
    """True when git reports an added or modified file under db/migration/.

    Returns True when git cannot answer -- no repository, no git on PATH -- so a
    guard that has lost its only source of truth fails open rather than blocking
    every entity edit.
    """
    code, output = mxhook.run(
        ["git", "status", "--porcelain"], cwd=root, timeout=TIMEOUT_SECONDS
    )
    if code is None or code != 0:
        return True
    for line in output.splitlines():
        if MIGRATION_SEGMENT in line.replace(os.sep, "/"):
            return True
    return False


def next_version(root):
    """The lowest version number no migration has used yet.

    An agent told only "add a migration" picks a number that collides with one
    already on the branch, and Flyway rejects the duplicate at startup.
    """
    highest = 0
    for current, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        if not current.replace(os.sep, "/").endswith(MIGRATION_SEGMENT.rstrip("/")):
            continue
        for name in files:
            match = VERSION_RE.match(name)
            if match:
                highest = max(highest, int(match.group("number")))
    return highest + 1


def handler(event):
    path = mxhook.file_path(event)
    if not path.endswith(".java"):
        return None

    text = mxhook.edited_text(event)

    # A new entity file is not on disk yet, so the annotation can only come from
    # the incoming content; an Edit to an existing one is the other way round.
    if not (ENTITY_RE.search(text) or file_contains_entity(path)):
        return None

    if not is_schema_affecting(text):
        return None

    root = mxhook.repo_root(mxhook.project_dir(event))
    if migration_in_working_tree(root):
        return None

    raise mxhook.Block(
        "Schema change to %s with no migration.\n"
        "Add the matching Flyway script under src/main/resources/db/migration/, "
        "named V%d__<description>.sql, in the same change.\n"
        "Hibernate grows the local schema on its own, so this only fails on deploy."
        % (os.path.basename(path), next_version(root))
    )


if __name__ == "__main__":
    sys.exit(mxhook.main(handler))
