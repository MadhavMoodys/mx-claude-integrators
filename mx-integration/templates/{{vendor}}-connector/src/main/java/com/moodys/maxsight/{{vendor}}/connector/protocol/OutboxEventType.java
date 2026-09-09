package com.moodys.maxsight.{{vendor}}.connector.protocol;

/**
 * Connector → orchestrator message types published via the transactional outbox.
 *
 * <p>Wire values must match the orchestrator's {@code subscriptions-api} constants:
 * {@code update_data} carries an {@code UpdateData} payload, {@code end_sub} an
 * {@code EndOfStream}.
 */
public enum OutboxEventType {

    UPDATE_DATA("update_data"),
    END_OF_STREAM("end_sub");

    private final String wireValue;

    OutboxEventType(String wireValue) {
        this.wireValue = wireValue;
    }

    public String wireValue() {
        return wireValue;
    }
}
