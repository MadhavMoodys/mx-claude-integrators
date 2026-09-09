package com.moodys.maxsight.{{vendor}}.connector.client;

import com.moodys.maxsight.{{vendor}}.connector.config.ConnectorProperties;
import com.moodys.mx.httpclient.spring.rest.MxRestClients;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;

import java.util.UUID;

/**
 * Calls {{vendor}}-api. The connector never talks to {{Vendor}} directly — all vendor
 * knowledge lives in the api module, and this side only knows a MaxSight endpoint.
 */
@Service
public class {{Vendor}}ServiceClient {

    private static final Logger log = LoggerFactory.getLogger({{Vendor}}ServiceClient.class);

    private final RestClient restClient;
    private final String apiEndpoint;

    public {{Vendor}}ServiceClient(MxRestClients restClients, ConnectorProperties connectorProperties) {
        this.restClient = restClients.client("{{vendor}}-service");
        this.apiEndpoint = connectorProperties.apiEndpoint();
    }

    public String fetch(UUID subscriptionId, byte[] requestBody) {
        // TODO(TICKET-000): replace with the real {{vendor}}-api endpoint and response type.
        log.debug("Fetching from {{vendor}}-api subscriptionId={} endpoint={}", subscriptionId, apiEndpoint);

        return restClient.post()
                .uri(apiEndpoint)
                .contentType(MediaType.APPLICATION_JSON)
                .body(requestBody)
                .retrieve()
                .body(String.class);
    }
}
