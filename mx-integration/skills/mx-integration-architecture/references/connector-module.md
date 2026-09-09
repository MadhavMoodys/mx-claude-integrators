# The connector module

Described against `newsedge-connector`, the reference implementation. In a new
integration every `newsedge`/`NewsEdge`/`Newsedge` below becomes the vendor's
name; the structure does not change.

Spring Boot 3.5 / Java 21 service that handles orchestrator subscription
lifecycle messages from Kafka via the inbox/outbox pattern. Uses
`mx-framework-java` starters:

- **mx-worker-spring-boot-starter** — DB-backed worker pools with retry (`RetriableException`) and dead-letter (any other exception)
- **mx-consumer-spring-boot-starter** — Kafka consumer with DLQ support
- **mx-orchestrator-subscriptions-proto** — Protobuf for both inbox payloads (`SubscriptionInput`, `CancelSubscription`) and outbox events (`UpdateData`, `EndOfStream`)
- **mx-http-client-spring-boot-starter** — HTTP client (`MxRestClients`) for calling the api module

## Data flow (production)

```
Orchestrator (protobuf) → Kafka topic → InboxHandler (consumer, stores raw bytes)
  → inbox table → InboxWorkerHandler (polls, routes by m-type header)
    → SubscriptionInputHandler / CancelSubHandler
      → OrchestratorPayloadParser (protobuf → JSON extraction)
        → SubscriptionOutputService (builds and sends responses to orchestrator)
          → NewsedgeApiFacade → newsedge-api (receives JSON)
          → OrchestratorResponseBuilder (JSON → protobuf)
          → OutboxEnqueuer → outbox table
            → OutboxWorkerHandler (polls, publishes to Kafka)
              → maxsight.orchestrator.inbox (protobuf)
```

**Wire format**: Orchestrator sends **protobuf binary** on Kafka. The connector
stores raw `byte[]` unchanged through the inbox. `OrchestratorPayloadParser`
decodes protobuf and extracts `Data.json_data` (JSON bytes). The api module
receives **JSON**. Responses back to orchestrator are **protobuf binary** built by
`OrchestratorResponseBuilder`.

## Kafka consumer (InboxHandler)

`InboxHandler` implements `ConsumerMessageHandler` from
`mx-consumer-spring-boot-starter`. It receives `ConsumerRecord<String, byte[]>`
from the topic `maxsight.orchestrator.newsedge-connector`, extracts headers, and
delegates to `InboxService.enqueue()`. `InboxService` peeks at the body via
`SubscriptionPayload.fromBytes()` (JSON-only) to extract `config.lookup_type` for
the `connector_msg_type` column, then persists the raw message into the `inbox`
table.

```yaml
# application.yml consumer config
mx.consumers.subscriptions:
  topics: [maxsight.orchestrator.newsedge-connector]
  group-id: mx-newsedge-connector
  handler-bean: inboxHandler
  dead-letter-sink.type: KAFKA
```

## Inbox worker (InboxWorkerHandler)

`InboxWorkerHandler` implements `JobHandler<InboxWorkerJob>` from
`mx-worker-spring-boot-starter`. The framework polls the `inbox` table and
provides `List<InboxWorkerJob>` (each wrapping an `Inbox` row and implementing
`InboxMessagePayload`). `InboxWorkerHandler` routes each job to the correct
`InboxMessageTypeHandler` by `m-type` header. Unknown or missing types are
dead-lettered via `InboxJobRepository.deadLetterJob()`.

```java
// ...connector.worker.inbox.InboxMessageTypeHandler
public interface InboxMessageTypeHandler {
    String getMessageType(); // wire value: "subscription_data", "cancel_sub"
    void handle(InboxMessagePayload payload) throws Exception;
}

// ...connector.worker.inbox.InboxMessagePayload
payload.getMessageKey()  // String — subscription UUID
payload.getBody()        // byte[] — raw protobuf from orchestrator
payload.getOtelContext() // String
payload.getHeaders()     // Map<String, String>
```

## OrchestratorPayloadParser (protocol)

Converts raw orchestrator protobuf bytes into the connector's own
`SubscriptionPayload` DTO. The rest of the codebase never imports orchestrator
protobuf types directly.

- `extractSubscriptionInput(byte[] body)` → `Optional<ExtractedInput>` — parses `SubscriptionInput` protobuf, extracts `input_version` + `json_data` bytes

A JSON-first fallback exists for local testing convenience. Production always
hits the protobuf path.

