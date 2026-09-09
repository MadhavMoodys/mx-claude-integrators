package com.moodys.maxsight.{{vendor}}.exception;

import lombok.Getter;
import org.springframework.http.HttpStatus;

import java.util.Map;

/**
 * Base for every failure of a call to {{Vendor}}.
 *
 * <p>Carries the status the caller should see and a context map — at minimum
 * {@code endpoint} and {@code statusCode} — so a log line says which call failed without
 * stitching threads together.
 */
@Getter
public class {{Vendor}}APIException extends RuntimeException {

    private final HttpStatus httpStatus;
    private final transient Map<String, Object> details;
    private final String errorCode;

    public {{Vendor}}APIException(String message) {
        this(message, HttpStatus.INTERNAL_SERVER_ERROR, Map.of(), null, null);
    }

    public {{Vendor}}APIException(String message, Throwable cause) {
        this(message, HttpStatus.INTERNAL_SERVER_ERROR, Map.of(), null, cause);
    }

    public {{Vendor}}APIException(String message, HttpStatus httpStatus, Map<String, Object> details) {
        this(message, httpStatus, details, null, null);
    }

    public {{Vendor}}APIException(String message,
                                  HttpStatus httpStatus,
                                  Map<String, Object> details,
                                  String errorCode,
                                  Throwable cause) {
        super(message, cause);
        this.httpStatus = httpStatus;
        this.details = details == null ? Map.of() : Map.copyOf(details);
        this.errorCode = errorCode;
    }
}
