package com.moodys.maxsight.{{vendor}}.exception;

import org.springframework.http.HttpStatus;

import java.util.Map;

/** {{Vendor}} rejected our credentials or the token has gone stale (401, 403). */
public class {{Vendor}}AuthenticationException extends {{Vendor}}APIException {

    public {{Vendor}}AuthenticationException(String message) {
        super(message, HttpStatus.UNAUTHORIZED, Map.of());
    }

    public {{Vendor}}AuthenticationException(String message, Throwable cause) {
        super(message, HttpStatus.UNAUTHORIZED, Map.of(), null, cause);
    }

    public {{Vendor}}AuthenticationException(String message, Map<String, Object> details) {
        super(message, HttpStatus.UNAUTHORIZED, details);
    }
}
