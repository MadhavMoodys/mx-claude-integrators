---
name: mx-integration-architecture
description: Use when working in any mx-<vendor> third-party integration repo - explains the api/connector module split, the HTTP status to exception mapping, credential indirection, and the comment policy that generated and edited code must follow.
---

# Moody's third-party integration architecture

Every `mx-<vendor>` integration is the same two-module Spring Boot 3.5 / Java 21
service, built on the `mx-framework-java` starters. `mx-newsedge` is the
reference implementation; this skill is the shape it settled into.

```
mx-<vendor>/
  <vendor>-api/         vendor-facing.  REST in, vendor HTTP out.
  <vendor>-connector/   orchestrator-facing.  Kafka in, Kafka out, inbox/outbox.
  infra/                terraform surface
  {build,artifacts,deployment,parameters}.yaml, Dockerfile
```

The connector is optional. A vendor that only serves synchronous requests from
the UI needs the api module alone.

## Read the reference for the module you are in

| File | Covers |
|---|---|
| `references/api-module.md` | layering, auth, retry, error mapping, config |
| `references/connector-module.md` | inbox/outbox, protobuf protocol, handlers, workers |
| `references/error-mapping.md` | the status→exception table and where it is enforced |
| `references/testing.md` | what a test must cover before the class is done |

## The rules that hold everywhere

**Layer boundaries.** `Controller → Service/Client → RestClient`. Controllers
carry no vendor logic; clients carry no HTTP-response shaping; the transformer is
pure and does no I/O. The connector never imports orchestrator protobuf types
outside its `protocol` package.

**Credentials are never literals.** Every secret is `${ENV_VAR}` in
`application.yml`, mapped from `parameters.yaml` as `$(Secret.NAME)`. A literal
API key, password or token in a `.java` or `.yml` file is blocked by a hook, and
that hook is right.

**Vendor failures become typed exceptions at the client boundary**, not
`RuntimeException` at the controller. See `references/error-mapping.md`.

**5xx retries, 4xx does not.** The api module retries with capped exponential
backoff via Resilience4j. The connector wraps 5xx in `RetriableException` so the
worker framework retries it, and rethrows 4xx so the caller can tell the
orchestrator the subscription is broken.

**Migrations are `V##__snake_case.sql`, sequential, never edited after merge.**

**Commits are `[M3PDS-123] type(scope): subject`**, subject ≤ 72 characters.

## Comment policy

This is measured from `mx-newsedge`, not invented. Density there tracks
non-obviousness: about 1% in a plain router, about 36% in the config whose
rejection policy deliberately deviates from `CallerRunsPolicy`. Almost every
inline comment is unique prose about a failure mode or a transaction boundary.

**Comment the why, never the what.** If a comment restates the line below it,
delete the comment.

Always comment:

- deliberate deviations from the obvious choice — `// No @Transactional -- deliberately.`
- transaction, concurrency and ordering constraints
- retry, rollback and dead-letter consequences
- vendor API quirks the code cannot express
- why a value was chosen, when the number looks arbitrary

Never comment:

- getters, setters, constructors
- self-evident control flow
- a restatement of the method name
- `@param x the x`

**Javadoc** goes on public types and on the public methods of controllers,
clients, configs and services: one line of purpose, plus contract notes — thrown
exceptions, nullability, threading — only where they are not obvious.

**TODOs carry a ticket:** `// TODO(M3PDS-123): map the vendor error body`. A bare
`// TODO:` is blocked.

**No commented-out code.** Git has it.

The `comment_lint` hook enforces the mechanical half of this on every Java edit.
It blocks on commented-out code, bare TODOs and filler javadoc, and warns without
blocking when a comment looks like it restates the next line — that last one is a
judgement call and the warning is sometimes wrong. Use judgement; do not write to
satisfy the linter.
