# ADR 0008: Use Host state and Device receipts for durable semantic jobs

- Status: Accepted design; implementation deferred to follow-up issues.
- Date: 2026-08-07

## Context

Phase 2 accepts online-only, non-retained MQTT jobs. QoS 1 can duplicate an
application message, Host result waiters vanish on restart, and the Device's
current completed-ID ledger is RAM-only. A Device reboot after printer output
can therefore make the result ambiguous and make redelivery dangerous.

Managed EMQX provides session and queue options, but these are at-least-once
transport facilities. They do not own Paperbridge job states, survive every
plan or provider change, prevent physical duplicate output after Device reboot,
or prove paper emerged. The detailed primary-source comparison is
`docs/research/durable-mqtt-delivery-2026-08-07.md`.

## Decision

For future durable v2 semantic jobs:

1. The Host is the durable lifecycle authority. It persists accepted jobs and
   transitions in a local SQLite database using Node's built-in `node:sqlite`.
2. The Device maintains a persistent, crash-safe execution receipt keyed by
   `job_id` and payload digest. It writes `attempt_started` before it opens the
   Printer connection, then writes a terminal result before publishing it.
3. MQTT stays versioned, QoS 1, and non-retained. The Device uses a clean
   print-job session and asks for work after connection. The Host publishes at
   most one queued head job after it durably marks that attempt as dispatched.
4. Any Host publish attempt, Device `attempt_started` receipt, or result timeout
   that cannot be proved terminal becomes Unknown Delivery Result. It blocks
   automatic retry and later inbox work until an Owner manually reconciles it.
5. Durable delivery is a v2 protocol. V1 remains online-only during rollout;
   rollback stops v2 dispatch without translating or replaying durable work.

This provides at-most-once automatic delivery. It does not claim exactly-once
paper output or change `delivered_to_printer` into `printed`.

## Considered options

- **EMQX Durable Sessions or Message Queue:** can improve broker-side survival
  but are provider/plan-specific and still redeliver at least once. Not selected
  as Paperbridge job state or duplicate prevention.
- **MQTT retained print jobs:** keeps only the last job per topic and redelivers
  it on subscription. It loses ordering and risks repeated paper output.
- **Host state only:** protects Host restart but cannot suppress a Device reboot
  after Printer work.
- **Device state only:** protects some redelivery but cannot retain accepted
  work, control ordering, expiry, authorization, or Sender reconciliation.

## Consequences

The system gains durable data, schema migration, encrypted job-body retention,
Device filesystem journal testing, capability rollout, and a manual
reconciliation workflow. It intentionally trades some ambiguous jobs for
physical-output safety. Implementation must pass fault-injection simulator tests
before any hardware acceptance, and must retain local Mosquitto as a supported
broker-neutral development path.
