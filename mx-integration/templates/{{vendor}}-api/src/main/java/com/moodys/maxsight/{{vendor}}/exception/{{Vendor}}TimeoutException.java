package com.moodys.maxsight.{{vendor}}.exception;

import org.springframework.http.HttpStatus;

import java.util.Map;

/** {{Vendor}} did not answer in time (504, or a read timeout). Retriable. */
public class {{Vendor}}TimeoutException extends {{Vendor}}APIException {

    public {{Vendor}}TimeoutException(String message) {
        super(message, HttpStatus.GATEWAY_TIMEOUT, Map.of());
    }

    public {{Vendor}}TimeoutException(String message, Throwable cause) {
        super(message, HttpStatus.GATEWAY_TIMEOUT, Map.of(), null, cause);
    }
}
