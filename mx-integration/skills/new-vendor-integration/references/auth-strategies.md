# Auth strategies

Three shapes cover the vendors seen so far. The scaffold ships shape 1 because it is
the only one with a lifecycle; the other two are subtractions from it.

Whatever the shape: the credential lives in `parameters.yaml` as `$(Secret.NAME)`,
arrives as an environment variable, and appears in `application.yml` only as
`${ENV_VAR}`. Never a literal, never in a test that points at a real endpoint.

## 1. JWT from a token endpoint (NewsEdge; the generated default)

`TokenManager` posts credentials to the vendor's token endpoint, keeps the token in an
`AtomicReference`, decodes the `exp` claim, and schedules its own refresh a buffer
ahead of expiry.

Edit these three things and nothing else:

- the endpoint path, request body, and the field the token arrives in (one TODO)
- `<Vendor>Config` fields for whatever the vendor's token call needs
- `token-refresh-buffer-minutes` if the vendor's tokens are short-lived

Two details in the generated code that look wrong and are not:

- **The JWT signature is not verified.** This service just received the token from the
  vendor over TLS and is reading its own token's expiry, not accepting a third party's
  identity claim. There is nothing to verify against.
- **A boot-time token failure is logged, not rethrown.** A vendor outage at startup
  must not stop the pod from starting and answering `/internal/health`. The scheduled
  refresh recovers.

If the vendor's token is opaque rather than a JWT, `JWT.decode` throws. Replace
`scheduleNextRefresh` with a fixed interval from the `expires_in` field and drop the
`java-jwt` dependency.

## 2. Static API key header

No lifecycle: delete `TokenManager` and its test, and add the header once at the
client level rather than on each call.

```java
@Bean
RestClient {{vendor}}RestClient(MxRestClients clients, {{Vendor}}Config config) {
    return clients.client("{{vendor}}").mutate()
            .defaultHeader("X-API-Key", config.getApiKey())
            .build();
}
```

`<Vendor>Config.apiKey` binds from `${{{VENDOR}}_API_KEY}`. Also delete
`<Vendor>AuthenticationException`'s refresh-related uses — keep the class, since 401
and 403 still map to it.

## 3. OAuth2 client credentials

Keep `TokenManager`'s structure — it is the same problem — and change three things:

- POST `client_id` / `client_secret` / `grant_type=client_credentials` as
  `application/x-www-form-urlencoded`, not JSON
- read `access_token` and `expires_in` from the response
- schedule the refresh from `expires_in` minus the buffer, not from a JWT claim

Do not reach for `spring-security-oauth2-client` for this. It brings a filter chain and
a client-registration model that this service has no use for, and the hand-rolled
version is 40 lines that the team already maintains in every other integration.

## Testing auth

- Token refresh: `MockWebServer`, assert the header on the *next* request rather than
  poking at internal state.
- Expiry maths: call the scheduling method with a token whose `exp` is already inside
  the buffer window and assert the delay is floored, not negative.
- Never point an auth test at the vendor's real token endpoint, even with a valid
  credential. The write hook exempts `src/test` from the literal-secret check so that
  fixtures can carry fake credentials; that exemption is not permission to use a real one.
