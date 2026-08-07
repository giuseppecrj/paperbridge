# Durable MQTT delivery for Paperbridge (issue #16)

Research date: 2026-08-07  
Status: documentation facts from primary sources only. Not a physical verification
of offline delivery, durable sessions, or retained-message behaviour on the
purchased hardware. Not a design decision or ADR.

## Purpose

Issue #16 asks which broker capabilities may support durable semantic delivery
without moving Paperbridge contracts into one provider. This note compares:

1. Standard MQTT 3.1.1 mechanisms that affect offline or reconnect delivery.
2. EMQX-specific options that extend or harden offline delivery.
3. What each mechanism does **not** solve for physical duplicate-output risk.

Paperbridge context used only to frame the comparison (already implemented /
documented in-repo):

- Phase 2 traffic is MQTT 3.1.1, QoS 1, non-retained semantic jobs and results.
- Device duplicate suppression is a bounded one-boot RAM ledger keyed by
  `job_id`; QoS redelivery of a completed `job_id` returns `duplicate` /
  `DUPLICATE_JOB` without a second printer socket.
- Host timeout is `unknown`; it does not expire, fail, or republish the job.
- Delivery vocabulary remains `delivered_to_printer`, never `printed`.
- ADR 0007 keeps EMQX replaceable: runtime job traffic uses standard MQTT 3.1.1
  contracts, not provider rules, webhooks, registries, or job systems.

Sources for that context: `docs/architecture.md`, `docs/protocol.md`,
`docs/adr/0007-use-exe-dev-and-managed-mqtt-for-the-phase-2-mvp.md`, GitHub
issue #16.

Primary sources for claims below:

- OASIS MQTT Version 3.1.1 OASIS Standard:
  <https://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html>
- EMQX official documentation URLs cited per claim.

---

## 1. MQTT 3.1.1 standard capabilities

### 1.1 QoS 1 — at least once

**What it does**

QoS 1 is “At least once delivery”. The sender assigns a Packet Identifier,
sends `PUBLISH` with QoS=1 and `DUP=0`, and must treat that packet as
unacknowledged until it receives `PUBACK`. The receiver must respond with
`PUBACK` after accepting ownership of the Application Message.

Source: MQTT 3.1.1 §4.3.2, <https://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html>

Bounded claim:

> “This quality of service ensures that the message arrives at the receiver at
> least once.”

**Duplicates are part of the contract**

After the receiver has sent `PUBACK`, any later `PUBLISH` with the same Packet
Identifier must be treated as a **new** publication, irrespective of the `DUP`
flag. The `DUP` flag marks re-delivery of a Control Packet; it does not prove
that the Application Message is new or old.

Source: MQTT 3.1.1 §4.3.2 / §3.3.1.1

Bounded claims:

> “After it has sent a PUBACK Packet the Receiver MUST treat any incoming
> PUBLISH packet that contains the same Packet Identifier as being a new
> publication, irrespective of the setting of its DUP flag.”

> “The recipient of a Control Packet that contains the DUP flag set to 1 cannot
> assume that it has seen an earlier copy of this packet.”

> “When using QoS 1, it is possible for a Client to receive a PUBLISH Packet
> with DUP flag set to 0 that contains a repetition of an Application Message
> that it received earlier, but with a different Packet Identifier.”

**What QoS 1 does not solve for Paperbridge**

| Physical / semantic risk | Why QoS 1 alone is insufficient |
| --- | --- |
| Second paper output from broker redelivery | QoS 1 **promises** possible duplicates. Application identity (`job_id`) must suppress redelivery after first delivery. |
| Second paper after Device reboot | Packet Identifiers and one-boot RAM ledgers do not survive reboot. |
| Host “unknown” after timeout | `PUBACK` proves broker accepted a publish from Host, not that Device delivered to Printer. |
| Exactly-once semantic job lifecycle | Spec provides at-least-once only. Exactly-once would require QoS 2 plus application state; Paperbridge uses QoS 1. |
| Ordering of independent jobs across reconnect | Ordering rules cover re-sent PUBLISH packets in one session flow, not a durable job store. |

### 1.2 Clean Session and Session state

**What it does**

`CleanSession=1`: Client and Server discard any previous Session and start a
new one that lasts only as long as the Network Connection. State must not be
reused in a later Session.

`CleanSession=0`: Server keeps Session state after disconnect so a later
connection with the same Client Identifier can resume. Non-normative guidance:
use QoS 1 or 2 with `CleanSession=0` if messages published while offline must
not be lost.

