package com.moodys.maxsight.{{vendor}}.connector.worker.inbox;

import org.springframework.lang.Nullable;

import java.util.Map;

/**
 * App-level contract for an inbox message handed to a message-type handler.
 *
 * <p>Exists so handlers are not written against the framework's job type: the worker
 * starter can change its job representation without every handler changing with it.
 */
public interface InboxMessagePayload {

    String getMessageKey();

    byte[] getBody();

    Map<String, String> getHeaders();

    @Nullable
    String getOtelContext();
}
