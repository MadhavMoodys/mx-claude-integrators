# Conventions

The rules that hold in every `mx-<vendor>` repo. Each is one line here on
purpose — the reasoning, the tables and the worked examples live in the
`mx-integration-architecture` skill. **When this file and that skill disagree,
the skill is correct**; fix this file.

- **Layering is `Controller → Service/Client → RestClient`.** Controllers carry
  no vendor logic; clients carry no HTTP-response shaping; the transformer is
  pure and does no I/O.
- **No credential is ever a literal.** Secrets are `${ENV_VAR}` in
  `application.yml`, mapped from `parameters.yaml` as `$(Secret.NAME)`.
- **Vendor failures become typed exceptions at the client boundary**, per the
  status→exception mapping — not `RuntimeException` at the controller.
- **5xx retries, 4xx does not.** The connector wraps 5xx in `RetriableException`
  and rethrows 4xx.
- **Migrations are `V##__snake_case.sql`**, sequential, and are never edited
  after merge.
- **Commits are `[M3PDS-123] type(scope): subject`**, subject ≤ 72 characters.
- **Comment the why, never the what.** Javadoc public types and the public
  methods of controllers, clients, configs and services. TODOs carry a ticket
  key. No commented-out code.
- **Constructor injection, not `@Autowired` fields.** Controllers return DTOs,
  never JPA entities.

Hooks enforce the mechanical half of these and will block the write. A hook that
fires is telling you something true; fix the cause rather than working around it.
