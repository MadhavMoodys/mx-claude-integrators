package com.moodys.maxsight.{{vendor}}.exception;

import org.springframework.http.HttpStatus;

import java.util.Map;

/** {{Vendor}} rejected the request as malformed (400, 422). Never retried. */
public class {{Vendor}}ValidationException extends {{Vendor}}APIException {

    public {{Vendor}}ValidationException(String message) {
        super(message, HttpStatus.UNPROCESSABLE_ENTITY, Map.of());
    }

    public {{Vendor}}ValidationException(String message, Map<String, Object> details) {
        super(message, HttpStatus.UNPROCESSABLE_ENTITY, details);
    }
}
