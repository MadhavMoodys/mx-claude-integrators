package com.moodys.maxsight.{{vendor}}.service;

import com.moodys.maxsight.{{vendor}}.config.TokenManager;
import com.moodys.maxsight.{{vendor}}.config.{{Vendor}}RetryConfiguration;
import com.moodys.maxsight.{{vendor}}.exception.{{Vendor}}APIException;
import com.moodys.maxsight.{{vendor}}.exception.{{Vendor}}AuthenticationException;
import com.moodys.maxsight.{{vendor}}.exception.{{Vendor}}ConnectionException;
import com.moodys.maxsight.{{vendor}}.exception.{{Vendor}}RateLimitException;
import com.moodys.maxsight.{{vendor}}.exception.{{Vendor}}ServerException;
import com.moodys.maxsight.{{vendor}}.exception.{{Vendor}}TimeoutException;
import com.moodys.maxsight.{{vendor}}.exception.{{Vendor}}ValidationException;
import io.github.resilience4j.retry.Retry;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.HttpStatusCode;
import org.springframework.stereotype.Service;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClient;

import java.util.List;
import java.util.Map;
import java.util.function.BiFunction;
import java.util.function.Predicate;

/**
 * The only class that speaks HTTP to {{Vendor}}.
 *
 * <p>Every vendor status becomes a typed exception here, so no caller has to interpret a
 * status code and no two callers interpret one differently.
 */
@Slf4j
@Service
public class {{Vendor}}Client {

    private final RestClient restClient;
    private final TokenManager tokenManager;
    private final Retry retry;

    public {{Vendor}}Client(RestClient {{vendor}}RestClient,
                            TokenManager tokenManager,
                            @Qualifier({{Vendor}}RetryConfiguration.RETRY_BEAN_NAME) Retry retry) {
        this.restClient = {{vendor}}RestClient;
        this.tokenManager = tokenManager;
        this.retry = retry;
    }

    /**
     * Issues a GET against {{Vendor}} and returns the raw body.
     *
     * @throws {{Vendor}}APIException with a subtype matching the vendor's status
     */
    public String get(String endpoint) {
        // TODO(TICKET-000): replace with the real endpoints and response types once the
        // vendor's OpenAPI spec is in hand. Keep the status handling below unchanged.
        return Retry.decorateSupplier(retry, () -> call(endpoint)).get();
    }

    private String call(String endpoint) {
        try {
            RestClient.ResponseSpec spec = restClient.get()
                    .uri(endpoint)
                    .header(HttpHeaders.AUTHORIZATION, "Bearer " + tokenManager.getToken())
                    .retrieve();

            for (StatusHandlerRegistration registration : statusHandlers()) {
                spec = spec.onStatus(registration.matches(),
                        (request, response) -> {
                            throw registration.toException(endpoint, response.getStatusCode());
                        });
            }
            return spec.body(String.class);
        } catch (ResourceAccessException e) {
            // Never reached the vendor: DNS, TLS or socket. Retriable.
            throw new {{Vendor}}ConnectionException("Could not reach {{Vendor}} at " + endpoint, e);
        }
    }

    /**
     * The status → exception table, in one place. Order matters: the first predicate that
     * matches wins, so specific statuses precede the catch-all 5xx entry.
     */
    private List<StatusHandlerRegistration> statusHandlers() {
        return List.of(
                new StatusHandlerRegistration(
                        status -> status.value() == 401 || status.value() == 403,
                        false,
                        (message, details) -> new {{Vendor}}AuthenticationException(message, details)),
                new StatusHandlerRegistration(
                        status -> status.value() == 400 || status.value() == 422,
                        false,
                        (message, details) -> new {{Vendor}}ValidationException(message, details)),
                new StatusHandlerRegistration(
                        status -> status.value() == 404,
                        true,
                        (message, details) -> new {{Vendor}}APIException(message, HttpStatus.NOT_FOUND, details)),
                new StatusHandlerRegistration(
                        status -> status.value() == 429,
                        false,
                        (message, details) -> new {{Vendor}}RateLimitException(message, details)),
                new StatusHandlerRegistration(
                        status -> status.value() == 504,
                        false,
                        (message, details) -> new {{Vendor}}TimeoutException(message)),
                new StatusHandlerRegistration(
                        HttpStatusCode::is5xxServerError,
                        false,
                        (message, details) -> new {{Vendor}}ServerException(message, details)));
    }

    /**
     * One row of the status table: which statuses it claims, whether the failure is worth an
     * error-level log, and how to build the exception.
     */
    private record StatusHandlerRegistration(
            Predicate<HttpStatusCode> matches,
            boolean warnOnly,
            BiFunction<String, Map<String, Object>, {{Vendor}}APIException> factory) {

        {{Vendor}}APIException toException(String endpoint, HttpStatusCode status) {
            String message = "{{Vendor}} call to " + endpoint + " failed with " + status.value();
            Map<String, Object> details = Map.of("endpoint", endpoint, "statusCode", status.value());
            if (warnOnly) {
                log.warn(message);
            } else {
                log.error(message);
            }
            return factory.apply(message, details);
        }
    }
}
