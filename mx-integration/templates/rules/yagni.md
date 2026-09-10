# YAGNI

Build what this ticket requires. Nothing else.

The cost of speculative code is not the hour spent writing it. It is every later
reader who must work out whether the abstraction is load-bearing, every test that
covers a path no caller takes, and every migration that drags an unused column
forward because nobody can prove it is dead.

**Do not write, unless the current requirement demands it:**

- an interface with one implementation, added alongside that implementation
- a config key nothing reads, or an env var nothing resolves
- a generic type parameter with one binding
- a strategy, factory or registry serving a single case
- `Optional` fields, nullable columns or protobuf `oneof`s for a second vendor
  shape that does not exist yet
- retry, cache or batching layers before a measurement says they are needed
- a public method with no caller and no test

**When you notice the pull toward one of these**, say so in one line and move on:
*"A `RateStrategy` interface would let us swap algorithms later — not adding it,
one algorithm today."* That sentence is worth more than the abstraction. It tells
the next reader the option was considered and declined, which is what stops them
re-litigating it.

## What YAGNI does not license

This is the half that gets dropped, and dropping it turns YAGNI into an excuse to
under-build. YAGNI governs **speculative capability**. It says nothing about
correctness, and it never overrides a rule the integration already mandates.

Still required, always:

- the `Controller → Service/Client → RestClient` layering, even where a direct
  call would be shorter
- typed exceptions at the client boundary — the status→exception mapping is not
  optional scaffolding
- error handling for every failure the vendor can actually return
- tests for the behaviour you did write
- `${ENV_VAR}` credential indirection, with no literal secret anywhere
- the comment policy: comment the why

"We might not need this error path" is not YAGNI. The vendor returns 429 today.

## The judgement call

YAGNI is about *needs*, not *counts*. A second implementation you have a ticket
for is a need. A second implementation someone mentioned in a meeting is not.

When it is genuinely unclear, prefer the smaller thing and say why — deleting a
concrete class later is cheap, and unpicking an abstraction that grew callers is
not.