Source: MQTT 3.1.1 §3.1.2.4

Bounded claims:

> “If CleanSession is set to 1, the Client and Server MUST discard any previous
> Session and start a new one.”

> “A Client using CleanSession set to 0 will receive all QoS 1 or QoS 2 messages
> that were published while it was disconnected. Hence, to ensure that you do
> not lose messages while disconnected, use QoS 1 or QoS 2 with CleanSession
> set to 0.”

**Server Session state includes**

- existence of the Session
- Client subscriptions
- QoS 1 and QoS 2 messages sent to the Client but not fully acknowledged
- QoS 1 and QoS 2 messages pending transmission to the Client
- QoS 2 messages received from the Client but not fully acknowledged
- optionally QoS 0 messages pending transmission

Retained messages are **not** Session state and must not be deleted when the
Session ends.

Source: MQTT 3.1.1 §3.1.2.4, §4.1

**What persistent sessions do not solve**

| Risk | Why Clean Session alone is insufficient |
| --- | --- |
| Physical duplicate after offline queue drains | Offline queue redelivers every stored QoS 1 message on reconnect. Without durable `job_id` idempotency, each redelivery may print again. |
| Device reboot with `CleanSession=1` | Session and offline queue are discarded; work is lost, not reconciled. |
| Device reboot with `CleanSession=0` but new ClientId | Session is not resumed; offline work stays with the old ClientId. |
| Broker restart / crash | Spec requires Session state for the Session lifetime but allows implementation limits and administrative policies on capacity and maximum storage time between connections (§4.1). Memory-only brokers may lose state. |
| Host restart / unknown waiter | Host Session state is separate from Device Session state. Broker offline queue for Device does not create a correlated Host job result. |
| Semantic job expiry, cancel, audit | MQTT Session expiry (MQTT 3.1.1 has no client-side expiry field) is not a Paperbridge job state machine. |
| Exactly-once paper | Session persistence multiplies redelivery opportunities unless application dedupe survives reboot. |

### 1.3 Retained messages

**What they do**

If `RETAIN=1` on a Client→Server `PUBLISH`, the Server must store that
Application Message and its QoS so future matching subscribers can receive it.
On a new subscription, the last retained message on each matching topic name
must be sent. Only the **last** retained message per topic name is kept for
that purpose. A zero-byte retained payload clears the retained message.

Source: MQTT 3.1.1 §3.3.1.3

Bounded claims:

> “If the RETAIN flag is set to 1, in a PUBLISH Packet sent by a Client to a
> Server, the Server MUST store the Application Message and its QoS, so that it
> can be delivered to future subscribers whose subscriptions match its topic
> name.”

> “When a new subscription is established, the last retained message, if any,
> on each matching topic name MUST be sent to the subscriber.”

**What retained messages do not solve**

| Risk | Why retain is a poor durable job queue |
| --- | --- |
| Queue of multiple pending jobs | One retained message per topic name; a later job overwrites an earlier one. |
| Per-device offline backlog | Retain is last-value state, not a FIFO of semantic jobs. |
| Clear-on-ack / consume semantics | Subscribing re-sends the retained message; it is not removed by Device ACK. Clearing requires an explicit zero-byte retained publish. |
| Duplicate paper on every reconnect/resubscribe | New subscription delivers the retained job again. Without durable `job_id` suppression, each reconnect can print again. |
| Privacy / retention policy for print content | Spec says Server SHOULD retain until deleted by a Client; default lifetime is not a Paperbridge retention policy. |
| Paperbridge current contract | Architecture and protocol require non-retained jobs and results. |

### 1.4 Duplicates summary (standard)

MQTT 3.1.1 gives transport reliability, not semantic idempotency:

| Mechanism | Delivery promise | Application-visible duplicates |
| --- | --- | --- |
| QoS 0 | At most once | Loss possible; no transport redelivery |
| QoS 1 | At least once | Expected under retry / reconnect |
| QoS 2 | Exactly once **Control Packet** delivery of that message exchange | Still not a durable application job store; still not paper proof |
| CleanSession=0 offline queue | Replay pending QoS 1/2 to resumed session | Full backlog can reappear after offline period |
| Retain | Last message per topic to new subscribers | Same job can reappear on every new subscription |

None of these mechanisms:

- own Paperbridge job states (`accepted`, `pending`, `unknown`,
  `delivered_to_printer`, …)
- correlate Host waiter lifecycle with Device reboot
- prove paper emerged
- authorize Sender retry after `unknown`

