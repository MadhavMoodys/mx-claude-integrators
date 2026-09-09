package com.moodys.maxsight.{{vendor}}.connector.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

import java.util.Objects;

/**
 * Bound from the {@code connector.*} block in application.yml.
 *
 * <p>The null checks fail the context at startup rather than at the first message: a
 * connector that boots with no outbox topic looks healthy and silently drops work.
 */
@ConfigurationProperties(prefix = "connector")
public record ConnectorProperties(
        String name,
        String outboxTopic,
        String apiEndpoint
) {

    public ConnectorProperties {
        Objects.requireNonNull(name, "connector.name must be configured");
        Objects.requireNonNull(outboxTopic, "connector.outbox-topic must be configured");
        Objects.requireNonNull(apiEndpoint, "connector.api-endpoint must be configured");
    }
}
