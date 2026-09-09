# mx-integration-plugin

A Claude Code plugin that scaffolds, documents and guards Moody's MaxSight
third-party vendor integrations.

`mx-newsedge` was the first of these, and it settled into a repeatable shape: a
vendor-facing API module, an orchestrator-facing connector module, and a fixed ops
surface. This plugin packages that shape — the module split, the status→exception
mapping, credential indirection, the commit and comment rules — so the next vendor
starts from it instead of from a copy-paste.

## What is in here

```
.claude-plugin/marketplace.json   # this repo is the marketplace
mx-integration/                   # the plugin itself
  .claude-plugin/plugin.json
  commands/new-integration.md     # /new-integration <vendor>
  skills/
    mx-integration-architecture/  # the always-on context skill
    new-vendor-integration/       # the workflow: interview -> scaffold -> fill in
    integration-release-checklist/
  templates/                      # {{vendor}}-tokenised source tree
  scripts/scaffold.py
  hooks/                          # seven hooks + hooks.json
  tests/                          # python3 -m unittest, no third-party deps
```

Nothing here is published outside the org. A "marketplace" is just the
`marketplace.json` above; Claude Code reads it straight from this repo.

## Installing it in a vendor repo

The scaffolder writes a `.claude/settings.json` into each new vendor repo that
registers this marketplace and enables the plugin, so a developer who clones that
repo and trusts the folder gets the skills and hooks with **no command to run**.

To add it to a repo by hand:

```bash
claude plugin marketplace add moodys/mx-integration-plugin
claude plugin install mx-integration@mx-integration
```

## Bootstrapping a new vendor repo

```bash
mkdir ../mx-acme && cd ../mx-acme && git init
cat > integration.yaml <<'YAML'
vendor: acme
display_name: Acme
ticket: M3PDS-999
connector: false
YAML
python3 ../mx-integration-plugin/mx-integration/scripts/scaffold.py \
  --spec integration.yaml --out .
```

That generates the repo and runs `mvn test-compile`. Open Claude Code there, trust
the folder, and `/new-integration acme` picks up from the interview.

`connector: false` is the right default — a vendor that only answers synchronous
requests does not need the connector module, and adding it later is a smaller job
than deleting a module nobody wired up.

## Working on the plugin itself

```bash
claude --plugin-dir ./mx-integration    # load without installing
/reload-plugins                          # after each edit
claude plugin validate ./mx-integration
python3 -m unittest discover -s mx-integration/tests -t mx-integration/tests
```

## Turning the hooks off

`MX_HOOKS_DISABLED=1` bypasses every hook. It exists for the case where a hook is
wrong and blocking real work — not as a way past a finding. If you used it, say so
in the PR: the checks it skipped are the ones the release checklist exists to
guarantee.

## Scope limit, stated plainly

Scaffolding cannot invent a vendor's API semantics. Auth, retry, error mapping, the
exception hierarchy, config binding, HTTP wiring, health endpoints, ops files and
tests for all of it are generated. The request DTOs, response DTOs, the response
transformer and the query builder come out as compiling skeletons with
ticket-tagged TODOs, to be filled from the vendor's OpenAPI spec.

The connector module is a **partial** skeleton plus a `PORTING.md` procedure, not a
full template set. The reference connector is ~76 files bound to `mx-worker`,
`mx-consumer` and the orchestrator protobuf contract; templating that would produce
code that compiles and then misbehaves on the first real message.
