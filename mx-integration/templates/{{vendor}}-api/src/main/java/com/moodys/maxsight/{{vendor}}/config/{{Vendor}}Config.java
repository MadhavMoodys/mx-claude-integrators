package com.moodys.maxsight.{{vendor}}.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Configuration;

/**
 * Configuration properties for the {{Vendor}} API, bound from the {@code {{vendor}}}
 * block in {@code application.yml}.
 *
 * <p>Credentials arrive as {@code ${ENV_VAR}} placeholders only; a literal here is
 * rejected by the secret-guard hook and would leak into git history.
 */
@Data
@Configuration
@ConfigurationProperties(prefix = "{{vendor}}")
public class {{Vendor}}Config {

    private String baseUrl;
    private String apiKey;
    private String username;
    private String password;
    private Integer requestTimeout;
    private Integer tokenRefreshBufferMinutes;

    /**
     * Max seconds between Resilience4j retry attempts. Caps the wait produced by
     * exponential backoff; see {@link {{Vendor}}RetryConfiguration}.
     */
    private Integer retryMaxWaitSeconds;

    // TODO(TICKET-000): add the vendor-specific tunables this integration needs
    // (page sizes, vocabularies, feature toggles) as plain fields.
}
