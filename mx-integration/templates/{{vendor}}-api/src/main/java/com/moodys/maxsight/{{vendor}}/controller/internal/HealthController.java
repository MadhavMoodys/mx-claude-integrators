package com.moodys.maxsight.{{vendor}}.controller.internal;

import com.moodys.maxsight.{{vendor}}.service.HealthService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/** Service-to-service health endpoint. Not exposed through the public ingress. */
@RestController
@RequestMapping("/internal")
public class HealthController {

    private final HealthService healthService;

    public HealthController(HealthService healthService) {
        this.healthService = healthService;
    }

    @GetMapping("/health")
    public ResponseEntity<Map<String, Object>> health() {
        return ResponseEntity.ok(healthService.health());
    }
}