---

## 2. EMQX-specific options relevant to offline delivery

Scope: official EMQX documentation. Deployment-product availability is noted
where the feature comparison page states it. Paperbridge Phase 2 currently
targets EMQX Serverless as a replaceable managed broker (ADR 0007).

### 2.1 Standard persistent sessions in EMQX (MQTT 3.1.1)

**What it does**

EMQX implements MQTT Session state. For MQTT 3.1.1, clients do not send Session
Expiry Interval; EMQX maps:

- `Clean Session = true` → session expiry interval 0 (session discarded on
  disconnect)
- `Clean Session = false` → use broker config `mqtt.session_expiry_interval`
  (documented default example: `2h`)

While a persistent session is valid, offline QoS 1/2 messages for that ClientId
accumulate and can be delivered on reconnect.

Sources:

- <https://docs.emqx.com/en/emqx/latest/durability/durability_introduction.html>
- <https://docs.emqx.com/en/emqx/v5.0/mqtt/mqtt-session-and-message-expiry.html>
- <https://docs.emqx.com/en/emqx/latest/configuration/mqtt.html>

Bounded claims:

> “For the clients using MQTT 3.\* protocol, EMQX derives the session expiry
> interval according to the following rule: if the Clean Session flag is true,
> then the session expiry interval is set to 0. Otherwise, the value of
> `mqtt.session_expiry_interval` configuration parameter is used.”

> “MQTT 3.1.1 does not give the option to specify when a Persistent Session will
> expire. But considering the resource consumed by sessions, EMQX offers a
> global configuration item for the session expiration duration”

**In-flight window and message queue (regular sessions)**

EMQX keeps unacked QoS 1/2 messages in a per-client Inflight Window
(`mqtt.max_inflight`, default 32). Overflow and offline traffic go to a
per-client Message Queue (`mqtt.max_mqueue_len`, default 1000). When that queue
is full, oldest messages are discarded. The same queue stores messages that
arrive while a persistent subscriber is offline.

Source: <https://docs.emqx.com/en/emqx/latest/design/inflight-window-and-message-queue.html>
and <https://docs.emqx.com/en/emqx/latest/configuration/mqtt.html>

Bounded claims:

> “If the Message Queue also reaches the length limit, subsequent messages will
> still be cached to the Message Queue, but the oldest message in the Message
> Queue will be discarded.”

> “The Message Queue is also used to store messages (including QoS 0 messages)
> that arrive while the subscriber is offline and that will be sent the next
> time the subscriber comes online.”

> “`max_mqueue_len` … maximum allowed queue length when persistent clients are
> disconnected or inflight window is full. Default: 1000”

**Regular vs durable session storage**

Without durable sessions enabled, EMQX “regular sessions” keep state in RAM of
the node that owns the session. Node restart loses that session state. Regular
sessions also bound the memory queue and can drop undelivered messages when the
limit is reached.

Source: <https://docs.emqx.com/en/emqx/latest/durability/durability_introduction.html>

Bounded claims:

> “Regular sessions: Sessions that keep their state in the memory of a running
> EMQX node. Their state is lost when the EMQX node restarts.”

> “EMQX imposes a limit on the size of the memory queue to prevent memory
> exhaustion. New messages are discarded when this limit is reached, potentially
> losing undelivered messages.”

Older EMQX 5.0 session docs also state memory-based persistent sessions and
note Enterprise external-database persistence / future disk session persistence
as separate reliability paths:
<https://docs.emqx.com/en/emqx/v5.0/mqtt/mqtt-session-and-message-expiry.html>

**What this does not solve**

Same physical duplicate risks as standard CleanSession=0, plus:

- finite offline queue drop under backlog
- possible loss of offline jobs on broker node restart (regular sessions)
- still no semantic `job_id` lifecycle or Host `unknown` reconciliation

### 2.2 EMQX Durable Sessions (disk-backed session/message storage)

**What it does**

Introduced in EMQX v5.7.0 (docs: disabled by default). When
`durable_sessions.enable = true` and session expiry interval is greater than 0,
EMQX stores session state and messages for durable subscribers on Durable
Storage (RocksDB + Raft replication). Messages to durable topic filters are
saved once per replica and replayed to durable sessions via iterators after
disconnect or node restart.

Sources:

- <https://docs.emqx.com/en/emqx/latest/durability/durability_introduction.html>
- <https://docs.emqx.com/en/emqx/latest/durability/management.html>

Bounded claims:

