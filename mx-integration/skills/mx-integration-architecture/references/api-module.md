# The api module

Vendor-facing. Takes REST requests from MaxSight, calls the vendor's HTTP API,
and returns a MaxSight-shaped response. Described against `newsedge-api`.

## Package layout

```
config/       properties, RestClient wiring, auth, retry, OpenAPI, CORS
constants/    error codes, vendor vocabularies
controller/   v1/ (public) and internal/ (service-to-service, health)
dto/          request/, response/, common/ -- the MaxSight-facing shapes
model/        JPA entities
repository/   Spring Data repositories
service/      the vendor client and the business services
transformer/  vendor JSON -> MaxSight DTO. Pure: no I/O, no Spring beans needed
util/         QueryBuilder and friends
exception/    the typed exception hierarchy + GlobalExceptionHandler
validation/   custom constraint annotations
```

## Layer boundaries

`Controller → Service/Client → RestClient`.

- Controllers validate input, delegate, and shape nothing.
- The client owns every HTTP concern: URL construction, headers, status handling.
- The transformer is **pure** — vendor JSON in, DTO out, no I/O. That is what
  makes it testable without a server.
- Repositories are plain Spring Data. Native queries need a comment justifying
  them.

## Configuration

`@ConfigurationProperties(prefix = "<vendor>")` on a `@Data` class, one field per
tunable, bound from `application.yml`:

```yaml
newsedge:
  base-url: ${NEWSEDGE_BASE_URL}
  api-key: ${NEWSEDGE_API_KEY}
  request-timeout: 30000
  token-refresh-buffer-minutes: 10
```

Every credential is `${ENV_VAR}`. The env var is populated from
`parameters.yaml` as `$(Secret.NEWSEDGE_API_KEY)`. Literals are blocked by a hook.

## HTTP client wiring

The starter builds the client; this module only names it.

```java
@Bean
public RestClient newsedgeRestClient(MxRestClients restClients) {
    return restClients.client("newsedge");
}
```

matched by `mx.http.client.clients.newsedge` in `application.yml`.

Calls that are independent of each other run on a **bounded** executor, not an
unbounded one: vendor calls block for up to the read timeout, so an unbounded
pool converts a slow upstream into unbounded parked threads. When the pool and
queue are full the work runs on the caller's thread — except after shutdown,
where `RestClientConfig` deliberately deviates from
`ThreadPoolExecutor.CallerRunsPolicy` and rejects loudly, because that policy
drops the task silently and a `CompletableFuture` caller would then block forever
on a future that never completes.

## Auth

The variation point between vendors. Three shapes, all living in `config/`:

| Shape | Implementation |
|---|---|
| JWT token endpoint | `TokenManager` — POST `/auth/token`, parse the JWT `exp`, schedule a refresh with a buffer (default 10 minutes), refresh on `ApplicationReadyEvent` |
| Static API key header | a `ClientHttpRequestInterceptor` that adds the header; no lifecycle |
| OAuth2 client credentials | Spring Security's `OAuth2AuthorizedClientManager` |

`TokenManager` decodes the JWT **without verifying the signature** — it is
reading the expiry of a token the vendor just handed it over TLS, not trusting a
third party's claim. That is worth the comment it carries in the code; copy the
reasoning, not just the call.

## Retry

Resilience4j, configured in `application.yml`, applied at the client:

```yaml
resilience4j.retry.instances.newsedgeApi:
  max-attempts: 5
  wait-duration: 1s
  exponential-backoff-multiplier: 2
  randomized-wait-factor: 0.5
```

Retry 5xx, connection failures and timeouts. Never retry 4xx — the request is
wrong and will stay wrong. Randomisation matters: without it, a vendor outage
produces a synchronised retry storm from every pod.

## Error handling

See `error-mapping.md`. The rule in one line: the client converts every vendor
status into a typed exception, and `GlobalExceptionHandler` converts those into
the MaxSight error response. Nothing in between catches and re-wraps.

## Health

`/internal/health` backed by `HealthService`, wired to the liveness and readiness
probes in `deployment.yaml`. Readiness must fail when the vendor is unreachable
*and* the service cannot serve anything useful without it — not merely when a
single call failed.
