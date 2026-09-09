package com.moodys.maxsight.{{vendor}}.connector.protocol;

/**
 * Message types on the orchestrator → connector subscription stream.
 *
 * <p>Wire values must match the {@code m-type} header the orchestrator sets. They are part
 * of a cross-service contract, so renaming a constant is safe but changing a wire value is
 * not.
 */
public enum SubscriptionMessageType {

    SUBSCRIPTION_DATA("subscription_data"),
    CANCEL_SUB("cancel_sub");

    private final String wireValue;

    SubscriptionMessageType(String wireValue) {
        this.wireValue = wireValue;
    }

    public String wireValue() {
        return wireValue;
    }
}
