package com.moodys.maxsight.{{vendor}}.exception;

import org.springframework.http.HttpStatus;

import java.util.Map;

/**
 * {{Vendor}} is asking for less traffic (429).
 *
 * <p>Not retried by the client: retrying is exactly what the vendor just asked us to stop.
 */
public class {{Vendor}}RateLimitException extends {{Vendor}}APIException {

    private static final String DEFAULT_MESSAGE = "{{Vendor}} rate limit exceeded";

    public {{Vendor}}RateLimitException() {
        this(DEFAULT_MESSAGE);
    }

    public {{Vendor}}RateLimitException(String message) {
        super(message, HttpStatus.TOO_MANY_REQUESTS, Map.of());
    }

    public {{Vendor}}RateLimitException(String message, Map<String, Object> details) {
        super(message, HttpStatus.TOO_MANY_REQUESTS, details);
    }
}
