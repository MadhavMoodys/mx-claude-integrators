package com.moodys.maxsight.{{vendor}}.service;

import com.moodys.maxsight.{{vendor}}.config.TokenManager;
import com.moodys.maxsight.{{vendor}}.config.{{Vendor}}Config;
import com.moodys.maxsight.{{vendor}}.config.{{Vendor}}RetryConfiguration;
import com.moodys.maxsight.{{vendor}}.exception.{{Vendor}}APIException;
import com.moodys.maxsight.{{vendor}}.exception.{{Vendor}}AuthenticationException;
import com.moodys.maxsight.{{vendor}}.exception.{{Vendor}}RateLimitException;
import com.moodys.maxsight.{{vendor}}.exception.{{Vendor}}ServerException;
import com.moodys.maxsight.{{vendor}}.exception.{{Vendor}}TimeoutException;
import com.moodys.maxsight.{{vendor}}.exception.{{Vendor}}ValidationException;
import io.github.resilience4j.retry.Retry;
import io.github.resilience4j.retry.RetryConfig;
import io.github.resilience4j.retry.RetryRegistry;
import okhttp3.mockwebserver.Dispatcher;
import okhttp3.mockwebserver.MockResponse;
import okhttp3.mockwebserver.MockWebServer;
import okhttp3.mockwebserver.RecordedRequest;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.web.client.RestClient;

import java.io.IOException;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

/**
 * One case per row of the status table. These assert the exception <em>type</em>: a
 * reworded message must not break them, but a status silently mapping to the wrong class
 * must.
 */
class {{Vendor}}ClientTest {

    private MockWebServer server;
    private {{Vendor}}Client client;

    @BeforeEach
    void setUp() throws IOException {
        server = new MockWebServer();
        server.start();

        {{Vendor}}Config config = new {{Vendor}}Config();
        config.setRetryMaxWaitSeconds(1);

        // One attempt: these tests are about mapping, not about backoff.
        RetryRegistry registry = RetryRegistry.of(
                Map.of({{Vendor}}RetryConfiguration.RETRY_INSTANCE_NAME,
                        RetryConfig.custom().maxAttempts(1).build()));
        Retry retry = {{Vendor}}RetryConfiguration.createCappedRetry(registry, config);

        TokenManager tokenManager = mock(TokenManager.class);
        when(tokenManager.getToken()).thenReturn("test-token");

        RestClient restClient = RestClient.builder()
                .baseUrl(server.url("/").toString())
                .build();

        client = new {{Vendor}}Client(restClient, tokenManager, retry);
    }

    @AfterEach
    void tearDown() throws IOException {
        server.shutdown();
    }

    /**
     * Answers every request with the same response, rather than enqueuing one.
     *
     * <p>Apache HttpClient 5 — which {@code mx-http-client} puts on the classpath, so
     * {@code RestClient} picks it over the JDK client — retries 429 and 503 once on its own,
     * beneath Resilience4j. A single enqueued response leaves that retry unanswered and the
     * test blocks until the 3-minute socket timeout, failing as a connection error instead of
     * the status being tested. A dispatcher keeps the assertion about mapping regardless of
     * how many times the transport decides to ask.
     */
    private void alwaysRespond(int status, String body) {
        server.setDispatcher(new Dispatcher() {
            @Override
            public MockResponse dispatch(RecordedRequest request) {
                return new MockResponse().setResponseCode(status).setBody(body);
            }
        });
    }

    @Test
    void returnsTheBodyOnSuccess() {
        alwaysRespond(200, "{\"results\":[]}");

        assertEquals("{\"results\":[]}", client.get("/search"));
    }

    @Test
    void unauthorizedBecomesAuthenticationException() {
        alwaysRespond(401, "");

        assertThrows({{Vendor}}AuthenticationException.class, () -> client.get("/search"));
    }

    @Test
    void badRequestBecomesValidationException() {
        alwaysRespond(400, "");

        assertThrows({{Vendor}}ValidationException.class, () -> client.get("/search"));
    }

    @Test
    void notFoundStaysOnTheBaseTypeWithNotFoundStatus() {
        alwaysRespond(404, "");

        {{Vendor}}APIException thrown =
                assertThrows({{Vendor}}APIException.class, () -> client.get("/search"));

        assertEquals(HttpStatus.NOT_FOUND, thrown.getHttpStatus());
    }

    @Test
    void tooManyRequestsBecomesRateLimitException() {
        alwaysRespond(429, "");

        assertThrows({{Vendor}}RateLimitException.class, () -> client.get("/search"));
    }

    @Test
    void gatewayTimeoutBecomesTimeoutException() {
        alwaysRespond(504, "");

        assertThrows({{Vendor}}TimeoutException.class, () -> client.get("/search"));
    }

    @Test
    void otherServerErrorsBecomeServerException() {
        alwaysRespond(503, "");

        assertThrows({{Vendor}}ServerException.class, () -> client.get("/search"));
    }

    @Test
    void everyFailureCarriesTheEndpointAndStatus() {
        alwaysRespond(500, "");

        {{Vendor}}APIException thrown =
                assertThrows({{Vendor}}APIException.class, () -> client.get("/search"));

        assertEquals("/search", thrown.getDetails().get("endpoint"));
        assertEquals(500, thrown.getDetails().get("statusCode"));
    }
}
