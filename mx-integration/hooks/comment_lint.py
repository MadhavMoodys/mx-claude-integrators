#!/usr/bin/env python3
"""PostToolUse(Edit|Write): enforce the comment policy on newly written Java.

The policy, measured from mx-newsedge rather than invented: comment density
there tracks non-obviousness -- ~1% in a plain router, ~36% in the config that
deliberately rejects work at shutdown -- and almost every inline comment is
unique prose about a failure mode or a transaction boundary.

Three checks block, because they are mechanical and have a single right answer:
commented-out code, TODOs without a ticket, and javadoc that restates its own
parameter name. One check only warns -- whether a comment is redundant with the
line below it is a judgement call, and a heuristic that blocks on judgement will
fight the agent over comments that are correct.

Also runnable directly to sweep existing files:

    python3 comment_lint.py --check path/to/File.java ...
"""

import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
import mxhook  # noqa: E402

TODO_RE = re.compile(r"\b(TODO|FIXME|XXX|HACK)\b(?!\s*\([A-Z][A-Z0-9_]+-\d+\))", re.IGNORECASE)

TAUTOLOGICAL_PARAM_RE = re.compile(
    r"@param\s+(?P<name>\w+)\s+(?:the\s+|a\s+|an\s+)?(?P<desc>\w+)\s*$", re.IGNORECASE
)

FILLER_RE = re.compile(
    r"^(?:getter|setter|constructor|default constructor|no-op|empty)"
    r"(?:\s+(?:for|of)\s+\w+)?\.?$",
    re.IGNORECASE,
)

# Arrange/Act/Assert and Given/When/Then markers structure a test; they restate
# the next line by design and flagging them buries every other warning.
SECTION_MARKER_RE = re.compile(
    r"^(?:arrange|act|assert|given|when|then|setup|teardown|verify)\b[\s:.-]*$",
    re.IGNORECASE,
)

STOPWORDS = {
    "the", "a", "an", "this", "that", "to", "of", "for", "and", "or", "is", "are",
    "we", "it", "its", "in", "on", "by", "with", "from", "as", "be", "not", "no",
}

# A comment body that looks like Java rather than prose. Ordered cheapest first.
CODE_SHAPES = (
    re.compile(r"^@[A-Z]\w*(?:\(.*\))?$"),                       # @Transactional
    re.compile(r"^(?:import|package)\s+[\w.]+\s*;$"),
    re.compile(r"^(?:public|private|protected|static|final|abstract|synchronized)\s+\S+.*[;{]$"),
    re.compile(r"^(?:if|for|while|switch|catch)\s*\(.*\)\s*\{?$"),
    re.compile(r"^(?:return|throw|break|continue)\b.*;$"),
    re.compile(r"^\}?\s*else(?:\s+if\s*\(.*\))?\s*\{?$"),
    re.compile(r"^[\w.<>\[\]]+\s+\w+\s*=\s*.+;$"),               # int total = a + b;
    re.compile(r"^[\w.]+\s*(?:=|\+=|-=)\s*.+;$"),                # this.x = y;
    re.compile(r"^[\w.]+\([^;]*\)\s*(?:\.\w+\([^;]*\))*\s*;$"),  # log.info("hi");
    re.compile(r"^[{}]+$"),
)


class Finding:
    def __init__(self, line_no, text, message, blocking):
        self.line_no = line_no
        self.text = text
        self.message = message
        self.blocking = blocking

    def format(self, path=None):
        prefix = "%s:%d: " % (path, self.line_no) if path else "line %d: " % self.line_no
        return "%s%s\n    %s" % (prefix, self.message, self.text.strip())


def comment_body(line):
    """(body, style) for a comment on this line, or (None, None) if there is none.

    `style` is "line" or "block". The distinction matters: javadoc legitimately
    embeds code in <pre>{@code ...} examples, so the commented-out-code check
    only applies to // comments.

    Lines whose only `//` sits inside a string literal are not comments, which is
    how URLs in code avoid being read as one.
    """
    stripped = line.strip()
    if stripped.startswith(("*", "/**", "/*")):
        return stripped.lstrip("/*").strip(), "block"
    index = find_line_comment(line)
    if index is None:
        return None, None
    return line[index + 2:].strip(), "line"


