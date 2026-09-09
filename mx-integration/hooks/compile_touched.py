#!/usr/bin/env python3
"""PostToolUse(Edit|Write): compile the module the agent just edited.

Compiling is the cheapest signal that catches the mistakes an agent actually
makes -- wrong type, missing import, renamed method. Running the full test suite
here would be too slow to keep the edit loop tight, so tests are deferred to the
Stop hook and this only ever runs `test-compile`.

Also records which modules were touched, which is how run_tests.py knows what to
run at the end of the turn.
"""

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
import mxhook  # noqa: E402

DEBOUNCE_SECONDS = 10
TIMEOUT_SECONDS = 240

TOUCHED_FILE = "touched.json"
LAST_COMPILE_FILE = "last_compile.json"


def record_touched(event, module):
    touched = mxhook.read_state(event, TOUCHED_FILE, default=[])
    if not isinstance(touched, list):
        touched = []
    if module not in touched:
        touched.append(module)
        mxhook.write_state(event, TOUCHED_FILE, touched)


def debounced(event, module):
    """True when this module compiled moments ago.

    An agent editing three files in a row would otherwise pay for three full
    Maven startups to learn the same thing once.
    """
    last = mxhook.read_state(event, LAST_COMPILE_FILE, default={})
    if not isinstance(last, dict):
        last = {}
    now = time.time()
    previous = last.get(module)
    if isinstance(previous, (int, float)) and now - previous < DEBOUNCE_SECONDS:
        return True
    last[module] = now
    mxhook.write_state(event, LAST_COMPILE_FILE, last)
    return False


def compile_module(root, module):
    """Compile offline first; fall back online only if offline mode is the problem.

    `-o` keeps the common case off the network. A cold or pruned local repository
    fails in offline mode with a resolution error, and retrying online is the
    only way to tell that apart from a genuine compile error.
    """
    base = ["mvn", "-o", "-q", "-DskipTests", "test-compile", "-pl", module]
    code, output = mxhook.run(base, cwd=root, timeout=TIMEOUT_SECONDS)
    if code == 0:
        return 0, output
    if code is None:
        return code, output
    if "offline" in output.lower() or "cannot access" in output.lower():
        return mxhook.run(
            ["mvn", "-q", "-DskipTests", "test-compile", "-pl", module],
            cwd=root, timeout=TIMEOUT_SECONDS,
        )
    return code, output


def handler(event):
    path = mxhook.file_path(event)
    if not path.endswith(".java"):
        return None

    root = mxhook.repo_root(mxhook.project_dir(event))
    module = mxhook.maven_module(path, root)
    if not module:
        return None

    record_touched(event, module)
    if debounced(event, module):
        return None

    code, output = compile_module(root, module)

    # A missing or hanging Maven is an environment problem, not the agent's --
    # reporting it as a compile failure would send it chasing code that is fine.
    if code is None:
        return "mx-integration: skipped compile of %s (%s)" % (module, output.strip())

    if code != 0:
        raise mxhook.Block(
            "Compilation of %s failed:\n%s\nFix this before continuing."
            % (module, mxhook.tail(output))
        )
    return None


if __name__ == "__main__":
    sys.exit(mxhook.main(handler))
