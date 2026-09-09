# Error mapping

One table, enforced in one place. Every vendor integration reproduces it.

## Status → exception

Registered as a list of `(predicate, log behaviour, exception factory)` in the
client, so "read the body, extract the message, log, throw" lives in exactly one
helper rather than once per status.

| Vendor status | Exception | Log level | Retried? |
|---|---|---|---|
| 401, 403 | `<Vendor>AuthenticationException` | error | no |
| 400, 422 | `<Vendor>ValidationException` | error | no |
| 404 | `<Vendor>APIException` (`HttpStatus.NOT_FOUND`) | warn | no |
| 429 | `<Vendor>RateLimitException` | error | no — the vendor is asking for less traffic |
| 504 | `<Vendor>TimeoutException` | error | yes |
| other 5xx | `<Vendor>ServerException` | error | yes |
| socket/connect failure | `<Vendor>ConnectionException` | error | yes |
| unreadable/unparseable body | `<Vendor>ResponseException` | error | no |

404 is a warn, not an error: an absent resource is usually a caller's question,
not a fault in the integration.

Every exception carries a context map — at minimum `endpoint` and `statusCode` —
so the log line and the error response say *which call* failed without stitching
threads together.

## The hierarchy

```
<Vendor>APIException            (base, carries HttpStatus + context map)
├── <Vendor>AuthenticationException
├── <Vendor>ValidationException
├── <Vendor>RateLimitException
├── <Vendor>TimeoutException
├── <Vendor>ServerException
├── <Vendor>ConnectionException
└── <Vendor>ResponseException
```

`GlobalExceptionHandler` (`@RestControllerAdvice`) maps each to the outbound
status and body. Add a handler method when you add an exception; an exception
with no handler surfaces as a 500 with no useful body.

## There are two retry layers, not one

`mx-http-client` puts Apache HttpClient 5 on the classpath, so Spring's `RestClient`
selects `HttpComponentsClientHttpRequestFactory` over the JDK client. Its default
`DefaultHttpRequestRetryStrategy` re-sends **429 and 503 exactly once**, underneath
Resilience4j and invisible to it. With the template's five Resilience4j attempts, a
rate-limited vendor can therefore see up to ten calls for one logical request.

Two consequences worth carrying:

- When sizing backoff against a vendor's rate limit, budget for the doubling.
- In tests, `MockWebServer.enqueue()` is not enough for a 429 or 503 case: the first
  attempt consumes the queued response and the transport's own retry then hangs until
  the 3-minute socket timeout, so the test fails as a connection error instead of the
  status you were asserting. Use a `Dispatcher` that answers every request the same
  way. The generated `<Vendor>ClientTest` already does this.

## Connector-side

The connector's facade re-reads the api module's status, not the vendor's:

- **5xx** → wrap in `RetriableException`, let the worker framework retry with backoff
- **4xx** → rethrow unchanged; the handler tells the orchestrator the subscription
  is broken via `end_of_stream` with a JSON error body
- anything else thrown → dead-lettered by the framework

That split is the whole contract. A 4xx that gets wrapped as retriable becomes an
infinite retry loop against a request that can never succeed; a 5xx that gets
rethrown dead-letters a subscription over a transient blip.

## What not to do

- Do not catch a typed exception in a controller to log it. The advice logs.
- Do not convert vendor errors to `null` or an empty result. A caller cannot tell
  "no data" from "the call failed".
- Do not put the vendor's raw error body in the outbound response. Extract the
  message; the body may carry request echoes and credentials.
