package com.moodys.maxsight.{{vendor}}.config;

import com.auth0.jwt.JWT;
import com.auth0.jwt.interfaces.DecodedJWT;
import com.moodys.maxsight.{{vendor}}.exception.{{Vendor}}AuthenticationException;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.scheduling.TaskScheduler;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;

import java.time.Duration;
import java.time.Instant;
import java.util.Map;
import java.util.concurrent.atomic.AtomicReference;

/**
 * Holds the {{Vendor}} bearer token and refreshes it before it expires.
 *
 * <p>Only for vendors that issue a JWT from a token endpoint. A vendor that takes a static
 * API key header needs no lifecycle at all — delete this class and add an interceptor
 * instead; see the auth-strategies reference.
 */
@Slf4j
@Component
public class TokenManager {

    private final RestClient restClient;
    private final {{Vendor}}Config config;
    private final TaskScheduler scheduler;
    private final AtomicReference<String> token = new AtomicReference<>();

    public TokenManager(RestClient {{vendor}}RestClient, {{Vendor}}Config config, TaskScheduler scheduler) {
        this.restClient = {{vendor}}RestClient;
        this.config = config;
        this.scheduler = scheduler;
    }

    /**
     * Fetches the first token once the context is up, so a startup failure surfaces in the
     * logs rather than on the first user request.
     */
    @EventListener(ApplicationReadyEvent.class)
    public void refreshOnStartup() {
        try {
            refresh();
        } catch ({{Vendor}}AuthenticationException e) {
            // Deliberately not rethrown: a vendor outage at boot should not stop the pod from
            // starting and serving /internal/health. The scheduled retry picks it up.
            log.error("Initial {{Vendor}} token fetch failed; will retry on schedule", e);
        }
    }

    /**
     * @return the current bearer token
     * @throws {{Vendor}}AuthenticationException if no token has been obtained yet
     */
    public String getToken() {
        String current = token.get();
        if (current == null) {
            throw new {{Vendor}}AuthenticationException("No {{Vendor}} token available");
        }
        return current;
    }

    /** Fetches a new token and schedules the next refresh from its expiry claim. */
    public synchronized void refresh() {
        // TODO(TICKET-000): match the vendor's token endpoint — path, body shape, and the
        // field the token arrives in.
        Map<String, Object> response;
        try {
            response = restClient.post()
                    .uri("/auth/token")
                    .body(Map.of(
                            "username", config.getUsername(),
                            "password", config.getPassword()))
                    .retrieve()
                    .body(Map.class);
        } catch (RestClientException e) {
            throw new {{Vendor}}AuthenticationException("{{Vendor}} refused to issue a token", e);
        }

        if (response == null || !(response.get("token") instanceof String issued)) {
            throw new {{Vendor}}AuthenticationException("{{Vendor}} token response had no token field");
        }

        token.set(issued);
        scheduleNextRefresh(issued);
    }

    /**
     * Decodes the token <em>without verifying its signature</em>. We are reading the expiry of
     * a token this service just received from the vendor over TLS, not accepting a third
     * party's claim about identity, so there is nothing to verify against.
     */
    private void scheduleNextRefresh(String issued) {
        DecodedJWT decoded = JWT.decode(issued);
        Instant expiry = decoded.getExpiresAt() != null
                ? decoded.getExpiresAt().toInstant()
                : Instant.now().plus(Duration.ofHours(1));

        int bufferMinutes = config.getTokenRefreshBufferMinutes() == null
                ? 10
                : config.getTokenRefreshBufferMinutes();
        Instant when = expiry.minus(Duration.ofMinutes(bufferMinutes));

        // A token that is already inside the buffer window would schedule in the past and
        // spin; floor it to a short delay instead.
        Instant floored = when.isAfter(Instant.now()) ? when : Instant.now().plusSeconds(30);
        scheduler.schedule(this::refresh, floored);
        log.info("Next {{Vendor}} token refresh scheduled for {}", floored);
    }
}
