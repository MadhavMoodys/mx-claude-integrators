package com.moodys.maxsight.{{vendor}}.exception;

import org.springframework.http.HttpStatus;

import java.util.Map;

/** The call never reached {{Vendor}} — DNS, TLS, or socket failure. Retriable. */
public class {{Vendor}}ConnectionException extends {{Vendor}}APIException {

    public {{Vendor}}ConnectionException(String message, Throwable cause) {
        super(message, HttpStatus.SERVICE_UNAVAILABLE, Map.of(), null, cause);
    }
}
