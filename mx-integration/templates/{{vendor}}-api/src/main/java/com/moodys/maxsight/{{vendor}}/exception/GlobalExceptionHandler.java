package com.moodys.maxsight.{{vendor}}.exception;

import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.HttpMediaTypeNotSupportedException;
import org.springframework.web.HttpRequestMethodNotSupportedException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.MissingServletRequestParameterException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.util.HashMap;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * Turns every exception that escapes a controller into the MaxSight error response.
 *
 * <p>This is the only place that logs a failed call. Controllers do not catch to log; adding
 * a catch there produces the same stack trace twice under two different messages.
 */
@Slf4j
@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler({{Vendor}}APIException.class)
    public ResponseEntity<Map<String, Object>> handle{{Vendor}}ApiException({{Vendor}}APIException ex) {
        // 404 is usually the caller asking about something absent, not a fault here.
        if (ex.getHttpStatus() == HttpStatus.NOT_FOUND) {
            log.warn("{{Vendor}} API: {} (status: {}, details: {})",
                    ex.getMessage(), ex.getHttpStatus(), ex.getDetails());
        } else {
            log.error("{{Vendor}} API error: {} (status: {}, details: {})",
                    ex.getMessage(), ex.getHttpStatus(), ex.getDetails(), ex);
        }

        Map<String, Object> response = new HashMap<>();
        response.put("status", "error");
        response.put("message", ex.getMessage());
        if (ex.getErrorCode() != null) {
            response.put("errorCode", ex.getErrorCode());
        }
        return ResponseEntity.status(ex.getHttpStatus()).body(response);
    }

    @ExceptionHandler({
            HttpMessageNotReadableException.class,
            HttpMediaTypeNotSupportedException.class,
            HttpRequestMethodNotSupportedException.class,
            MissingServletRequestParameterException.class
    })
    public ResponseEntity<Map<String, Object>> handleRequestErrors(Exception ex) {
        HttpStatus status = resolveStatus(ex);
        log.warn("Request error: status={}, exception={}, message={}",
                status.value(), ex.getClass().getSimpleName(), ex.getMessage());
        return error(status, resolveMessage(ex));
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<Map<String, Object>> handleValidation(MethodArgumentNotValidException ex) {
        String message = ex.getBindingResult().getFieldErrors().stream()
                .map(e -> e.getField() + ": " + e.getDefaultMessage())
                .collect(Collectors.joining(", "));
        log.warn("Request validation failed: {}", message);
        return error(HttpStatus.UNPROCESSABLE_ENTITY, message.isEmpty() ? "Invalid request data" : message);
    }

    @ExceptionHandler(IllegalArgumentException.class)
    public ResponseEntity<Map<String, Object>> handleIllegalArgument(IllegalArgumentException ex) {
        log.warn("Invalid request parameter: {}", ex.getMessage());
        return error(HttpStatus.UNPROCESSABLE_ENTITY, ex.getMessage());
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<Map<String, Object>> handleUnexpected(Exception ex) {
        // The real message is logged, never returned: it can carry vendor request echoes.
        log.error("Unexpected error: {}", ex.getMessage(), ex);
        return error(HttpStatus.INTERNAL_SERVER_ERROR,
                "An unexpected error occurred. Please contact support.");
    }

    private ResponseEntity<Map<String, Object>> error(HttpStatus status, String message) {
        Map<String, Object> response = new HashMap<>();
        response.put("status", "error");
        response.put("message", message);
        return ResponseEntity.status(status).body(response);
    }

    private HttpStatus resolveStatus(Exception ex) {
        if (ex instanceof HttpRequestMethodNotSupportedException) {
            return HttpStatus.METHOD_NOT_ALLOWED;
        }
        if (ex instanceof HttpMediaTypeNotSupportedException) {
            return HttpStatus.UNSUPPORTED_MEDIA_TYPE;
        }
        return HttpStatus.BAD_REQUEST;
    }

    private String resolveMessage(Exception ex) {
        if (ex instanceof HttpMessageNotReadableException e) {
            Throwable cause = e.getRootCause();
            return "Invalid request body: " + (cause != null ? cause.getMessage() : e.getMessage());
        }
        if (ex instanceof MissingServletRequestParameterException e) {
            return "Missing required parameter: " + e.getParameterName();
        }
        return ex.getMessage();
    }
}