## OrchestratorResponseBuilder (protocol)

Builds **protobuf binary** payloads for connector → orchestrator messages:

- `buildUpdateData(inputVersion, streamVersion, outputJson)` → protobuf `UpdateData` bytes
- `buildEndOfStream(inputVersion, streamVersion, errors)` → protobuf `EndOfStream` bytes

## OutboxEventType (protocol)

Wire values for connector → orchestrator messages:

- `UPDATE_DATA` → `"update_data"`
- `END_OF_STREAM` → `"end_sub"`

## SubscriptionOutputService (service)

Responsible for fetching data from the backend and sending protobuf responses to
the orchestrator via the outbox. All orchestrator-bound messages flow through
this service.

```java
public String fetchAndEnqueueUpdateData(UUID subscriptionId, byte[] inputData,
    int inputVersion, String otelContext) throws Exception
public void enqueueEndOfStream(UUID subscriptionId, int inputVersion,
    int streamVersion, List<String> errors, String otelContext)
```

- `fetchNewsStats` — calls the api facade; on success returns the JSON response, on 4xx enqueues `end_of_stream` with valid JSON error (`{"identifier":"newsedge_api_client_error","summary":"..."}`) and rethrows
- `enqueueUpdateData` — builds protobuf `update_data` and enqueues to outbox
- `enqueueEndOfStream` — builds protobuf `end_of_stream` and enqueues to outbox

## NewsedgeApiFacade (HTTP error handling)

A Spring `@Component` that wraps the generated service client and centralises HTTP
error handling. Does **not** interact with the outbox — that responsibility
belongs to `SubscriptionOutputService`.

```java
public String fetchNewsStats(UUID subscriptionId, byte[] requestBody) throws Exception
```

- **5xx** → wrapped in `RetriableException` → framework retries with backoff
- **4xx** → rethrown unchanged (caller handles orchestrator notification)
- **Success** → returns the raw JSON response from the api module

## Subscription handlers

| Handler | m-type | What it does |
|---|---|---|
| `SubscriptionInputHandler` | `subscription_data` | Parses protobuf via `OrchestratorPayloadParser.extractSubscriptionInput()`, bypasses if empty/invalid; if new subscription inserts into `subscription_state`, if existing checks the monotonic version guard and upserts; calls the facade then `enqueueUpdateData` |
| `CancelSubHandler` | `cancel_sub` | Sets status to `CANCELLED` via `SubscriptionStateService` (preserves the original `cancelled_at`). Does **not** send `end_of_stream` — the orchestrator already handles cancellation on its side |

**Deprecated (ignored, logged at DEBUG)**: `new_sub` and `update_input` messages
are discarded by `InboxWorkerHandler.DEPRECATED_MESSAGE_TYPES`. The orchestrator
may still send these alongside `subscription_data` during migration. Remove once
the orchestrator stops sending them.

## Outbox worker (OutboxWorkerHandler)

Implements `JobHandler<Outbox>`. Polls the `outbox` table and publishes messages
to Kafka via `MxKafkaProducerClient` (from `mx-kafka-spring-boot-starter`) using
the topic, key, headers, and body stored in each outbox row. Target topic:
`maxsight.orchestrator.inbox`.

`OutboxEnqueuer` is the write-side component that inserts rows into the `outbox`
table. It uses `ConnectorProperties` for `outboxTopic` and `connectorName`.

## ConnectorProperties

`@ConfigurationProperties("connector")` record with:

- `name` — connector name (`maxsight.orchestrator.newsedge-connector`)
- `outboxTopic` — target topic for outbox (`maxsight.orchestrator.inbox`)
- `riskEndpoint` — api module endpoint (`/internal/news/risk-stats`)

## Service layer

- `SubscriptionOutputService` fetches data from the backend and sends responses to the orchestrator via the outbox.
- `SubscriptionStateService` wraps `SubscriptionStateRepository` (plain JPA, no native queries).
- `InboxService` wraps `InboxRepository` — enqueues raw Kafka messages into the inbox table.

## Database

PostgreSQL with JPA entities (`Inbox`, `InboxDeadLetter`, `Outbox`,
`OutboxDeadLetter`, `SubscriptionState`) and Flyway migrations in
`src/main/resources/db/migration/`.

## Worker config (application.yml)

```yaml
mx.workers:
  inbox:
    handler-bean: inboxWorkerHandler
    repository-bean: inboxJobRepository
  outbox:
    handler-bean: outboxWorkerHandler
    repository-bean: outboxJobRepository
```
