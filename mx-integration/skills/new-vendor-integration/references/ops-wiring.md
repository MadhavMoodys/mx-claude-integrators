# Ops wiring: which file owns which value

Five files at the repo root, plus `infra/`. They overlap enough that putting a value
in the wrong one usually still deploys — and then fails in an environment nobody
tested. This is the ownership map.

| File | Owns | Never contains |
|---|---|---|
| `build.yaml` | build targets: the Java module list, the Docker images and their `BINARY_NAME` build args | env values, secrets |
| `artifacts.yaml` | pipeline stages, service name, K8s resource/HPA overrides | per-environment values |
| `parameters.yaml` | **every** config value and secret, as `$(Config.X)` / `$(Secret.X)` / resource lookups | anything the code reads directly |
| `deployment.yaml` | which config and secret groups each container mounts, probes, replicas | credential literals |
| `Dockerfile` | one image, parameterised by `BINARY_NAME` for both modules | module-specific logic |
| `infra/infra.yaml` | databases, Kafka service accounts, anything terraform creates | application config |

## The chain a credential travels

```
parameters.yaml   {{VENDOR}}_API_KEY: "$(Secret.{{VENDOR}}_API_KEY)"
      ↓ mounted by name in deployment.yaml
container env     {{VENDOR}}_API_KEY=…
      ↓
application.yml   api-key: ${{{VENDOR}}_API_KEY}
      ↓
<Vendor>Config    getApiKey()
```

Every link is by name, and nothing in the repo holds the value. A literal anywhere in
a `.java` or `.yml` is denied by the write hook, and the denial is correct even when
the value is a throwaway — the file outlives the intent.

## Adding a new environment variable

1. `parameters.yaml` — add to the right group (`{{vendor}}-api-configs` for plain
   config, `{{vendor}}-api-secrets` for anything sensitive).
2. `deployment.yaml` — only if you added a whole new group; existing groups are
   already mounted.
3. `application.yml` — bind it as `${NAME}` with a local-dev default if one is safe.
   No default for a secret: a missing secret must fail the boot, not silently run
   against nothing.
4. `<Vendor>Config` — add the field so it is typed and validated at startup rather
   than read as a raw string somewhere deep.

## Connector-only additions

With `connector: true`, `parameters.yaml` gains Kafka SASL credentials and a database
URL, both read from terraform resource outputs
(`@!Resources.GetResource('mx-{{vendor}}-db')…`). Those resources must exist in
`infra/infra.yaml` first; a lookup against a resource that was never created fails at
deploy time with a message that does not mention the missing resource.

## Health and probes

Both modules expose `/internal/health` (`management.endpoints.web.base-path:
/internal`, not `/actuator`). Liveness and readiness in `deployment.yaml` point there.
If you change the base path, change both — a probe pointed at a 404 restarts a
perfectly healthy pod on a loop.

## The gate the pipeline enforces

After the build, JFrog runs **Docker PR repository scan descendants**. Critical and
High findings must be triaged there before merge. The `vuln_check.py` hook gives you a
local heads-up on pom edits; it is not a substitute, and a clean local run says
nothing about the base image.
