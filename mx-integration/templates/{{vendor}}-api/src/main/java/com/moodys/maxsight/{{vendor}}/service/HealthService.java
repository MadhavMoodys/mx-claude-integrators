package com.moodys.maxsight.{{vendor}}.service;

import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.Map;

/**
 * Backs {@code /internal/health}, which the liveness and readiness probes in
 * {@code deployment.yaml} poll.
 */
@Slf4j
@Service
public class HealthService {

    /**
     * Reports the service healthy when it can serve requests.
     *
     * <p>Deliberately does not call {{Vendor}}: readiness that fails on a single upstream blip
     * takes the pod out of rotation for a fault it cannot fix, and Kubernetes then restarts
     * a process that was working.
     */
    public Map<String, Object> health() {
        return Map.of("status", "UP", "service", "{{vendor}}-api");
    }
}
