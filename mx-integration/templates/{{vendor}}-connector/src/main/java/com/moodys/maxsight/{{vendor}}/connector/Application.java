package com.moodys.maxsight.{{vendor}}.connector;

import com.moodys.maxsight.{{vendor}}.connector.config.ConnectorProperties;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.autoconfigure.domain.EntityScan;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.scheduling.annotation.EnableScheduling;

@SpringBootApplication
@EnableScheduling
// Restrict entity scanning: the mx-* starters put their own entities on the classpath and
// an unrestricted scan picks them up as this service's tables.
@EntityScan(basePackages = "com.moodys.maxsight.{{vendor}}.connector.entity")
@EnableConfigurationProperties(ConnectorProperties.class)
public class Application {

    public static void main(String[] args) {
        SpringApplication.run(Application.class, args);
    }
}
