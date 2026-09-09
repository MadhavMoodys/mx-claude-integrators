package com.moodys.maxsight.{{vendor}}.connector.client;

import com.moodys.mx.worker.spring.error.RetriableException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.HttpServerErrorException;
import org.springframework.web.client.ResourceAccessException;

import java.util.UUID;

/**
 * The one place that decides whether a failed {{vendor}}-api call is worth retrying.
 *
 * <ul>
 *   <li>5xx, 429 and connection failures → {@link RetriableException}, so the worker
 *       reschedules with backoff instead of dead-lettering</li>
 *   <li>other 4xx → rethrown unchanged; the caller must tell the orchestrator, because a
 *       retry would fail identically</li>
 * </ul>
 */
@Component
public class {{Vendor}}ApiFacade {

    private static final Logger log = LoggerFactory.getLogger({{Vendor}}ApiFacade.class);

    private final {{Vendor}}ServiceClient serviceClient;

    public {{Vendor}}ApiFacade({{Vendor}}ServiceClient serviceClient) {
        this.serviceClient = serviceClient;
    }

    public String fetch(UUID subscriptionId, byte[] requestBody) throws Exception {
        try {
            return serviceClient.fetch(subscriptionId, requestBody);
        } catch (HttpClientErrorException e) {
            if (e.getStatusCode() == HttpStatus.TOO_MANY_REQUESTS) {
                log.warn("{{vendor}}-api rate limited (retriable). subscriptionId={}", subscriptionId);
                throw new RetriableException("{{vendor}}-api rate limited", e);
            }
            throw e;
        } catch (HttpServerErrorException e) {
            log.warn("{{vendor}}-api returned server error (retriable). subscriptionId={} status={}",
                    subscriptionId, e.getStatusCode());
            throw new RetriableException("{{vendor}}-api returned " + e.getStatusCode(), e);
        } catch (ResourceAccessException e) {
            // Connection refused, read/connect timeout, network partition. Transient, and it must
            // not surface as an unexpected worker error -- that stalls the whole pool.
            log.warn("{{vendor}}-api connection/IO error (retriable). subscriptionId={} error={}",
                    subscriptionId, e.getMessage());
            throw new RetriableException("{{vendor}}-api unreachable", e);
        }
    }
}