def find_line_comment(line):
    """Index of the `//` that starts a comment, ignoring string literals."""
    in_string = False
    quote = ""
    i = 0
    while i < len(line) - 1:
        char = line[i]
        if in_string:
            if char == "\\":
                i += 2
                continue
            if char == quote:
                in_string = False
        elif char in "\"'":
            in_string = True
            quote = char
        elif char == "/" and line[i + 1] == "/":
            return i
        i += 1
    return None


def looks_like_code(body):
    if not body:
        return False
    # A sentence that happens to end in a semicolon is still a sentence; require
    # the whole body to match a code shape, not merely contain punctuation.
    for pattern in CODE_SHAPES:
        if pattern.match(body):
            return True
    return False


def tokens(text):
    return {
        word.lower()
        for word in re.findall(r"[A-Za-z]+", text)
        if word.lower() not in STOPWORDS and len(word) > 2
    }


def identifier_tokens(line):
    """Words in a line of code, with camelCase split so `incrementCounter`
    matches the comment `increment counter`."""
    result = set()
    for word in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", line):
        for part in re.findall(r"[A-Z]+(?![a-z])|[A-Z][a-z]*|[a-z]+", word):
            if len(part) > 2 and part.lower() not in STOPWORDS:
                result.add(part.lower())
    return result


def next_code_line(lines, index):
    for line in lines[index + 1:]:
        stripped = line.strip()
        if not stripped or stripped.startswith(("//", "*", "/*")):
            continue
        return stripped
    return None


def lint(text, start_line=1):
    findings = []
    lines = text.splitlines()

    for offset, line in enumerate(lines):
        line_no = start_line + offset
        body, style = comment_body(line)
        if not body:
            continue

        if TODO_RE.search(body):
            findings.append(Finding(
                line_no, line,
                "TODO without a ticket. Write TODO(M3PDS-123): ... so it can be tracked.",
                blocking=True,
            ))
            continue

        if style == "line" and looks_like_code(body):
            findings.append(Finding(
                line_no, line,
                "commented-out code. Delete it; git has the history.",
                blocking=True,
            ))
            continue

        param = TAUTOLOGICAL_PARAM_RE.match(body)
        if param and param.group("name").lower() == param.group("desc").lower():
            findings.append(Finding(
                line_no, line,
                "javadoc restates the parameter name. Say something contractual or drop the tag.",
                blocking=True,
            ))
            continue

        if FILLER_RE.match(body):
            findings.append(Finding(
                line_no, line,
                "filler comment on an obvious member. Delete it.",
                blocking=True,
            ))
            continue

        if SECTION_MARKER_RE.match(body):
            continue

        following = next_code_line(lines, offset)
        if following and not following.startswith(("}", "{")):
            words = tokens(body)
            if words and words <= identifier_tokens(following):
                findings.append(Finding(
                    line_no, line,
                    "comment may just restate the next line (%s). Keep it only if it "
                    "explains why." % following[:60],
                    blocking=False,
                ))

    return findings


def handler(event):
    path = mxhook.file_path(event)
    if not path.endswith(".java"):
        return None

    findings = lint(mxhook.edited_text(event))
    if not findings:
        return None

    blocking = [f for f in findings if f.blocking]
    if blocking:
        raise mxhook.Block(
            "Comment policy violations in %s:\n%s\n\n"
            "Policy: comment the why, never the what. No commented-out code. "
            "TODOs carry a ticket key."
            % (os.path.basename(path), "\n".join(f.format() for f in blocking))
        )

    return "mx-integration comment check (advisory):\n" + "\n".join(
        f.format() for f in findings
    )


def check_files(paths):
    """--check mode: report findings for existing files without blocking anything."""
    failures = 0
    for path in paths:
        try:
            with open(path, errors="replace") as handle:
                text = handle.read()
        except OSError as exc:
            print("%s: unreadable (%s)" % (path, exc))
            failures += 1
            continue
        for finding in lint(text):
            kind = "BLOCK" if finding.blocking else "warn "
            print("%s %s" % (kind, finding.format(path)))
            if finding.blocking:
                failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--check":
        sys.exit(check_files(sys.argv[2:]))
    sys.exit(mxhook.main(handler))
