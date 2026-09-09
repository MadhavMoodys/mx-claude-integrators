"""Test helper: run a hook script end-to-end the way Claude Code runs it.

Hooks are invoked as subprocesses with a JSON event on stdin, so the tests do
the same rather than importing the handler. That keeps the exit-code contract
-- the part that actually decides whether an edit is blocked -- under test.
"""

import json
import os
import subprocess
import sys

HOOKS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks")


class Result:
    def __init__(self, code, stdout, stderr):
        self.code = code
        self.stdout = stdout
        self.stderr = stderr

    @property
    def blocked(self):
        return self.code == 2

    def __repr__(self):
        return "Result(code=%r, stderr=%r)" % (self.code, self.stderr)


def run_hook(name, event, env=None, cwd=None, timeout=120):
    script = os.path.join(HOOKS_DIR, name)
    child_env = dict(os.environ)
    child_env.pop("MX_HOOKS_DISABLED", None)
    if env:
        child_env.update(env)
    proc = subprocess.run(
        [sys.executable, script],
        input=json.dumps(event),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=child_env,
        cwd=cwd,
        timeout=timeout,
    )
    return Result(proc.returncode, proc.stdout, proc.stderr)


def write_event(tool_name, tool_input, **extra):
    event = {"tool_name": tool_name, "tool_input": tool_input}
    event.update(extra)
    return event
