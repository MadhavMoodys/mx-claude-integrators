package com.moodys.maxsight.{{vendor}}.config;

import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.info.Info;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/** OpenAPI document metadata for the generated {@code /v3/api-docs}. */
@Configuration
public class OpenApiConfig {

    @Bean
    public OpenAPI {{vendor}}OpenApi() {
        return new OpenAPI().info(new Info()
                .title("MX {{Vendor}} API")
                .version("v1")
                .description("MaxSight-facing API for the {{Vendor}} integration"));
    }
}