> “Durable sessions: Sessions that back up their state and received messages in
> the durable storage. They can be resumed after restart of the EMQX node.”

> “There is no upper limit on the number of undelivered messages, and undelivered
> messages are never discarded due to memory queue overrun.”

> “`durable_sessions.message_retention_period` … Defines the retention period of
> MQTT messages in durable sessions. Note: this parameter is global.”

Selection matrix from the same introduction page:

| `durable_sessions.enable` | Session Expiry Interval = 0 | Session Expiry Interval > 0 |
| --- | --- | --- |
| `false` | Regular | Regular |
| `true` | Regular | Durable |

**Deployment relevance for Paperbridge’s managed path**

EMQX feature comparison marks **Data Persistence** (built-in RocksDB backend)
for Self-Hosted Enterprise, and marks Serverless / Dedicated Flex reliability as
“Session persistence” rather than RocksDB data persistence. **Message Queue**
is ❌ on Serverless and ✅ on Dedicated Flex / Self-Hosted Enterprise.

Source: <https://docs.emqx.com/en/emqx/latest/getting-started/feature-comparison.html>

Bounded comparison facts:

- Data Persistence: Self-Hosted ✅ (RocksDB or external DBs); Serverless N/A;
  Dedicated Flex N/A
- Reliability row: Self-Hosted “Data persistence in RocksDB with highly
  available replication”; Serverless and Dedicated Flex “Session persistence”
- Message Queue feature: Self-Hosted ✅; Serverless ❌; Dedicated Flex ✅

Implication for issue #16: disk-backed Durable Sessions / RocksDB persistence
and the EMQX Message Queue product feature are **not** documented as portable
Serverless knobs Paperbridge can assume on the current managed path. Treat them
as provider-specific, plan-specific capabilities—not protocol contracts.

**What Durable Sessions do not solve**

| Risk | Why |
| --- | --- |
| Physical duplicate paper | Durable storage improves **survival** of the offline backlog; on reconnect it still redelivers QoS 1 messages. Without durable app idempotency, survival increases redelivery volume. |
| Semantic exactly-once | Storage iterators track broker consumption progress, not Paperbridge `job_id` completion across Device flash/reboot. |
| Host unknown / cancel / reconcile | Still no Host-side job state machine. |
| Broker-neutral contract | Enablement, retention period, replication, and plan availability are EMQX-specific. |
| Privacy of long-lived print payloads on broker disk | `message_retention_period` is a broker retention knob, not Owner privacy policy. |

### 2.3 EMQX Message Queue feature (named server-side queues, EMQX 6.0+)

**What it does**

A named, durable server-side buffer independent of subscriber availability.
Messages matching a configured topic filter are persisted; consumers subscribe
with `$queue/<name>` (optional topic filter suffix). Supports TTL/size/overflow
policies and optional last-value semantics. Queue delivery uses QoS 1.

Source: <https://docs.emqx.com/en/emqx/latest/message-queue/message-queue-concept.html>

Bounded claims:

> “A Message Queue in EMQX is a named, durable server-side buffer that stores
> MQTT messages independently of subscriber availability.”

> “Unlike traditional MQTT behavior, Message Queues persist messages even when
> no clients are online.”

> “All messages in Message Queues are delivered with QoS 1 (at-least-once),
> regardless of the QoS level used when publishing or subscribing.”

Docs also state MQTT shared subscriptions still do not retain messages when no
subscribers are online, and lack TTL/size/lifecycle controls—motivation for this
extension.

**What it does not solve**

- Not standard MQTT 3.1.1; requires EMQX Message Queue and `$queue/...`
  consumption.
- Documented ❌ on Serverless in feature comparison.
- Still at-least-once to the Device; does not replace `job_id` idempotency.
- Last-value mode drops prior jobs for the same key (can lose paper work).
- Pulls Paperbridge contracts toward an EMQX-specific queue API if used as the
  product job store.

### 2.4 Offline Messages plugin (external DB)

**What it does**

Enterprise plugin persists selected topic messages to MySQL or Redis so a
subscriber can retrieve them after reconnect even if disconnected at publish
time. Intended when “standard MQTT session persistence is not enough”, e.g.
retention must outlive a session or other systems need message history.

Source: <https://docs.emqx.com/en/emqx/latest/extensions/plugin-catalog/emqx-offline-messages.html>

**What it does not solve**

- Plugin / external DB path is EMQX-extension-specific, not broker-neutral.
- Replay still yields at-least-once application delivery.
- History in MySQL/Redis is not a Paperbridge audit/job state model unless the
  application defines one.
