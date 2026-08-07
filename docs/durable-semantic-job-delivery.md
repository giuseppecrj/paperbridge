# Durable semantic job delivery and recovery

- Status: Accepted design for issue #16; not implemented.
- Decision: ADR 0008.

## Purpose

This design adds eventual offline delivery without changing Paperbridge's
physical-output safety rule: an Unknown Delivery Result is never permission to
send a job again. It applies only to a future durable v2 path. The current v1
REST, MCP, USB, and MQTT paths remain online-only and non-retained.

`delivered_to_printer` remains a successful write to the Printer Endpoint. It
never means `printed`.

## Decisions

1. The Host owns the durable semantic-job lifecycle in a local SQLite database.
   The Device owns a persistent execution receipt that prevents a reboot from
   turning MQTT redelivery into a second delivery.
2. MQTT remains MQTT 3.1.1, QoS 1, and non-retained. The Device uses a clean
   print-job session. Broker queues, retained jobs, and broker session state are
   transport aids, never Paperbridge's system of record.
3. The Host sends a job only after a currently connected Device asks for work.
   It records the dispatch attempt before the first publish.
4. The Device persists `attempt_started` before it opens a Printer connection.
   A reboot with that record is `unknown`, even when no paper may have emerged.
   The Device does not deliver that `job_id` again automatically.
5. A Sender may cancel only before dispatch. A Sender cannot retry a dispatched
   or Unknown Delivery Result. Manual reconciliation may close a job or create a
   replacement with a new `job_id`; it never reuses the old one.
6. One unresolved job blocks later jobs for the same Physical Inbox. This
   preserves order and makes uncertain physical output visible rather than
   printing newer work around it.

The design gives at-most-once automatic delivery, not exactly-once paper. It
prefers an explicit human decision over duplicate physical output.

## Authority and durable records

| Component | Durable authority | Does not own |
| --- | --- | --- |
| Host | acceptance, payload, lifecycle, expiry, order, authorization evidence, and reconciliation | paper observation or Device execution truth |
| Device | immutable per-`job_id` execution receipt and stored terminal result | queueing, Sender authorization, or reordering |
| MQTT broker | best-effort QoS 1 transport for current connections | job lifecycle, expiry, audit, or idempotency |
| Printer | accepts bytes at its Printer Endpoint | proof that paper emerged |

### Host record

A Host record contains the canonical prepared v2 semantic job, `job_id`,
Device ID, SHA-256 payload digest, state, transition timestamps, expiry,
requesting principal, and transition audit data. It uses `node:sqlite` on the
single production Host's persistent volume. The database is outside the
release tree, owned by the service user, and is backed up with the Host's
encrypted operational backup.

The ciphertext job body is retained only while it can be dispatched or
reconciled, then for seven days after a terminal or reconciled outcome. The
Host retains the minimum audit metadata and payload digest for 90 days. It must
not log job content, image bytes, QR data, MQTT credentials, or bearer tokens.

The Host rejects an attempt to reuse a `job_id` with a different Device ID or
payload digest. An idempotent repeated acceptance of the same identity returns
the existing record; it does not create another job.

### Device execution receipt

The Device stores an append-only, crash-safe journal in its local filesystem.
Each entry contains only `job_id`, payload digest, state, timestamps, bytes
sent when known, and the terminal error code. It stores no second copy of the
job body. It retains entries through `expires_at + 7 days`, with a configured
bounded maximum. Storage exhaustion fails closed: the Device reports that it
cannot accept a new durable job and does not evict an unresolved entry.

A duplicate `job_id` with the same digest returns its stored terminal or
Unknown Delivery Result. A different digest is rejected as an identity
conflict. The journal is a delivery guard, not a Device queue.

## Lifecycle

### Host states

| State | Meaning | Allowed next state |
| --- | --- | --- |
| `accepted` | validated v2 job is committed | `pending`, `rejected` |
| `pending` | eligible but no publish attempted | `dispatched`, `cancelled`, `expired` |
| `dispatched` | Host committed one publish attempt; no terminal Device receipt yet | `delivered_to_printer`, `rejected`, `failed`, `unknown` |
| `unknown` | a publish, Device attempt, Host restart, or result timeout makes the outcome ambiguous | `delivered_to_printer`, `rejected`, `failed`, `manually_reconciled` |
| `delivered_to_printer` | Device durably recorded all bytes accepted by the Printer Endpoint | terminal |
| `rejected` | no delivery occurred because validation, authorization, expiry, or identity failed | terminal |
| `failed` | Device reported a known delivery failure; partial bytes, when present, remain physical ambiguity | terminal |
| `cancelled` | Sender cancelled before dispatch | terminal |
| `expired` | job expired before dispatch | terminal |
| `manually_reconciled` | an authorized Owner recorded the resolution of an Unknown Delivery Result | terminal |

The Host persists `dispatched` before calling MQTT publish. Any Host restart
that finds this state changes it to `unknown`; a publish callback error also
changes it to `unknown` because the broker may already have accepted the
packet. The Host may accept a late, digest-matching Device terminal result for
an `unknown` job. It records a late result after manual reconciliation as audit
evidence but does not reopen or dispatch the job.

### Device states

| State | Meaning | Behavior after reboot or duplicate arrival |
| --- | --- | --- |
| absent | no execution receipt | validate expiry and identity, then persist `attempt_started` |
| `attempt_started` | persisted before a Printer connection | publish/report `unknown`; never open a second Printer connection automatically |
| `delivered_to_printer` | terminal socket-delivery receipt was persisted | replay the stored result; never deliver again |
| `rejected` / `failed` | terminal device outcome was persisted | replay the stored result; never deliver again |

