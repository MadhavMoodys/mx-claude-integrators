package com.moodys.maxsight.{{vendor}};

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/** Entry point for the {{Vendor}} vendor-facing API service. */
@SpringBootApplication
public class {{Vendor}}ApiApplication {

    public static void main(String[] args) {
        SpringApplication.run({{Vendor}}ApiApplication.class, args);
    }
}
