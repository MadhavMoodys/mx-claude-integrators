#!/usr/bin/env python3
"""Stop: run the tests for whatever the turn touched before it is allowed to end.

The edit loop only compiles, so this is the first point at which behaviour is
actually checked. Scoping to the modules compile_touched.py recorded keeps a
one-file change from paying for the whole reactor.

Blocking here means the agent gets the failures back and keeps working, so a
turn cannot end on red.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
import mxhook  # noqa: E402

TIMEOUT_SECONDS = 900

TOUCHED_FILE = "touched.json"


def handler(event):
    # Set when this Stop is itself the result of a previous Stop hook blocking.
    # Running again would loop the turn forever.
    if event.get("stop_hook_active"):
        return None

    touched = mxhook.read_state(event, TOUCHED_FILE, default=[])
    if not isinstance(touched, list) or not touched:
        return None

    root = mxhook.repo_root(mxhook.project_dir(event))
    modules = ",".join(sorted(touched))
    code, output = mxhook.run(
        ["mvn", "-q", "test", "-pl", modules],
        cwd=root, timeout=TIMEOUT_SECONDS,
    )

    if code is None:
        mxhook.write_state(event, TOUCHED_FILE, [])
        return "mx-integration: skipped tests for %s (%s)" % (modules, output.strip())

    if code != 0:
        # Deliberately not cleared: the next Stop must retry the same modules
        # until they pass.
        raise mxhook.Block(
            "Tests failed in %s:\n%s\nFix these before ending the turn."
            % (modules, mxhook.tail(output))
        )

    mxhook.write_state(event, TOUCHED_FILE, [])
    return "mx-integration: tests passed for %s" % modules


if __name__ == "__main__":
    sys.exit(mxhook.main(handler))
