---
name: integration-release-checklist
description: Use before opening a PR in any mx-<vendor> integration repo - the security, schema, commit, test and comment gates that must pass, including the mandatory JFrog scan review.
---

# Release checklist

Walk it top to bottom before the PR. Report each item as pass or fail with the
evidence — a command's output, a file and line. "Looks fine" is not a result.

Some of these are also enforced by hooks, which means they were checked as you typed.
Verify them anyway: hooks can be disabled with `MX_HOOKS_DISABLED=1`, and a branch that
was worked on with them off looks identical to one that was not.

## 1. Secrets

```bash
grep -rnE '(api-key|password|token|secret)\s*:\s*[^$#]' --include=*.yml --include=*.yaml --include=*.java . | grep -v /src/test/
```

Every hit must be `${ENV_VAR}`. A credential lives in `parameters.yaml` as
`$(Secret.NAME)` and nowhere else.

Then check the test exemption was not abused: no test points at a real vendor endpoint
with a real credential. Fake fixtures are fine and are why the exemption exists.

## 2. Vulnerabilities

- Local: `mvn -pl <modules> org.owasp:dependency-check-maven:check` if any pom changed.
- **Mandatory and authoritative: the JFrog "Docker PR repository scan descendants"
  review.** Every Critical and High must be triaged there before merge, regardless of
  what the local scan said. It covers the base image, which the local scan does not.

If a finding is accepted rather than fixed, the PR says so and says why.

## 3. Schema

- Migrations are `V##__snake_case.sql`, sequential, no gaps, no duplicate version.
- **No edit to a migration that has been applied anywhere.** Flyway compares
  checksums; a changed one is a failed deploy, not a re-run. Add the next version.
- `ddl-auto` is still `validate`.
- Entities match the migration — column names, nullability, types.

## 4. Commits

```bash
git log --oneline origin/master..HEAD
```

Every subject: `[PROJ-123] type(scope): subject`, subject ≤ 72 chars, JIRA key real and
matching the branch's work. No "wip", no "fix stuff", no fixups left unsquashed.

## 5. Tests

```bash
mvn -q test
```

Green, and:

- a test exists for each class added or meaningfully changed
- error paths are covered, not just the happy path — the status→exception mapping in
  particular
- the transformer's tests use real vendor response fixtures, not hand-written ideals
- no `@Disabled` added without a ticket in the annotation
- no test that reaches the network

## 6. Config and ops

- `application.yml` binds every new env var, with a safe local default for config and
  **no default for a secret** — a missing secret must fail the boot.
- `parameters.yaml` carries anything new, in the right group.
- Liveness and readiness still point at `/internal/health`.
- New terraform resources exist in `infra/infra.yaml` before anything looks them up.

## 7. Comments

The pass most likely to be skipped, so do it explicitly:

```bash
grep -rn "TODO" --include=*.java . | grep -v "TODO("
```

- Every remaining TODO carries a ticket: `// TODO(M3PDS-123): …`. Bare ones are a fail.
- No commented-out code. Git has it.
- No comment that restates the line below it.
- The non-obvious decisions made during this work are actually explained — a deliberate
  deviation, a transaction boundary, a vendor quirk the code cannot express. If you
  argued about it in review or with yourself, it needs a comment.
- Javadoc on public types and on public methods of controllers, clients, configs and
  services. One line of purpose; contract notes only where non-obvious. No
  `@param x the x`.

## 8. Scaffold leftovers

For a newly scaffolded repo, confirm nothing generated was left unread:

- No `TODO(TICKET-000)` — the scaffolder writes the real ticket, so this string means a
  file was added by hand from a template.
- No unused `<Vendor>Config` fields.
- `README.md`'s "what still needs filling in" section is gone or accurate.
- `integration.yaml` still describes the repo.

## Reporting

Summarise as a table of item → pass/fail → evidence. If anything failed, say so plainly
and do not open the PR. If a hook was disabled at any point during the work, say that
in the PR description.
