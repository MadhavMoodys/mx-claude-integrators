#!/usr/bin/env python3
"""Generate a new mx-<vendor> integration repo from templates/.

Deterministic on purpose: the mechanical half of an integration -- auth, retry,
error mapping, exception hierarchy, config, ops wiring -- is copied and renamed,
not written by an agent. What the templates cannot know (the vendor's request and
response shapes) is left as ticket-tagged TODOs for the agent to fill from the
vendor's OpenAPI spec.

    scaffold.py --spec integration.yaml --out /path/to/mx-acme

Stdlib only -- the plugin must run on a clean checkout with no pip install.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

# A file whose bytes are copied verbatim: no token substitution, no block handling.
BINARY_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".jar", ".p12", ".keystore"}

# Templates cannot ship a real ".gitignore": in the plugin repo it would be hidden
# from tooling and would ignore its own directory. It is renamed on the way out.
RENAME_ON_COPY = {"gitignore": ".gitignore"}

BLOCK_OPEN_RE = re.compile(r"^\s*\{\{#(\w+)\}\}\s*$")
BLOCK_CLOSE_RE = re.compile(r"^\s*\{\{/(\w+)\}\}\s*$")


class SpecError(Exception):
    """The spec file is missing a field, or holds a value the scaffolder rejects."""


# --------------------------------------------------------------------------- spec


def parse_spec(text: str) -> dict:
    """Parse the flat `key: value` subset of YAML that integration.yaml uses.

    Deliberately not PyYAML: a stdlib-only hook and scaffold set is worth more than
    the extra syntax. Supported forms are `key: value`, `key:` followed by `- item`
    lines, `#` comments, and blank lines. Anything else is a hard error rather than
    a silent misread.
    """
    spec: dict = {}
    current_list_key: str | None = None

    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.split("#", 1)[0].rstrip() if not raw.lstrip().startswith("#") else ""
        if not line.strip():
            continue

        if line.lstrip().startswith("- "):
            if current_list_key is None:
                raise SpecError(f"line {lineno}: list item with no key above it")
            spec[current_list_key].append(_scalar(line.lstrip()[2:].strip()))
            continue

        if ":" not in line:
            raise SpecError(f"line {lineno}: expected 'key: value', got {line!r}")

        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if value:
            spec[key] = _scalar(value)
            current_list_key = None
        else:
            spec[key] = []
            current_list_key = key

    return spec


def _scalar(value: str):
    value = value.strip().strip('"').strip("'")
    lowered = value.lower()
    if lowered in ("true", "yes"):
        return True
    if lowered in ("false", "no"):
        return False
    return value


def build_context(spec: dict) -> dict:
    """Turn a spec into the substitution tokens and the conditional-block flags."""
    vendor = str(spec.get("vendor", "")).strip()
    if not vendor:
        raise SpecError("spec must set 'vendor'")
    if not re.fullmatch(r"[a-z][a-z0-9]*", vendor):
        raise SpecError(
            f"vendor must be lowercase letters and digits, starting with a letter: got {vendor!r}. "
            "It becomes a Java package segment and a Maven artifactId, so hyphens and "
            "underscores are rejected rather than silently mangled."
        )

    display = str(spec.get("display_name") or "").strip() or vendor.capitalize()
    ticket = str(spec.get("ticket") or "TICKET-000").strip()
    if not re.fullmatch(r"[A-Z][A-Z0-9_]+-\d+", ticket):
        raise SpecError(
            f"ticket must look like PROJ-123 (it is written into the generated TODOs "
            f"and the commit hook enforces the same shape): got {ticket!r}"
        )

    return {
        "tokens": {
            "{{vendor}}": vendor,
            "{{Vendor}}": display,
            "{{VENDOR}}": vendor.upper(),
            "TICKET-000": ticket,
        },
        "flags": {"connector": bool(spec.get("connector", False))},
    }


# ---------------------------------------------------------------------- rendering


def apply_blocks(text: str, flags: dict) -> str:
    """Keep or drop the lines between `{{#flag}}` and `{{/flag}}` markers.

    The markers occupy whole lines and are always removed, so a connector-less
    vendor gets a pom.xml and a deployment.yaml with no dangling references rather
    than ones that mention a module that was never generated.
    """
    out: list[str] = []
    stack: list[tuple[str, bool]] = []

    for lineno, line in enumerate(text.splitlines(keepends=True), start=1):
        opened = BLOCK_OPEN_RE.match(line)
        if opened:
            name = opened.group(1)
            if name not in flags:
                raise SpecError(f"line {lineno}: unknown conditional block {{{{#{name}}}}}")
            # A nested block inside a dropped one stays dropped regardless of its flag.
            keeping = flags[name] and all(k for _, k in stack)
            stack.append((name, keeping))
            continue

        closed = BLOCK_CLOSE_RE.match(line)
        if closed:
            if not stack or stack[-1][0] != closed.group(1):
                raise SpecError(f"line {lineno}: {{{{/{closed.group(1)}}}}} does not close an open block")
            stack.pop()
            continue

        if all(keeping for _, keeping in stack):
            out.append(line)

    if stack:
        raise SpecError(f"unclosed conditional block {{{{#{stack[-1][0]}}}}}")

    return "".join(out)


def substitute(text: str, tokens: dict) -> str:
    """Replace the tokens. Case-sensitive, so {{vendor}} and {{Vendor}} stay distinct."""
    for token, value in tokens.items():
        text = text.replace(token, value)
    return text


def render_path(relative: Path, tokens: dict) -> Path:
    parts = [substitute(part, tokens) for part in relative.parts]
    if parts and parts[-1] in RENAME_ON_COPY:
        parts[-1] = RENAME_ON_COPY[parts[-1]]
    return Path(*parts)


def should_skip(relative: Path, flags: dict) -> bool:
    """Drop whole template subtrees whose module was not requested."""
    if not flags.get("connector") and relative.parts and relative.parts[0].endswith("-connector"):
        return True
    return False


def generate(templates_dir: Path, out_dir: Path, context: dict, force: bool) -> list[Path]:
    tokens, flags = context["tokens"], context["flags"]
    written: list[Path] = []

    for source in sorted(p for p in templates_dir.rglob("*") if p.is_file()):
        relative = source.relative_to(templates_dir)
        if should_skip(relative, flags):
            continue

        target = out_dir / render_path(relative, tokens)
        if target.exists() and not force:
            raise SpecError(f"refusing to overwrite {target} (pass --force)")

        target.parent.mkdir(parents=True, exist_ok=True)

        if source.suffix.lower() in BINARY_SUFFIXES:
            shutil.copyfile(source, target)
        else:
            try:
                blocked = apply_blocks(source.read_text(encoding="utf-8"), flags)
            except SpecError as exc:
                # Without the path, a stray marker reports a line number in an unnamed file.
                raise SpecError(f"{relative}: {exc}") from exc
            rendered = substitute(blocked, tokens)
            target.write_text(rendered, encoding="utf-8")

        written.append(target)

    return written


# ------------------------------------------------------------------- compile gate


def compile_check(out_dir: Path) -> int:
    """Fail loudly rather than hand back a scaffold that does not build.

    Offline first: every mx-* starter the templates use is already in ~/.m2 on a
    developer machine, and -o keeps a network hiccup from looking like a template
    bug. A genuine offline miss falls through to the online run.
    """
    for args in (["mvn", "-o", "-q", "test-compile"], ["mvn", "-q", "test-compile"]):
        print(f"$ {' '.join(args)}", file=sys.stderr)
        result = subprocess.run(args, cwd=out_dir, capture_output=True, text=True)
        if result.returncode == 0:
            return 0
        if args[1] == "-o" and "Cannot access" not in result.stderr and "offline" not in result.stderr.lower():
            # A real compiler error, not a missing artifact: retrying online will not help.
            print(result.stdout + result.stderr, file=sys.stderr)
            return result.returncode
        last = result

    print(last.stdout + last.stderr, file=sys.stderr)
    return last.returncode


# -------------------------------------------------------------------------- main


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--spec", required=True, type=Path, help="path to integration.yaml")
    parser.add_argument("--out", required=True, type=Path, help="directory to generate into")
    parser.add_argument("--force", action="store_true", help="overwrite existing files")
    parser.add_argument("--skip-compile", action="store_true", help="skip the mvn test-compile gate")
    parser.add_argument("--templates", type=Path, default=TEMPLATES_DIR)
    args = parser.parse_args(argv)

    try:
        context = build_context(parse_spec(args.spec.read_text(encoding="utf-8")))
        written = generate(args.templates, args.out, context, args.force)
        # The spec travels with the repo: the architecture skill and the SessionStart hook
        # both read it, and it is the only record of what the scaffold was told.
        spec_copy = args.out / "integration.yaml"
        if spec_copy.resolve() != args.spec.resolve():
            shutil.copyfile(args.spec, spec_copy)
            written.append(spec_copy)
    except (SpecError, OSError) as exc:
        print(f"scaffold: {exc}", file=sys.stderr)
        return 1

    print(f"Generated {len(written)} files into {args.out}")

    if args.skip_compile:
        return 0

    code = compile_check(args.out)
    if code != 0:
        print("scaffold: generated tree does not compile (see output above)", file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
