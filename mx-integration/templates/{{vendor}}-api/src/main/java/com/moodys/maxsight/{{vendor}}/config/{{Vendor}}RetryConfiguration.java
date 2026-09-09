package com.moodys.maxsight.{{vendor}}.config;

import io.github.resilience4j.core.IntervalFunction;
import io.github.resilience4j.retry.Retry;
import io.github.resilience4j.retry.RetryConfig;
import io.github.resilience4j.retry.RetryRegistry;
import io.github.resilience4j.retry.event.RetryOnErrorEvent;
import io.github.resilience4j.retry.event.RetryOnRetryEvent;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * Builds the {@link Retry} used for {{Vendor}} HTTP calls, taking its base policy from
 * {@code resilience4j.retry.instances.{{vendor}}Api} and capping the wait between attempts
 * at {@code {{vendor}}.retry-max-wait-seconds}.
 */
@Slf4j
@Configuration
public class {{Vendor}}RetryConfiguration {

    /** Same name as {@code resilience4j.retry.instances.*} in application.yml. */
    public static final String RETRY_INSTANCE_NAME = "{{vendor}}Api";

    public static final String RETRY_BEAN_NAME = "{{vendor}}ApiRetry";

    @Bean(name = RETRY_BEAN_NAME)
    public Retry {{vendor}}ApiRetry(RetryRegistry retryRegistry, {{Vendor}}Config config) {
        Retry retry = createCappedRetry(retryRegistry, config);
        retry.getEventPublisher().onRetry(this::logRetryScheduled);
        retry.getEventPublisher().onError(this::logRetriesExhausted);
        return retry;
    }

    /**
     * Unit tests that build the client without Spring should register a config under
     * {@link #RETRY_INSTANCE_NAME} on the registry, then call this.
     */
    @SuppressWarnings("deprecation") // getIntervalFunction() — still the only way to detect which interval API is active
    public static Retry createCappedRetry(RetryRegistry retryRegistry, {{Vendor}}Config config) {
        /*
         * Spring Boot registers resilience4j.retry.instances.* so that retry(name) resolves the
         * instance; it is not always present as getConfiguration(name). Unit tests usually pass
         * Map.of(name, cfg), which is.
         */
        RetryConfig base = retryRegistry.getConfiguration(RETRY_INSTANCE_NAME)
                .orElseGet(() -> retryRegistry.retry(RETRY_INSTANCE_NAME).getRetryConfig());
        long capMs = Math.max(1, config.getRetryMaxWaitSeconds()) * 1000L;
        /*
         * RetryConfig.from copies either intervalFunction or intervalBiFunction, not both.
         * Setting the other kind on the builder trips "intervalFunction was configured twice".
         */
        RetryConfig capped;
        if (base.getIntervalFunction() != null) {
            IntervalFunction original = (IntervalFunction) base.getIntervalFunction();
            capped = RetryConfig.from(base)
                    .intervalFunction(attempt -> Math.min(original.apply(attempt), capMs))
                    .build();
        } else {
            capped = RetryConfig.from(base)
                    .intervalBiFunction((attempt, either) ->
                            Math.min(base.getIntervalBiFunction().apply(attempt, either), capMs))
                    .build();
        }
        /* Register on the shared registry so actuator metrics and retry(name) see one instance. */
        return retryRegistry.retry(RETRY_INSTANCE_NAME, capped);
    }

    private void logRetryScheduled(RetryOnRetryEvent event) {
        log.info("Resilience4j [{}]: retry #{} after {}; last failure: {}",
                event.getName(),
                event.getNumberOfRetryAttempts(),
                event.getWaitInterval(),
                event.getLastThrowable() != null ? event.getLastThrowable().getMessage() : "n/a");
    }

    private void logRetriesExhausted(RetryOnErrorEvent event) {
        log.error("Resilience4j [{}]: all {} attempts failed; not retrying further",
                event.getName(),
                event.getNumberOfRetryAttempts(),
                event.getLastThrowable());
    }
}