- Not part of ADR 0007’s “replaceable standard MQTT traffic” boundary.

### 2.5 Retained messages in EMQX

EMQX implements standard retain: last retained message per topic; new
subscribers receive it; empty retained payload clears. Dashboard docs: default
expiration is never, unless manually deleted (operator-configurable elsewhere).

Sources:

- <https://docs.emqx.com/en/emqx/latest/messaging/mqtt-retained-message.html>
- (dashboard) <https://docs.emqx.com/en/emqx/latest/dashboard/retained.html>

Same structural limits as §1.3. Feature comparison: MQTT Retainer ✅ on
Serverless, Dedicated Flex, and Self-Hosted.

### 2.6 Rule engine / webhooks (relevance only)

Feature comparison shows Webhook / HTTP Server ✅ on Serverless. Rules can copy
MQTT events to external systems. That can help **Host-side** durable intake or
audit if the application owns storage, but:

- it is not Device offline delivery by itself
- it is provider integration surface, not a Paperbridge protocol type
- using it as the job source of truth would fork behaviour between Mosquitto
  (local) and EMQX (cloud)

For issue #16, treat rules/webhooks as optional **application integration**, not
as the Device delivery contract.

---

## 3. Comparison matrix (durable semantic delivery lens)

| Capability | Standard MQTT 3.1.1? | Offline backlog | Survives broker node restart | Multi-job queue | App duplicates without `job_id` store | Fits current non-retained QoS 1 contract | Broker-neutral |
| --- | --- | --- | --- | --- | --- | --- | --- |
| QoS 1 | Yes | No (alone) | N/A | No | Yes (expected) | Yes (already used) | Yes |
| CleanSession=0 + QoS 1 | Yes | Yes (session pending msgs) | Implementation-defined | Per-session, bounded by broker | Yes on reconnect drain | Yes if still non-retained | Yes (flags/QoS) |
| Retained job message | Yes | Last-value only | Usually yes (retain store) | **No** (one per topic) | Yes on each new subscription | **No** (contract forbids retain) | Yes |
| EMQX regular persistent session + mqueue | MQTT behaviour + EMQX limits | Yes, max_mqueue_len | **No** (RAM session) | Bounded; drops oldest | Yes | Yes | Limits are EMQX-specific |
| EMQX Durable Sessions | EMQX extension of sessions | Yes; retention_period | **Yes** (DS) | Large/unbounded vs mqueue | Yes | Yes at wire level | **No** |
| EMQX Message Queue (`$queue`) | **No** | Yes | Yes (uses DS) | Named queues + policies | Yes (QoS 1) | Requires non-standard consume path | **No** |
| EMQX offline-messages plugin | **No** | Yes (external DB) | Depends on DB | Topic history | Yes | Extra plugin path | **No** |
| Host/app durable job store + idempotent Device | Application (not MQTT) | Yes if app republishes carefully | Yes if app storage durable | Yes | Preventable with durable `job_id` | Yes | Yes |

---

## 4. Physical duplicate-output risk (what nothing above closes alone)

Paperbridge’s dangerous transition is not “MQTT message lost”. It is:

1. Device accepts ownership of a semantic job (`job_id`).
2. Device writes bytes to the printer socket (`delivered_to_printer`) **or**
   crashes after partial/full write.
3. Transport or operator causes the **same** or **equivalent** job to run again.
4. A second physical receipt emerges.

| Scenario | MQTT mechanism effect | Still open without app durability |
| --- | --- | --- |
| QoS 1 redelivery same connection | Possible duplicate PUBLISH | One-boot ledger can return `duplicate` |
| Disconnect before Device PUBACK to broker | Broker/session redelivers on resume | Same as above if ledger still has `job_id` |
| Device reboot after print, ledger empty | Persistent session may redeliver offline/unacked jobs | **Second paper** |
| Device reboot, CleanSession=1 | Jobs not replayed by session | Job **lost**; Host may be `unknown` |
| Host timeout `unknown` then Sender retries new `job_id` | New Application Message | **Second paper** if first already printed |
| Host timeout `unknown` then republish same `job_id` | Redelivery / second publish | Safe only if Device durable idempotency exists |
| Retained print-job topic | Every resubscribe gets last job | **Second paper** / lost intermediates |
| Durable Sessions / Message Queue survive broker restart | Backlog preserved | Preserved backlog **increases** replay chances after Device reboot |
| Broker queue full (max_mqueue_len) | Oldest dropped | Silent loss, not duplicate—but not honest job state |

