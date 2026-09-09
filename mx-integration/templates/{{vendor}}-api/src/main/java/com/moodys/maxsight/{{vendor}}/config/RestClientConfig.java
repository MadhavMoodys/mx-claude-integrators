package com.moodys.maxsight.{{vendor}}.config;

import com.moodys.mx.httpclient.spring.rest.MxRestClients;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.TaskScheduler;
import org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor;
import org.springframework.scheduling.concurrent.ThreadPoolTaskScheduler;
import org.springframework.web.client.RestClient;

import java.util.concurrent.Executor;
import java.util.concurrent.RejectedExecutionException;
import java.util.concurrent.ThreadPoolExecutor;

/**
 * RestClient and task-scheduling beans.
 *
 * <p>The HTTP client itself is built by mx-http-client-spring-boot-starter from the
 * {@code mx.http.client.clients.{{vendor}}} block in {@code application.yml}; this class
 * only names it.
 */
@Configuration
public class RestClientConfig {

    /** Bean name of the executor used for concurrent {{Vendor}} calls. */
    public static final String {{VENDOR}}_CALL_EXECUTOR = "{{vendor}}CallExecutor";

    @Bean
    public RestClient {{vendor}}RestClient(MxRestClients restClients) {
        return restClients.client("{{vendor}}");
    }

    /**
     * Executor for {{Vendor}} calls that are independent of each other and can be in flight
     * at the same time.
     * <p>
     * Bounded on purpose: vendor calls block for up to the read timeout, so an unbounded pool
     * would let a slow upstream convert every inbound request into more parked threads. When
     * the pool and its queue are full, the extra call runs on the request thread instead.
     * <p>
     * This is {@link ThreadPoolExecutor.CallerRunsPolicy} with one deliberate difference: that
     * policy is {@code if (!pool.isShutdown()) call.run();}, so after shutdown it drops the task
     * and returns normally. A caller that submitted through {@code CompletableFuture} would then
     * hold a future that never completes and block forever joining it. Rejecting loudly turns
     * that into an exception the caller can handle.
     */
    @Bean(name = {{VENDOR}}_CALL_EXECUTOR)
    public Executor {{vendor}}CallExecutor() {
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        executor.setCorePoolSize(8);
        executor.setMaxPoolSize(32);
        executor.setQueueCapacity(64);
        executor.setThreadNamePrefix("{{vendor}}-call-");
        executor.setRejectedExecutionHandler((call, pool) -> {
            if (pool.isShutdown()) {
                throw new RejectedExecutionException("{{Vendor}} call executor is shut down");
            }
            call.run();
        });
        executor.setWaitForTasksToCompleteOnShutdown(true);
        executor.setAwaitTerminationSeconds(30);
        executor.initialize();
        return executor;
    }

    /** Single daemon thread that runs the scheduled token refresh. */
    @Bean
    public TaskScheduler taskScheduler() {
        ThreadPoolTaskScheduler scheduler = new ThreadPoolTaskScheduler();
        scheduler.setPoolSize(1);
        scheduler.setThreadNamePrefix("token-refresh-");
        scheduler.setDaemon(true);
        scheduler.initialize();
        return scheduler;
    }
}