The Device persists the terminal receipt before publishing it to MQTT. If that
publish is lost, the Host requests status by `job_id` after reconnect; the
Device replies from its journal. Result replay is safe because it is not a
second Printer operation.

## v2 protocol boundary

Durability requires a new version because v1 schemas reject extra fields and
v1 clients must keep their current online-only behavior. V2 keeps the semantic
receipt model and adds:

- a required UTC `expires_at`, at most seven days after acceptance;
- a canonical SHA-256 payload digest bound to `job_id`;
- Device work-request, job-result, and per-`job_id` status-query messages;
- terminal `unknown` and identity/expiry/storage error codes; and
- explicit result replay metadata without calling replayed delivery `printed`.

The exact schema, topics, and fixtures are follow-up work. They use versioned
v2 topics so a v1 Device cannot consume a durable job. A Device must have a
valid UTC clock before it accepts a v2 job; otherwise it reports a non-delivery
failure. The Host also enforces expiry before dispatch.

A Device publishes a short-lived work request after each clean MQTT connection.
The Host publishes at most one head-of-line pending job in response. The request
is not authority to retry an older job and is not a retained availability signal.

## Failure ownership and outcome

| Scenario | Owner | Outcome |
| --- | --- | --- |
| Device is offline before selection | Host | keep head job `pending`; expire or allow pre-dispatch cancellation |
| Host restarts after `accepted` | Host | resume `pending` from SQLite without a new job ID |
| Host restarts after durable `dispatched` | Host | change to `unknown`; query Device, never republish automatically |
| MQTT publish callback fails after attempt | Host | `unknown`; broker acceptance is ambiguous |
| Host result wait expires | Host | `unknown`; late stored Device result may resolve it |
| Device reboots before journal write | Host | Host's published state becomes `unknown`; no automatic repeat |
| Device reboots after `attempt_started` | Device | return durable `unknown`; Owner must reconcile |
| Device reboots after Printer write but before terminal receipt | Device | return durable `unknown`; never claim delivery or repeat |
| Device terminal result cannot reach Host | Device and Host | Device retains result; Host requests status after reconnect |
| Duplicate MQTT delivery | Device | replay journal result; no second Printer connection |
| Device journal is full or corrupt | Device | reject new durable job and alert Host; do not evict unresolved work |
| Printer reports a socket failure or partial write | Device | persist `failed` with bytes sent; no automatic repeat |

## Sender rules

- A Sender can read the durable state for a job it is authorized to inspect.
- A Sender can cancel only `accepted` or `pending` work. Cancellation does not
  contact a Device and cannot withdraw dispatched bytes.
- A Sender can submit the same `job_id` and digest idempotently while it is
  retained. It cannot alter its content or Device.
- A Sender cannot retry `dispatched`, `unknown`, `failed`, or
  `delivered_to_printer` work automatically.
- An Owner performs manual reconciliation with a recorded reason and one of:
  close as intentionally abandoned, close after independent physical evidence,
  or create a replacement job with a new `job_id`. Replacement is a new
  authorization and appears after the reconciled job in inbox order.

Current Phase 2 uses one private infrastructure credential, not a Sender or
Invite model. This design does not falsely treat that credential as sender
identity. A later public authorization design must supply the actor identity
that the durable audit record stores.

## Broker options

| Option | Benefit | Rejected as job authority because |
| --- | --- | --- |
| QoS 1 with clean sessions | broker-neutral current transport | at-least-once and no offline backlog by itself |
| MQTT persistent sessions | standard offline buffering | replay can duplicate paper; broker retention and limits are not job state |
| Retained print jobs | last-value recovery | overwrites prior work and redelivers on subscribe |
| EMQX Durable Sessions or Message Queue | broker restart/offline hardening | provider/plan-specific and still at-least-once to Device |
| Host SQLite plus Device journal | durable lifecycle plus reboot-safe idempotency | requires explicit application implementation; selected |

The full primary-source comparison is
`docs/research/durable-mqtt-delivery-2026-08-07.md`. EMQX-only facilities may
be operational hardening after this design works with local Mosquitto. They
must remain optional and outside Paperbridge's protocol contract.

## Security, rollout, and rollback

- Host data directory: `0700`; database and backups: least privilege; payload
  encryption key: root-owned runtime secret, never committed or logged.
- Audit data records actor reference, job ID, digest, state transition, time,
  and reconciliation reason. It excludes printable content and credentials.
- Device/Host status queries authenticate through the existing per-Device MQTT
  credentials. Topic ACLs must limit a Device to its own durable-delivery topics.
- V1 remains the default during rollout. Enable v2 only after the Host has its
  schema migration, the Device advertises v2 capability, and simulator crash
  cases pass.
- Rollback disables new v2 acceptance and dispatch. It never turns a durable
  row into v1 work, republishes it, or deletes Device receipts. Existing
  `pending`, `dispatched`, and `unknown` rows remain inspectable and require
  explicit reconciliation.
- A database restore must restore both records and audit history atomically. If
  recovery cannot prove its freshness, the Host enters read-only reconciliation
  mode instead of dispatching.

## Verification gates

Before activation, host/simulator tests must inject every tabled failure between
state write, MQTT publish, Device journal write, Printer connect/write, result
write, and result publish. They must prove no second Printer socket delivery for
the same `job_id` across Host restart, Device reboot, and QoS redelivery.

Physical acceptance is a separate later issue. It requires explicit output
authorization and must record paper observation separately from
`delivered_to_printer`.
