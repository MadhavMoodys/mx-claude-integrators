# Porting the inbox/outbox worker layer into `{{vendor}}-connector`

## What you have, and what you don't

The scaffolder generated a **partial** connector: enough to boot, connect to Kafka and
Postgres, and give you the shapes everything else plugs into.

| Generated | File |
|---|---|
| Module + dependencies | `pom.xml` |
| Boot class | `connector/Application.java` |
| Typed config | `connector/config/ConnectorProperties.java` |
| Wire vocabulary | `connector/protocol/SubscriptionMessageType.java`, `OutboxEventType.java` |
| Handler contracts | `connector/worker/inbox/InboxMessagePayload.java`, `InboxMessageTypeHandler.java` |
| Calls back into `{{vendor}}-api` | `connector/client/{{Vendor}}ServiceClient.java`, `{{Vendor}}ApiFacade.java` |
| Runtime config | `src/main/resources/application.yml` |
| Schema | `src/main/resources/db/migration/V1__initial_schema.sql` |

**Not generated:** the consumer, the two workers, the entities, the repositories, the
subscription handlers, and the orchestrator protobuf parsing. That layer is ~60 classes
bound tightly to `mx-worker`, `mx-consumer` and the orchestrator's protobuf contract.
Writing it from a template would be guesswork that compiles and then misbehaves at the
first real message, so it is ported from the reference repo instead, where it is known
to work.

Reference repo: **`mx-newsedge`**, module `newsedge-connector`.

## The flow you are building

```
Kafka topic  maxsight.orchestrator.{{vendor}}-connector
  → InboxHandler            (consumer; writes a row and returns — no work on the poll thread)
  → inbox table
  → InboxWorkerHandler      (poller; routes on the m-type header)
  → SubscriptionInputHandler | CancelSubHandler
  → OrchestratorPayloadParser  (protobuf → JSON)
  → {{Vendor}}ApiFacade     → {{vendor}}-api
  → SubscriptionOutputService → outbox table
  → OutboxWorkerHandler     (poller; publishes protobuf)
  → Kafka topic  maxsight.orchestrator.inbox
```

Two hops through the database on purpose: the consumer never blocks on vendor calls, and
a crash mid-flight loses nothing, because the row is already committed.

## Port order

Copy in this order — each step compiles before the next one starts. Rename the package
`com.moodys.maxsight.newsedge.connector` → `com.moodys.maxsight.{{vendor}}.connector` and
`Newsedge` → `{{Vendor}}` throughout.

1. **Entities and repositories** — `entity/Inbox`, `InboxDeadLetter`, `Outbox`,
   `OutboxDeadLetter`, `SubscriptionState`; `repository/InboxRepository`,
   `InboxJobRepository`, `InboxDeadLetterRepository`, `OutboxRepository`,
   `OutboxJobRepository`, `OutboxDeadLetterRepository`, `SubscriptionStateRepository`.
   The `*JobRepository` classes are the beans `application.yml` names under
   `mx.workers.*.repository-bean`; the names must match.
2. **Consumer** — `consumer/InboxHandler`, `service/InboxService`,
   `util/MxMessageHeaderKeys`. Keep the handler thin: persist and return.
3. **Inbox worker** — `worker/inbox/InboxWorkerHandler`, `InboxWorkerJob`. The handler is
   a router over `InboxMessageTypeHandler` beans; you already have that interface.
4. **Subscription handlers** — `subscriptions/SubscriptionInputHandler`,
   `CancelSubHandler`, `SubscriptionInputPersistenceService`,
   `service/SubscriptionStateService`. This is where `{{Vendor}}ApiFacade` gets called and
   where most of the vendor-specific editing lands.
5. **Protobuf** — `protocol/OrchestratorPayloadParser`, `OrchestratorResponseBuilder`.
   See the protobuf note below before this step.
6. **Outbox** — `worker/outbox/OutboxWorkerHandler`, `OutboxEnqueuer`,
   `service/SubscriptionOutputService`, `config/KafkaProducerConfig`.
7. **Tests** — port the matching `src/test` classes as you go, not at the end.

## Deliberate omissions in the generated `pom.xml`

The reference `newsedge-connector/pom.xml` carries four things this skeleton drops. They
are absent by choice, not by oversight — add each one back only when the step that needs
it arrives.

| Dropped | Add back when |
|---|---|
| `os-maven-plugin`, `protobuf-maven-plugin`, `build-helper-maven-plugin`, `protobuf-java` | You add a **local** `.proto` under `src/main/proto`. The orchestrator's messages do **not** need this — `mx-orchestrator-subscriptions-proto` already ships generated classes, and it is already a dependency. NewsEdge only needs codegen for its own `subject_events.proto`. |
| `shedlock-spring` / `shedlock-provider-jdbc-template` | You add a scheduled job that must run on exactly one pod. The refresh job is NewsEdge-specific. |

Also not templated: `ci/*` and `config/DatabaseUrlPostProcessor` — environment
plumbing specific to the NewsEdge pipeline. Port them if your pipeline has the same shape.

## Things that bite

- **`@EntityScan` stays restricted.** `Application.java` pins scanning to this service's
  `entity` package. The `mx-*` starters put their own entities on the classpath, and an
  unrestricted scan adopts them as your tables — `ddl-auto: validate` then fails the boot
  with a confusing message about a table you have never heard of.
- **Never edit `V1__initial_schema.sql` after it has been applied anywhere.** Flyway
  compares checksums; a changed one is a failed deploy, not a re-run. Add `V2__…`.
- **Worker concurrency vs. connection pool.** Every worker thread holds a connection for
  its whole transaction. The `inbox: 2` + `outbox: 2` in `application.yml` sits inside the
  default Hikari pool of 10. Raise them together or you will deadlock under load.
- **Handler bean names are config, not types.** `handler-bean: inboxWorkerHandler` resolves
  by Spring bean name. Renaming the class silently breaks it at startup.
- **`RetriableException` is the retry switch.** Throw it and the worker reschedules with
  backoff; throw anything else and the row dead-letters. `{{Vendor}}ApiFacade` already
  draws that line for HTTP failures — keep the same rule in the handlers.
