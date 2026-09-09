package com.moodys.maxsight.{{vendor}}.transformer;

import com.moodys.maxsight.{{vendor}}.exception.{{Vendor}}ResponseException;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/** The transformer is pure, so these run with no Spring context and no server. */
class ResponseTransformerTest {

    private final ResponseTransformer transformer = new ResponseTransformer();

    @Test
    void readsTheResultsArray() {
        String body = "{\"results\":[{\"id\":\"1\"},{\"id\":\"2\"}]}";

        assertEquals(2, transformer.toResults(body).size());
    }

    @Test
    void anEmptyResultsArrayIsNotAnError() {
        assertTrue(transformer.toResults("{\"results\":[]}").isEmpty());
    }

    @Test
    void aMissingResultsArrayIsRejectedRatherThanReturnedEmpty() {
        // "no data" and "the shape changed" must not look the same to a caller.
        assertThrows({{Vendor}}ResponseException.class, () -> transformer.toResults("{\"other\":1}"));
    }

    @Test
    void malformedJsonIsRejected() {
        assertThrows({{Vendor}}ResponseException.class, () -> transformer.toResults("not json"));
    }
}
