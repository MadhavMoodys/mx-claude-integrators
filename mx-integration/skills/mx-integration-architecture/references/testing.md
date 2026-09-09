# Testing

JUnit 5 + Mockito. `mockwebserver` for the vendor HTTP surface, `rest-assured`
for the controller surface. Tests mirror the main package tree.

## What each layer owes

| Layer | Must be covered |
|---|---|
| Client | one test per status in the mapping table — 401, 400, 404, 429, 504, 5xx, connect failure — asserting the **exception type**, not just that something threw |
| Transformer | vendor JSON fixture in, DTO out. Pure, so no Spring context. Include a malformed and a missing-field fixture |
| Controller | happy path plus the validation failures, through `rest-assured` or `@WebMvcTest` |
| GlobalExceptionHandler | every exception type maps to its intended status and body |
| Auth | token refresh scheduling, expiry parsing, and the failure path where the vendor refuses to issue a token |
| Connector handlers | the `m-type` routing, the version guard, and the 4xx/5xx split at the facade |
| Repositories | only where a query is non-trivial. A generated `findById` needs no test |

## Rules

**Assert the type, not the message.** `assertThrows(VendorRateLimitException.class, …)`
survives a reworded log line; asserting on the string does not.

**Vendor fixtures are real captured responses**, trimmed and de-identified, kept
under `src/test/resources`. A hand-written approximation of the vendor's JSON
tests your imagination.

**Fake credentials belong in tests and only in tests.** The secret-guard hook
deliberately exempts `src/test/`; that exemption is not permission to point a
test at a real credential.

**No sleeps.** Scheduled refresh is tested by injecting a `TaskScheduler` and
asserting the scheduled delay, not by waiting for it.

**A test that needs a running database uses the repository test pattern already
in the connector module**, not a mock of Spring Data.

## Running them

```
mvn -q test -pl <vendor>-api
mvn -q test                     # whole reactor
```

The Stop hook runs the tests for whatever modules the turn touched, so a turn
cannot end on red. If it reports a failure, that is the same command you can run
yourself.
