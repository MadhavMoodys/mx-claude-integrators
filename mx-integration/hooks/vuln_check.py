#!/usr/bin/env python3
"""PostToolUse(Edit|Write) on pom.xml: screen new dependencies for known CVEs.

This runs OWASP dependency-check against the module whose pom just changed, at
the same threshold the pipeline uses. It is a fast local signal, not the gate:
the mandatory JFrog "scan descendants" review of the built image still decides
what ships. Anything this hook cannot do confidently -- a cold NVD database, a
missing Maven, a run that outlives its budget -- is reported and waved through,
because a local convenience check that blocks on its own setup problems just
gets switched off.

Results are cached for a day against the pom's hash, so editing the same file
repeatedly costs one run.
"""

import hashlib
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
import mxhook  # noqa: E402

CACHE_FILE = "vuln_cache.json"
CACHE_SECONDS = 24 * 3600

# The first NVD download takes 10-20 minutes, far longer than a turn should
# wait. Exceeding this budget is reported, never blocked on.
DEFAULT_BUDGET_SECONDS = 300

FAIL_ON_CVSS = "7"

# Phrases dependency-check prints while it is populating or refreshing its copy
# of the NVD. They mean "no verdict yet", which is not the same as "clean".
SYNC_MARKERS = (
    "nvd cve",
    "updating the nvd",
    "nvd data",
    "download started",
    "nvd api",
)


def budget_seconds():
    raw = os.environ.get("MX_VULN_SYNC_BUDGET", "")
    try:
        return max(1, int(raw))
    except ValueError:
        return DEFAULT_BUDGET_SECONDS


def pom_hash(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def cached(event, digest):
    cache = mxhook.read_state(event, CACHE_FILE, default={})
    if not isinstance(cache, dict):
        return False
    entry = cache.get(digest)
    if not isinstance(entry, dict):
        return False
    return (time.time() - entry.get("at", 0)) < CACHE_SECONDS


def remember(event, digest):
    cache = mxhook.read_state(event, CACHE_FILE, default={})
    if not isinstance(cache, dict):
        cache = {}
    # Only the current pom matters; older hashes describe files that no longer
    # exist in this shape.
    fresh = {
        key: value
        for key, value in cache.items()
        if isinstance(value, dict) and (time.time() - value.get("at", 0)) < CACHE_SECONDS
    }
    fresh[digest] = {"at": time.time()}
    mxhook.write_state(event, CACHE_FILE, fresh)


def is_syncing(output):
    lowered = output.lower()
    return any(marker in lowered for marker in SYNC_MARKERS)


def command(module):
    cmd = [
        "mvn", "-q",
        "org.owasp:dependency-check-maven:check",
        "-DfailBuildOnCVSS=" + FAIL_ON_CVSS,
        "-DskipTestScope=true",
    ]
    api_key = os.environ.get("NVD_API_KEY")
    if api_key:
        cmd.append("-Dnvd.api.key=" + api_key)
    if module:
        cmd += ["-pl", module]
    return cmd


def handler(event):
    path = mxhook.file_path(event)
    if os.path.basename(path) != "pom.xml":
        return None
    if not os.path.exists(path):
        return None

    try:
        digest = pom_hash(path)
    except OSError:
        return None

    if cached(event, digest):
        return None

    root = mxhook.repo_root(mxhook.project_dir(event))
    module = mxhook.maven_module(path, root)
    code, output = mxhook.run(command(module), cwd=root, timeout=budget_seconds())

    target = module or "the reactor"

    if code is None:
        return "mx-integration: dependency-check skipped for %s (%s). JFrog remains the gate." % (
            target, output.strip()
        )

    if code != 0 and is_syncing(output):
        # No verdict was reached, so nothing is cached -- the next pom edit
        # tries again against a warmer database.
        return (
            "mx-integration: dependency-check is still syncing the NVD for %s, so it "
            "returned no verdict. Set NVD_API_KEY to speed this up. JFrog remains the gate."
            % target
        )

    if code != 0:
        raise mxhook.Block(
            "dependency-check found vulnerabilities at CVSS >= %s in %s:\n%s\n"
            "Upgrade the dependency, or suppress it with a documented reason if the "
            "path is unreachable." % (FAIL_ON_CVSS, target, mxhook.tail(output))
        )

    remember(event, digest)
    return "mx-integration: dependency-check clean for %s." % target


if __name__ == "__main__":
    sys.exit(mxhook.main(handler))