Conclusion from the sources: **broker durability and QoS are transport tools**.
They do not provide Paperbridge’s required distinctions among accepted,
dispatched, unknown, delivered_to_printer, rejected, failed, and manually
reconciled work. They also never prove `printed`.

---

## 5. Recommendation (broker-neutral contracts)

1. **Keep the wire contract broker-neutral.** Continue to define product traffic
   as MQTT 3.1.1, QoS 1, non-retained, versioned topics, and semantic payloads
   (`print-job.v1` / `job-result.v1`). Do not put Durable Sessions, `$queue`,
   retain-as-job-buffer, offline plugins, or rule/webhook fan-out into the
   public/device protocol contract.

2. **Treat MQTT QoS 1 + optional persistent sessions as reconnect transport
   only.** They may reduce loss while a Device ClientId session remains valid.
   They must not be the system of record for job lifecycle and must not authorize
   automatic Sender retry after `unknown`.

3. **Put durable semantic state in Paperbridge application components**, not in
   broker features:
   - Host/service: durable acceptance and terminal/unknown state keyed by
     `job_id` (and Sender-visible recovery rules).
   - Device: durable idempotency for completed `job_id`s across reboot (stronger
     than one-boot RAM), still reporting `duplicate` without a second printer
     delivery when safe.
   - Explicit human/manual reconcile path for `unknown` that never equates
     timeout with “retry print”.

4. **Do not use retained messages as a job queue.** Spec and EMQX behaviour are
   last-value-per-topic; that both drops earlier jobs and re-delivers the last
   job to new subscriptions—bad for physical inbox semantics and privacy.

5. **Classify EMQX-only offline hardening as optional infrastructure**, evaluated
   per deployment tier:
   - Serverless: do not assume RocksDB Durable Sessions or Message Queue from
     the feature comparison page; assume standard session persistence behaviour
     only unless a current Serverless doc explicitly enables more.
   - Self-hosted Enterprise / Dedicated Flex: Durable Sessions or Message Queue
     may reduce **broker-side** loss, but still require the application
     idempotency model above.
   - Local Mosquitto: must remain a first-class dev path; any design that only
     works with EMQX queues fails ADR 0007 replaceability.

6. **For issue #16 design work, answer ownership questions in application
   terms:**
   - Who records “accepted” before Device is online?
   - Who may create a new `job_id` vs reuse one?
   - What Device storage survives reboot for dedupe?
   - What Host shows for `unknown`, and what operator action is allowed?
   - What retention/expiry applies to job payloads and results in **app**
     storage, independent of `session_expiry_interval` /
     `message_retention_period`?

Broker settings (`session_expiry_interval`, `max_mqueue_len`, durable session
retention) are operational tuning under that model, not substitutes for it.

---

## 6. Source register (URLs)

| Topic | URL |
| --- | --- |
| MQTT 3.1.1 OASIS Standard (HTML) | <https://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html> |
| EMQX Durable Sessions intro | <https://docs.emqx.com/en/emqx/latest/durability/durability_introduction.html> |
| EMQX Durable Sessions management | <https://docs.emqx.com/en/emqx/latest/durability/management.html> |
| EMQX session/message expiry (v5.0) | <https://docs.emqx.com/en/emqx/v5.0/mqtt/mqtt-session-and-message-expiry.html> |
| EMQX MQTT configuration | <https://docs.emqx.com/en/emqx/latest/configuration/mqtt.html> |
| EMQX inflight / message queue | <https://docs.emqx.com/en/emqx/latest/design/inflight-window-and-message-queue.html> |
| EMQX Message Queue concept | <https://docs.emqx.com/en/emqx/latest/message-queue/message-queue-concept.html> |
| EMQX offline messages plugin | <https://docs.emqx.com/en/emqx/latest/extensions/plugin-catalog/emqx-offline-messages.html> |
| EMQX retained messages | <https://docs.emqx.com/en/emqx/latest/messaging/mqtt-retained-message.html> |
| EMQX feature comparison (Serverless vs Enterprise) | <https://docs.emqx.com/en/emqx/latest/getting-started/feature-comparison.html> |

## Non-claims

- No code, schema, ADR, or issue body was changed by this research.
- No physical offline-delivery test was run.
- No assertion that EMQX Serverless currently exposes Durable Sessions
  configuration; feature comparison suggests RocksDB data persistence / Message
  Queue are not Serverless features.
- No recommendation to enable persistent sessions on the Device today; that is a
  later design choice under issue #16.
