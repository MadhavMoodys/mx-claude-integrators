#!/usr/bin/env python3
"""PreToolUse(Edit|Write|MultiEdit): the Spring conventions a compiler cannot state.

Three rules, all chosen because they compile cleanly and only bite later:

1. Field injection in a controller. `@Autowired` on a field works at runtime and
   fails in a unit test, where there is no container to populate it. Constructor
   injection is what the templates already use and what makes the dependency
   visible in the signature.
2. A JPA entity in a controller signature. Returning one makes the persistence
   model the public API, so the next schema change is a breaking API change.
   Entity names are read off the repo rather than inferred from package names --
   a repo with no @Entity classes, which is every -api module, cannot produce a
   false positive here.
3. Wildcard imports. `import java.util.*` hides which types a file actually uses
   and turns an upstream addition into an ambiguous-reference compile error.

Rules 1 and 2 are scoped to controllers; rule 3 applies to all Java. Only the
text being *added* is inspected, so pre-existing violations never block an agent
that is merely editing around them.
"""

import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
import mxhook  # noqa: E402

WILDCARD_IMPORT_RE = re.compile(
    r"^\s*import\s+(?P<static>static\s+)?(?P<name>[\w.]+)\.\*\s*;", re.MULTILINE
)

AUTOWIRED_RE = re.compile(r"^\s*@Autowired\b(?P<rest>.*)$")

# A signature we consider exposed: public or protected, and taking arguments.
# Private mapping helpers are legitimate -- converting an entity to a DTO inside
# the controller is the fix, not the violation.
EXPOSED_SIGNATURE_RE = re.compile(r"^\s*(?:public|protected)\b.*\(")

ENTITY_RE = re.compile(r"^\s*@(?:Entity|Table)\b", re.MULTILINE)

SKIP_DIRS = {".git", "target", "build", "node_modules", ".idea"}

INJECTION_HELP = (
    "Use constructor injection instead:\n"
    "  private final AcmeClient client;\n"
    "  public AcmeController(AcmeClient client) { this.client = client; }\n"
    "A field-injected controller cannot be constructed in a unit test."
)


def is_controller(path):
    normalised = path.replace(os.sep, "/")
    return normalised.endswith("Controller.java") or "/controller/" in normalised


def is_test_source(path):
    normalised = path.replace(os.sep, "/")
    return "/src/test/" in normalised or "/tests/" in normalised


def check_wildcard_imports(path, text):
    for match in WILDCARD_IMPORT_RE.finditer(text):
        # `import static org.mockito.Mockito.*` is how Mockito and AssertJ are
        # meant to be used; blocking it in tests is how a hook gets switched off.
        if match.group("static") and is_test_source(path):
            continue
        raise mxhook.Block(
            "Wildcard import in %s:\n  %s\nImport each type explicitly."
            % (path, match.group(0).strip())
        )


def declaration_after_autowired(lines, index):
    """The declaration `@Autowired` is annotating, skipping stacked annotations.

    Returns None when the annotation trails off the end of the edited fragment,
    which happens whenever an Edit splits a class mid-way. Guessing there would
    block on incomplete information.
    """
    for line in lines[index + 1:]:
        stripped = line.strip()
        if not stripped or stripped.startswith("@"):
            continue
        return stripped
    return None


def check_field_injection(path, text):
    lines = text.splitlines()
    for index, line in enumerate(lines):
        match = AUTOWIRED_RE.match(line)
        if not match:
            continue

        # Covers both `@Autowired` on its own line and `@Autowired private Foo f;`.
        declaration = match.group("rest").strip()
        if not declaration:
            declaration = declaration_after_autowired(lines, index)
        if not declaration:
            continue

        # A constructor or setter takes arguments; a field never does.
        if "(" in declaration:
            continue

        raise mxhook.Block(
            "Field injection in %s:\n  %s\n%s" % (path, declaration, INJECTION_HELP)
        )


def entity_names(root):
    """Simple names of every @Entity/@Table class in the repo.

    The class name is taken from the filename rather than parsed out of the
    source: a public Java class must match its file, and that holds even when
    the declaration is spread over several lines.
    """
    found = set()
    for current, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            if not name.endswith(".java"):
                continue
            try:
                with open(os.path.join(current, name)) as handle:
                    source = handle.read()
            except (OSError, UnicodeDecodeError):
                continue
            if ENTITY_RE.search(source):
                found.add(name[:-len(".java")])
    return found


def check_entity_exposure(event, path, text):
    signatures = [
        line for line in text.splitlines() if EXPOSED_SIGNATURE_RE.match(line)
    ]
    if not signatures:
        return

    # Only walk the tree once there is something that could violate the rule.
    root = mxhook.repo_root(mxhook.project_dir(event))
    names = entity_names(root)
    if not names:
        return

    for line in signatures:
        for name in sorted(names):
            if not re.search(r"\b%s\b" % re.escape(name), line):
                continue
            raise mxhook.Block(
                "Controller signature exposes the JPA entity %s:\n  %s\n"
                "Return a DTO instead. Exposing the entity makes the database "
                "schema the public API, so the next migration breaks callers."
                % (name, line.strip())
            )


def handler(event):
    path = mxhook.file_path(event)
    if not path.endswith(".java"):
        return None

    text = mxhook.edited_text(event)
    check_wildcard_imports(path, text)

    if is_controller(path):
        check_field_injection(path, text)
        check_entity_exposure(event, path, text)
    return None


if __name__ == "__main__":
    sys.exit(mxhook.main(handler))
