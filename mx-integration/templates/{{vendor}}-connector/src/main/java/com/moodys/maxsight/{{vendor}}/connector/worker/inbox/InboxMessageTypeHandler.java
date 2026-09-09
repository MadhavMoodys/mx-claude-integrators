package com.moodys.maxsight.{{vendor}}.connector.worker.inbox;

/**
 * Handles one inbox message type. The worker routes on {@link #getMessageType()}, matched
 * against the {@code m-type} header, so adding a type means adding a bean and nothing else.
 */
public interface InboxMessageTypeHandler {

    String getMessageType();

    void handle(InboxMessagePayload payload) throws Exception;
}
