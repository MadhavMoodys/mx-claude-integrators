package com.moodys.maxsight.{{vendor}}.exception;

import org.springframework.http.HttpStatus;

import java.util.Map;

/** {{Vendor}} failed on its own side (5xx other than 504). Retriable. */
public class {{Vendor}}ServerException extends {{Vendor}}APIException {

    public {{Vendor}}ServerException(String message) {
        super(message, HttpStatus.BAD_GATEWAY, Map.of());
    }

    public {{Vendor}}ServerException(String message, Map<String, Object> details) {
        super(message, HttpStatus.BAD_GATEWAY, details);
    }
}
