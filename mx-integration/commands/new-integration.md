---
description: Start a new mx-<vendor> third-party integration - interview, write integration.yaml, scaffold, and fill in the vendor semantics.
argument-hint: [vendor short name]
---

Start a new third-party vendor integration for: **$1**

Use the `new-vendor-integration` skill and follow it in order. Read the
`mx-integration-architecture` skill first if it is not already in context.

Before anything else:

1. Check whether `integration.yaml` already exists at the repo root. If it does, this
   repo has been scaffolded — do not re-run the scaffolder. Say so and ask what the
   user actually wants to change.
2. Confirm the working directory is the new vendor's repo, not `mx-newsedge`. The
   scaffolder writes into the directory it is given and refuses to overwrite, but a
   half-written tree in the wrong repo is still a mess to unpick.

Then interview for the spec. If `$1` is empty, the vendor short name is the first
thing to ask for. Do not guess values that end up in a package name.

Scaffolding is one command and it runs `mvn test-compile` at the end:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/scaffold.py" --spec integration.yaml --out .
```

If it fails, fix the cause before touching any generated file.
