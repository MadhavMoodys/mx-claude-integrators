package com.moodys.maxsight.{{vendor}}.transformer;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.moodys.maxsight.{{vendor}}.exception.{{Vendor}}ResponseException;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.Map;

/**
 * Turns {{Vendor}}'s JSON into MaxSight-shaped DTOs.
 *
 * <p>Pure by design — no HTTP, no repositories, no Spring beans beyond the mapper — which is
 * what makes it testable against captured vendor fixtures with no server running.
 */
@Component
public class ResponseTransformer {

    private final ObjectMapper objectMapper = new ObjectMapper();

    /**
     * @param body raw response body from {{Vendor}}
     * @return the MaxSight representation
     * @throws {{Vendor}}ResponseException if the body is not the shape the vendor documents
     */
    public List<Map<String, Object>> toResults(String body) {
        // TODO(TICKET-000): replace Map with the real DTOs once the vendor's response shape is
        // known, and add a fixture per shape under src/test/resources.
        try {
            JsonNode root = objectMapper.readTree(body);
            JsonNode results = root.path("results");
            if (!results.isArray()) {
                throw new {{Vendor}}ResponseException(
                        "{{Vendor}} response had no results array", Map.of());
            }
            return objectMapper.convertValue(results, List.class);
        } catch (com.fasterxml.jackson.core.JsonProcessingException e) {
            throw new {{Vendor}}ResponseException("{{Vendor}} response was not valid JSON", e);
        }
    }
}
