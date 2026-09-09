package com.moodys.maxsight.{{vendor}}.exception;

import org.springframework.http.HttpStatus;

import java.util.Map;

/**
 * {{Vendor}} answered 2xx with a body this service cannot read.
 *
 * <p>Not retriable: the same request would produce the same unreadable body.
 */
public class {{Vendor}}ResponseException extends {{Vendor}}APIException {

    public {{Vendor}}ResponseException(String message, Throwable cause) {
        super(message, HttpStatus.BAD_GATEWAY, Map.of(), null, cause);
    }

    public {{Vendor}}ResponseException(String message, Map<String, Object> details) {
        super(message, HttpStatus.BAD_GATEWAY, details);
    }
}
