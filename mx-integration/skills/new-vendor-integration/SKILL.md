---
name: new-vendor-integration
description: Use when starting a new third-party vendor integration - interviews for the vendor spec, writes integration.yaml, runs the scaffolder, and drives filling in the vendor-specific request/response semantics.
---

# Starting a new vendor integration

Scaffold the mechanical half, then fill the half no template can know.

Generated for you: auth, retry, status→exception mapping, the exception hierarchy,
config binding, the HTTP client wiring, health endpoints, ops files, and tests for
all of it. Left as ticket-tagged TODOs: the vendor's request shapes, response DTOs,
the transformer, and the query builder. That split is a limit, not a shortcut — the
scaffolder cannot invent the vendor's API semantics, and pretending otherwise would
produce code that compiles and then lies.

Read `mx-integration-architecture` first if you have not. This skill assumes it.

## 1. Interview

Ask these, one at a time. Do not guess a value that ends up in a package name.

| Question | Feeds |
|---|---|
| Vendor short name, lowercase letters/digits only | `{{vendor}}` — Java package, artifactId |
| Display name | `{{Vendor}}` — class-name prefix, javadoc |
| JIRA ticket for this work | every generated TODO, and the commit hook |
| Base URL (per environment if they differ) | `application.yml`, `parameters.yaml` |
| Auth: JWT token endpoint, static API key, or OAuth2 client credentials | `TokenManager` |
| Endpoints to call, and what each returns | DTOs, client methods |
| Does the orchestrator drive it over Kafka? | `connector: true/false` |
| Rate limits and documented error codes | retry config, error mapping |

On auth, read `references/auth-strategies.md` before writing anything: the template
ships the JWT-refresh shape, and the other two are edits to it, not rewrites.

If they hand you an OpenAPI spec, read it instead of asking about endpoints. It also
answers the response-shape questions you would otherwise ask in step 4.

## 2. Write `integration.yaml`

At the new repo root. Format in `references/spec-format.md`; example in
`examples/acme.yaml`.

```yaml
vendor: acme
display_name: Acme
ticket: M3PDS-999
connector: false
```

`connector: false` is the right default. A vendor that only answers synchronous
requests from the UI does not need the connector module, and adding it later is a
smaller job than deleting a module nobody wired up.

## 3. Scaffold

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/scaffold.py" --spec integration.yaml --out .
```

It refuses to overwrite existing files without `--force`, and it runs
`mvn test-compile` at the end. If that fails, stop and fix the scaffold output —
do not start filling in TODOs on a tree that does not build.

With `connector: true`, the connector module arrives as a **partial** skeleton plus
`PORTING.md`. Follow that document; it lists the classes to port from `mx-newsedge`
in compile order and the pom entries deliberately left out.

## 4. Fill in the vendor semantics

```bash
grep -rn "TODO(" --include=*.java --include=*.yml .
```

Work them in this order, because each one narrows the next:

1. **`<Vendor>Config`** — the fields the vendor actually needs. Delete the ones it
   does not; an unused config property is a question in every later code review.
2. **`TokenManager`** — match the vendor's auth shape (see the reference).
3. **Request DTOs and `QueryBuilder`** — how a query is expressed on the wire.
4. **Response DTOs** — records, one per response shape, nullable fields marked.
5. **`ResponseTransformer`** — vendor JSON → the MaxSight shape. Keep it pure: no
   HTTP, no clock, no randomness. It is the one class that is cheap to test hard.
6. **`<Vendor>Client`** — the call methods. The status mapping is already written;
   add methods, do not re-map statuses per call.

Add a test alongside each, not at the end. The testing reference in the
`mx-integration-architecture` skill sets the bar; the generated `<Vendor>ClientTest` and `ResponseTransformerTest` are
the patterns to extend.

## 5. Ops

`build.yaml`, `artifacts.yaml`, `deployment.yaml`, `parameters.yaml`, `Dockerfile`
and `infra/` come out named and wired. What still needs a human:

- Real secret names in `parameters.yaml` as `$(Secret.NAME)` — and nowhere else.
- Environment-specific base URLs in `deployment.yaml`.
- The infra repo entry, if this vendor needs its own database or topics.

Read `references/ops-wiring.md` for which file owns which value. The rule that
matters: a credential exists in `parameters.yaml` and reaches code only as
`${ENV_VAR}`. The write hook denies a literal, and it is right to.

## 6. Close it out

Run the `integration-release-checklist` skill before opening the PR.
