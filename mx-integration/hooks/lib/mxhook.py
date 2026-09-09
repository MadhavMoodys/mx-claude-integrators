"""Shared plumbing for the mx-integration hooks.

Every hook is a standalone python3 script with no third-party imports, so this
module is the only thing they share. Import it by putting `lib/` on sys.path:

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lib"))
    import mxhook

Exit-code contract (Claude Code):
  0  allow, stdout is shown to the user (and injected as context on SessionStart)
  2  block, stderr is fed back to the agent so it can correct itself
  1  hook itself failed; Claude warns the user but the tool call proceeds

Hooks must never fail closed on their own bugs -- a crashing linter that blocks
every edit is worse than no linter, so `main` funnels unexpected exceptions to
exit 1 rather than 2.
"""

import json
import os
import subprocess
import sys

DISABLE_ENV = "MX_HOOKS_DISABLED"

EXIT_ALLOW = 0
EXIT_ERROR = 1
EXIT_BLOCK = 2


class Block(Exception):
    """Raised by a hook to deny the tool call with a message for the agent."""


def disabled():
    return os.environ.get(DISABLE_ENV, "") not in ("", "0", "false")


def read_event(stream=None):
    """Parse the hook payload Claude Code writes to stdin.

    Returns {} on empty or malformed input so a hook degrades to a no-op rather
    than erroring out of a tool call it could not have judged anyway.
    """
    stream = stream if stream is not None else sys.stdin
    try:
        raw = stream.read()
    except Exception:
        return {}
    if not raw or not raw.strip():
        return {}
    try:
        event = json.loads(raw)
    except (ValueError, TypeError):
        return {}
    return event if isinstance(event, dict) else {}


def tool_input(event):
    value = event.get("tool_input")
    return value if isinstance(value, dict) else {}


def file_path(event):
    return tool_input(event).get("file_path") or ""


def edited_text(event):
    """Everything this tool call is about to add to a file, as one string.

    Covers Write (`content`), Edit (`new_string`) and MultiEdit (`edits[].new_string`)
    with a single accessor so guards do not each re-derive the shape. Only the
    *new* text is returned -- guards must not fire on pre-existing content the
    agent is merely reading past.
    """
    ti = tool_input(event)
    parts = []
    for key in ("content", "new_string"):
        value = ti.get(key)
        if isinstance(value, str):
            parts.append(value)
    edits = ti.get("edits")
    if isinstance(edits, list):
        for edit in edits:
            if isinstance(edit, dict) and isinstance(edit.get("new_string"), str):
                parts.append(edit["new_string"])
    return "\n".join(parts)


def project_dir(event):
    return (
        event.get("cwd")
        or os.environ.get("CLAUDE_PROJECT_DIR")
        or os.getcwd()
    )


def repo_root(start):
    """Nearest ancestor containing a .git directory, else `start`."""
    current = os.path.abspath(start)
    while True:
        if os.path.isdir(os.path.join(current, ".git")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            return os.path.abspath(start)
        current = parent


def maven_module(path, root):
    """Top-level Maven module owning `path`, or None if outside one.

    Resolved by walking down from the repo root to the first directory that has
    a pom.xml, which is what `mvn -pl` expects. Returns the module directory
    name, not an absolute path.
    """
    if not path:
        return None
    path = os.path.abspath(path)
    root = os.path.abspath(root)
    if not path.startswith(root + os.sep):
        return None
    relative = os.path.relpath(path, root)
    top = relative.split(os.sep)[0]
    if not top or top in (".", ".."):
        return None
    if not os.path.isfile(os.path.join(root, top, "pom.xml")):
        return None
    return top


def state_dir(event):
    """Scratch directory shared between hooks within a working tree.

    Lives under the repo's .git/ so it is already ignored by git and is wiped
    with the clone. MX_HOOK_STATE_DIR overrides it, which is what the tests use.
    """
    override = os.environ.get("MX_HOOK_STATE_DIR")
    path = override or os.path.join(repo_root(project_dir(event)), ".git", "mx-hooks")
    try:
        os.makedirs(path, exist_ok=True)
    except OSError:
        return None
    return path


def read_state(event, name, default=None):
    directory = state_dir(event)
    if not directory:
        return default
    try:
        with open(os.path.join(directory, name)) as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return default


def write_state(event, name, value):
    directory = state_dir(event)
    if not directory:
        return
    try:
        with open(os.path.join(directory, name), "w") as handle:
            json.dump(value, handle)
    except OSError:
        pass


def run(cmd, cwd, timeout):
    """Run a command, never raising. Returns (returncode, combined_output)."""
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            timeout=timeout,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        return proc.returncode, proc.stdout or ""
    except subprocess.TimeoutExpired:
        return None, "timed out after %ss" % timeout
    except FileNotFoundError:
        return None, "%s not found on PATH" % cmd[0]
    except Exception as exc:  # pragma: no cover - defensive
        return None, str(exc)


def tail(text, limit=4000):
    """Trim tool output to the tail, which is where compilers put the errors."""
    text = text or ""
    if len(text) <= limit:
        return text
    return "...(truncated)...\n" + text[-limit:]


def main(handler, stream=None):
    """Run `handler(event)` under the exit-code contract described above.

    `handler` returns a string to emit on stdout (or None), and raises Block to
    deny. Any other exception is a hook bug: exit 1, never 2.
    """
    if disabled():
        return EXIT_ALLOW
    try:
        event = read_event(stream)
        message = handler(event)
    except Block as block:
        sys.stderr.write(str(block).rstrip() + "\n")
        return EXIT_BLOCK
    except Exception as exc:  # pragma: no cover - defensive
        sys.stderr.write("mx-integration hook error: %s\n" % exc)
        return EXIT_ERROR
    if message:
        sys.stdout.write(message.rstrip() + "\n")
    return EXIT_ALLOW
