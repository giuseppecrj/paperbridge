# ADR 0010: Use MQTT Device events for diagnostics

- Status: Proposed
- Date: 2026-08-12
- Amends: ADR 0009 no-logging-vendor boundary

## Decision at a glance

Paperbridge will add one versioned Device diagnostic-event stream at
`v1/devices/{device_id}/events`. The Device will publish closed,
privacy-minimized events over MQTT 3.1.1 with QoS 1 and `retain=false`.
Event producers will only append to a bounded, thread-safe RAM ring. A dedicated,
outbound-only telemetry MQTT client and execution lane will publish one event at
a time and retain the ring head until the matching PUBACK arrives.

This is broker-acknowledged, duplicate-prone delivery from the Device to the
broker. The complete Device-to-Axiom path is bounded, volatile, and best effort.
It may lose or duplicate events during Device reset, API absence or restart,
queue overflow, or sink failure.

The existing API container will consume and validate events, add a separate
backend-observed UTC time, perform bounded recent-event deduplication, and
forward events through a bounded in-memory queue to Axiom Personal in US East 1
over outbound HTTPS. Axiom is a replaceable operational sink, not part of the
Device event contract. Its outage must never change print delivery, API health,
or API readiness.

This capability observes and reports. It does not actively probe the Printer,
restart the W5500, diagnose a cause from one signal, or claim that paper emerged.
It does not change ADR 0008's durable Semantic Print Job design.

ADR acceptance is blocked on an explicitly authorized, no-output,
purchased-Device prototype proving that the second MQTT/TLS client fits the
Device and does not interfere with the existing Job path.

## Context and problem statement

The purchased Device can observe the direct W5500 link as down after Printer
power, cable, or long-standby changes. Recovery has sometimes required a Printer
power cycle. Current evidence records a recovery sequence, not a root cause.
MicroPython 1.28 can also expose stale LAN event status during Wi-Fi recovery,
while a separate TCP probe can still show the Printer Endpoint as Reachable.
Checking status after a failure therefore cannot establish when the transition
occurred or which dependency failed first.

Paperbridge currently has three incomplete diagnostic surfaces:

- `firmware/micropython/src/ethernet.py` returns current W5500 status but keeps no
  transition history;
- `firmware/micropython/src/logging.py` writes NDJSON only to its supplied
  stream, which requires an attached Host to retain it; and
- `packages/protocol/schemas/device-event.v1.schema.json` exists, but it has no
  live publisher or consumer. Firmware does not publish `/events`. The unused
  schema requires UTC `created_at`, requires `event_id`, and permits an open
  `data` object. Those fields do not meet this decision's identity, clock, and
  privacy boundaries.

The Wi-Fi/MQTT control plane is independent of the direct W5500 Printer link.
That makes MQTT suitable for reporting W5500 transitions without requiring the
Device to stay connected to a Host. MQTT remains transport rather than the
system of record: QoS 1 permits duplicate delivery, and PUBACK proves broker
receipt only. It does not prove that the API or Axiom accepted an event.

The current Device uses one `umqtt.simple` client on one polling path. Its QoS 1
`publish()` waits synchronously for PUBACK through `wait_msg()`. On a subscribed
client, `wait_msg()` can invoke the message callback while a publish is waiting;
a callback can then publish a Job Result synchronously. This creates blocking,
reentrancy, and concurrent acknowledgement risks for spontaneous events.
Telemetry must not share that stock execution path.

The current Job Result path already uses stock synchronous QoS 1 publication
without a bounded PUBACK timeout. This ADR does not claim to fix that existing
risk. Its telemetry prototype and acceptance must prove that the added client,
TLS memory, scheduling, and reconnect behavior do not make the Job path worse.

The decision must support unattended diagnosis without turning diagnostic
availability into a dependency of the Physical Inbox. It must preserve the
project's distinction between Device, Printer, Reachable, Delivered to Printer,
and Printed.

## Decision drivers

- Capture the order and timing of failures while the Device is unattended.
- Distinguish Wi-Fi, MQTT, W5500 link, and Printer transport observations.
- Preserve honest semantics when one status source is stale or incomplete.
- Keep diagnostic memory, payloads, rates, retries, and failure effects bounded.
- Exclude receipt content, credentials, personal data, and unbounded error text.
- Reuse broker-neutral MQTT 3.1.1 and the existing API container.
- Tolerate duplicates, gaps, reconnects, invalid clocks, and sink outages.
- Isolate telemetry socket ownership and PUBACK waiting from the Job client.
- Avoid flash wear and crash-consistency work until evidence requires durability.
- Keep the protocol and local tests independent of Axiom.
- Require production identity and authorization boundaries suitable for a fleet,
  even though the current service supports one Device and one private operator.

## Considered diagnostic designs

| Option | Unattended evidence | Offline and reboot behavior | Contract and security boundary | Operational footprint | Primary cost |
| --- | --- | --- | --- | --- | --- |
| Host-attached serial logs only | Captures detail only while a Host remains attached and awake | Host capture may survive Device reboot; no evidence when detached | No new broker authority, but no production remote path | Smallest firmware change | Cannot diagnose normal unattended operation |
| Live MQTT events on the existing Job client | Captures transitions while connected | Loses events during publish interruption and on restart | One client and credential | Smallest MQTT change | Stock synchronous QoS 1 publication can block or re-enter the Job path |
| **Dedicated MQTT event client, bounded Device RAM replay, existing API consumer, and replaceable managed sink** | **Captures structured transitions and heartbeats without a Host** | **Replays the remaining ring after short MQTT interruptions; reset and queue overflow may lose evidence** | **Closed schema, separate socket ownership, exact ACLs, backend validation** | **A second Device MQTT/TLS session, two bounded queues, and one HTTPS sink** | **Measured Device feasibility is not yet proven** |
| Events plus retained state and a separate collector | Adds immediate last-known state and independent scaling | Retained state can remain stale; collector durability depends on its storage | More topics, credentials, and lifecycle semantics | Another service and deployment path | No current consumer or load justifies it |
| Flash-backed Device journal and durable backend outbox | Preserves more evidence across reboot and long outages | Can provide crash-safe replay after explicit application acknowledgement | Requires journal format, corruption policy, acknowledgement protocol, and migrations | Highest Device and backend complexity | Flash wear, fault injection, recovery, and support obligations before need is proven |

The proposed option is the smallest design that isolates spontaneous QoS 1
events from the existing subscribed Job client. It remains a candidate until the
purchased-Device prototype passes. Failure triggers reconsideration of a bounded,
single-owner MQTT state machine. It never permits a silent fallback to QoS 0 or
to stock same-session publication.

## Considered managed sinks

Current vendor capabilities and prices must be rechecked before rollout.
Unverified details are not acceptance evidence.

| Sink | Direct bounded ingest | Published retention and region | Governance in selected tier | Additional operation | Fit |
| --- | --- | --- | --- | --- | --- |
| Existing journald only | API can write structured stdout | VM retention and remote search guarantees are undocumented | Existing private VM access | Host storage, rotation, and retrieval | Does not provide the selected managed incident window |
| **Axiom Personal** | **Structured HTTPS ingest with a dataset-scoped token** | **30 days; this decision selects US East 1** | **One private operator; no selected-plan RBAC, audit logs, or SLA** | **No Host collector or new inbound port** | **Selected for the private one-Device MVP** |
| Better Stack | Direct HTTPS JSON or OTLP is documented | Germany region and configurable source retention are documented; exact free-tier limits were not verified | Selected-plan access/audit capabilities were not verified | Direct HTTPS avoids its comparatively large collector | Viable replacement after account-level verification |
| Grafana Cloud | Direct OTLP is documented | Published free log allowance has 14-day retention; EU-region fit was not verified | Selected-plan access/audit capabilities were not verified | Grafana recommends Alloy for broader production collection | Prefer only if broader Grafana metrics/traces justify it |

Axiom Personal is selected for a private MVP with one operator and a
privacy-minimized schema. Before adding another operator, a customer fleet,
sensitive diagnostic fields, an access-audit requirement, or a service-level
requirement, Paperbridge must upgrade to a tier with the needed governance or
select another sink. No Paperbridge contract depends on Axiom field names,
query language, agent, SDK, price, or free-plan entitlement.

## Decision outcome

### Event contract

A Device event is a bounded, immutable observation emitted by the Device. It is
not a Job Result, a mutable Device shadow, a free-form log line, or proof of
Printer output.

The first schema version permits exactly these event names:

- `device.booted`
- `device.heartbeat`
- `ethernet.link_changed`
- `wifi.connection_changed`
- `mqtt.connection_changed`
- `printer.transport_failed`
- `diagnostics.events_dropped`

The shared protocol package will replace the current permissive, unused
`device-event.v1` shape with closed per-event payloads. Unknown fields, event
names, and schema versions fail validation and are counted without forwarding.
Every field and encoded event has an explicit bound. Events contain stable
machine values such as prior/new state, raw status, transport phase, stable
error code, elapsed duration, or bytes accepted when relevant. They exclude:

- print text, raster data, QR data, or raw Printer bytes;
- Owner, Sender, or Recipient data;
- credentials, certificates, headers, or tokens;
- Wi-Fi SSID/BSSID, MAC addresses, and Printer Endpoint details; and
- raw exception text or an arbitrary extension object.

The identities and times remain distinct:

| Field | Meaning |
| --- | --- |
| `device_id` | Stable logical Device identity |
| `boot_id` | Opaque event-epoch identity created at every Device boot |
| `sequence` | Strictly increasing event order within one `boot_id` |
| `uptime_ms` | Monotonic Device time for ordering and durations within one boot |
| optional Device UTC | RFC 3339 occurrence time included only after valid clock synchronization |
| backend-observed UTC | UTC time recorded when the API accepts the event |

The authoritative event identity is `(device_id, boot_id, sequence)`. There is
no separate `event_id` in the Device contract. A sink adapter may derive one
canonical string from that tuple, but it does not create another identity.
Sequence must never wrap within one event epoch. Its width must cover the
supported maximum uptime and event rate; before exhaustion the Device must start
a fresh opaque event epoch rather than reuse a tuple. The exact representation
is an implementation detail confirmed by boundary tests.

Monotonic uptime is not UTC and does not establish ordering across event epochs.
The backend does not overwrite Device occurrence evidence with its observed
time. Gaps and duplicates remain visible through `boot_id` and `sequence`.

### MQTT transport and Device buffering

The Device publishes events only to:

```text
v1/devices/{device_id}/events
```

The topic uses MQTT 3.1.1, QoS 1, and `retain=false`. Heartbeats share this event
stream because they have the same authorization, retention, and delivery
semantics. This decision adds no `/telemetry`, retained `/state`, or event
acknowledgement topic.

Event producers append only to a bounded, thread-safe RAM ring. They never call
an MQTT client. If the ring is full, it drops the oldest entry, increments
bounded drop counters, and later emits `diagnostics.events_dropped`. A Device
reset loses the ring.

A dedicated outbound-only telemetry MQTT client and separate execution lane own
event publication. The client uses:

- MQTT 3.1.1 with a unique client ID and clean session;
- a unique socket with one owner and no subscriptions or message callback;
- the Device principal's exact `/events` publish-only ACL;
- one QoS 1, non-retained event in flight;
- retention of the ring head until the matching PUBACK;
- a bounded socket timeout; and
- close-and-reconnect with bounded backoff after timeout, protocol error, or
  transport failure, while retaining the ring head.

The telemetry client must match PUBACK to the in-flight packet identifier.
Packet-identifier exhaustion and wrap must be handled without ambiguity; the
exact approach remains an implementation detail and acceptance boundary.

The existing subscribed Job client remains separate. Stock same-session
`umqtt.simple.publish()` is rejected for spontaneous telemetry because its
blocking `wait_msg()` can process callbacks reentrantly and does not provide the
required isolation for concurrent acknowledgement flows. A second client is not
a claim that unmodified `umqtt.simple` already satisfies every timeout and
packet-ID requirement; the prototype must verify the bounded client behavior.

One `device.heartbeat` is produced every 60 seconds. The interval is configurable
for acceptance and later operations, but 60 seconds is the v1 production value.
A heartbeat reports bounded current diagnostic state and never contacts the
Printer.

A successful telemetry PUBACK allows the Device to remove the ring head. It
proves broker receipt only. The broker can acknowledge while the clean-session
API consumer is absent, so the end-to-end path can lose that event. A crash
after broker receipt but before ring removal can replay it.

Diagnostic collection and publication must not block rendering, Printer
transport, serial RPC, the Job client's inbound polling, or Job Result handling.
An unavailable broker, telemetry session, full ring, invalid event, or
telemetry error degrades diagnostics only.

No heartbeat or event starts an active Printer probe. `printer.transport_failed`
records failures from an already-authorized delivery or explicit diagnostic
operation; it does not create Printer traffic. No event automatically reconnects
Ethernet, restarts the W5500, retries a Semantic Print Job, or recovers a Printer.

### API ingestion and managed sink

The existing API container subscribes to the event topic for its configured
Device. It validates the closed schema and Device identity, enforces the event
byte bound, and adds backend-observed UTC before forwarding.

The API maintains a bounded in-memory recent-identity set keyed by
`(device_id, boot_id, sequence)`. It exposes duplicate and eviction counters.
Eviction or API restart can allow a duplicate to reach Axiom; deduplication is an
optimization, not a durable guarantee.

The API forwards accepted events through a bounded in-memory, drop-oldest queue
to an Axiom Personal dataset in US East 1 over outbound HTTPS. It sends only an
allowlisted structured representation, not raw MQTT payloads. The selected plan
has a 30-day raw-event retention window and one private operator. It has no
selected-plan RBAC, audit logs, or SLA.

Axiom latency, rejection, rate limits, credential failure, or outage must not
change `/health`, `/ready`, Job acceptance, Job Result waiting, Device MQTT
connectivity, or Printer delivery. The API queue drops oldest on overflow and
records bounded forwarding/drop counters through its operational logs. There is
no API disk spool in v1. End-to-end forwarding is volatile and best effort.

Paperbridge schemas, MQTT topics, event identity, and tests must not depend on
Axiom-specific fields, query language, agents, or SDKs. Local integration tests
use a fake HTTP sink. One Device does not justify a separate collector or an
embedded OpenTelemetry SDK.

The backend marks a Device `not observed` internally when it has accepted no
heartbeat for five minutes. This means only that Paperbridge has not observed a
heartbeat through the Device, Wi-Fi, broker, API, and consumer path. It does not
prove which component failed. Initial alerts are internal operator alerts only;
a single link transition does not page an operator or notify an Owner.

### Production identity and authorization gates

Production diagnostic events require:

- a unique high-entropy Device credential over verified TLS;
- separate Device and API MQTT principals;
- deny-by-default broker authorization;
- exact per-Device publish and subscribe topic ACLs; and
- independent restrictions on topic direction, QoS, and retained publication.

The Device principal may publish only its exact event, Job Result, and probe
status topics and subscribe only to its exact Print Job and probe request topics.
The API principal has the inverse authority required for the same Device.
Neither principal receives wildcard, cross-Device, broker-administration, or
retained-event authority. The dedicated telemetry connection has its own client
ID but uses only the Device principal authority required to publish `/events`.
Broker policy must permit and bound that second connection.

Authentication does not derive from `device_id`, MQTT client ID, or a topic
string. API MQTT and Axiom secrets use ADR 0009's encrypted systemd credential
boundary. The separate Device MQTT credential uses the existing Fnox-generated
Device provisioning workflow. This ADR requires tested replacement and
revocation but does not invent a new Device secure-storage mechanism.

Mutual TLS is not required for v1. It remains a follow-up after certificate
provisioning, storage, rotation, revocation, and purchased-Device behavior are
proven. MQTT transport security and ACLs do not provide broker-independent,
end-to-end event provenance; signed events are outside this threat model.

### Decision boundaries

This decision:

- establishes reusable Device diagnostic events, beginning with Ethernet
  diagnosis;
- amends ADR 0009 only by allowing the existing API container to use Axiom
  Personal as a replaceable managed sink and to mount one additional encrypted
  credential;
- does not change ADR 0009's image, systemd, read-only filesystem, loopback HTTP,
  private proxy, hardening, deployment, or digest rollback decisions;
- does not alter ADR 0008's durable Semantic Print Job authority, receipts,
  Unknown Delivery Result, or manual reconciliation design;
- does not fix the existing synchronous Job Result PUBACK wait;
- does not make telemetry a condition of API or Physical Inbox availability;
- does not claim that a Printer is Reachable from W5500 status alone;
- does not claim Delivered to Printer from a link or probe observation; and
- never claims Printed without reliable Printer status.

Deferred decisions are flash-backed or API-durable observability, a retained
state topic, MQTT Last Will, MQTT 5, a separate collector, mTLS, Owner-facing
alerts, automatic Printer probes, active recovery, and automatic W5500 recovery.

## Consequences

### Benefits

- Link and control-plane transitions can be observed without a USB-attached Host.
- One timeline can correlate boot, heartbeat, Wi-Fi, MQTT, Ethernet, and Printer
  transport observations without conflating their meanings.
- Sequence gaps and duplicate events are explicit rather than silently hidden.
- A 30-day managed search window supports the initial one-Device investigation.
- The event contract stays broker- and sink-neutral.
- Bounded RAM avoids flash wear and a premature crash-safe journal.
- A dedicated outbound connection isolates spontaneous event PUBACK handling
  from the subscribed Job client's callbacks.

### Costs and operational obligations

- The Device adds a second MQTT/TLS client, socket, execution lane, RAM ring, and
  reconnect state. Their heap, scheduling, and Wi-Fi effects are not yet
  physically proven.
- Only Device-to-broker QoS 1 is broker-acknowledged and duplicate-prone. The
  complete path can lose or duplicate events after Device reset, API absence or
  restart, identity-set eviction, queue overflow, or sink failure.
- The API gains an MQTT subscription, validation path, bounded identity set,
  bounded worker queue, outbound dependency, credential, and drop monitoring.
- Operators must maintain separate MQTT principals, exact ACLs, Axiom retention,
  token rotation/revocation, and incident-access discipline.
- Axiom Personal provides no selected-plan RBAC, audit logs, or SLA. Its one
  private operator is an explicit MVP limitation.
- Event byte and rate limits must protect Device heap, broker capacity, API
  memory, and managed-ingest quotas.
- The five-minute threshold detects absence, not root cause, and can produce an
  internal alert during internet or broker outages.
- Vendor limits, pricing, region, and service terms must be rechecked before
  implementation and capacity review.

### Compatibility effects

Existing probe, Print Job, and Job Result topics and payloads remain unchanged.
The current unused `device-event.v1` schema is replaced before any live producer
or consumer exists, so no deployed compatibility promise is broken. Older
firmware publishes no events; the API treats that as unsupported capability,
not immediate failure, until rollout marks the Device event-capable.

Disabling the consumer or Device publisher leaves print delivery unchanged.
Because events are non-retained and buffers are volatile, rollback does not
replay old observations into an older release.

## Confirmation

### Contract and Host tests

- Shared-schema fixtures accept all seven event names and reject unknown
  versions, names, fields, unbounded values, private content, and oversized
  encoding.
- Topic tests prove exact `v1/devices/{device_id}/events`, QoS 1, and
  `retain=false` behavior without changing existing topics.
- Clock tests prove monotonic uptime is not emitted as UTC, optional UTC appears
  only after valid synchronization, and backend-observed UTC remains separate.
- Identity tests cover duplicate, gap, epoch rotation, reboot, and out-of-order
  cases by `(device_id, boot_id, sequence)` and prove sequence never wraps within
  one event epoch.

### Device and simulator tests

- Transition tests emit only on state change, plus boot and 60-second heartbeat.
- No-output tests prove heartbeats and link observation never open a Printer
  socket.
- Ring tests prove fixed bounds, thread-safe producer behavior, oldest-first
  replay, removal only after matching PUBACK, duplicate replay after interrupted
  acknowledgement, drop-oldest overflow, and exact dropped-event counts.
- Client tests prove one event in flight, packet-ID matching, bounded socket
  timeout, retained ring head on failure, session close, and bounded reconnect
  backoff.
- Delayed or missing PUBACK, rapid link flap, broker disconnect, reconnect,
  invalid clock, and Device reset tests preserve the documented volatile loss
  boundary.
- Concurrency tests prove the telemetry lane cannot invoke the Job callback,
  consume a Job PUBACK, or own the Job client's socket.

### Required purchased-Device feasibility gate

Before this ADR can be accepted, an explicitly authorized no-output prototype on
the purchased Device must run the Job and telemetry MQTT 3.1.1 clients together
over verified TLS. It must measure and record:

- baseline and worst-case free heap with both TLS sessions;
- scheduling behavior and Wi-Fi stack stability;
- delayed and missing telemetry PUBACK isolation;
- telemetry timeout, close, reconnect, and bounded backoff;
- continued Job receive/result behavior without increased failure;
- continued serial RPC availability; and
- a bounded coexistence soak without Printer output.

The prototype must also record the existing stock Job Result client's
synchronous, potentially unbounded PUBACK wait as a separate risk and prove that
telemetry does not worsen it. Host tests cannot satisfy this hardware gate.

Failure rejects the dedicated-client candidate. The next option is a bounded,
single-owner MQTT state machine evaluated in a separate decision or amendment.
There is no fallback to QoS 0 or stock same-session telemetry.

### API and local sink tests

- The API validates Device identity and schema before forwarding.
- A bounded recent-identity set proves duplicate handling, deterministic
  eviction, restart behavior, and observable duplicate/eviction counters.
- A local fake HTTP sink proves the payload allowlist, backend-observed UTC,
  authentication handling, timeouts, rejection, bounded retry, queue behavior,
  recovery, and secret-free logs without contacting Axiom.
- Queue tests prove fixed memory, drop-oldest overflow, and observable drop
  counters.
- Sink latency and outage tests prove `/health`, `/ready`, REST, MCP, MQTT Job
  Results, shutdown draining, and Printer-simulator delivery remain independent.
- Container acceptance proves outbound HTTPS works with the existing non-root,
  read-only, no-capability image and encrypted credential mount, without a new
  inbound port or writable filesystem requirement.

### Live vendor acceptance

An Owner-authorized, no-output acceptance against the selected Axiom account
must verify separately from the fake sink:

- the exact US East 1 dataset and ingest endpoint;
- a dataset-scoped ingest-only token;
- the published 30-day Personal retention;
- deletion behavior and one-operator access;
- absence of selected-plan RBAC, audit logs, and SLA as recorded limitations;
- queryability of allowlisted fields; and
- API behavior during vendor rejection and outage.

This acceptance does not contact the Printer and does not prove Device or
Printer reachability.

### Security gates

- Broker acceptance denies shared API/Device credentials, wildcard topics,
  cross-Device access, reversed publish/subscribe direction, retained events,
  disallowed QoS, and broker administration.
- Production acceptance verifies separate API and Device principals, the
  telemetry client's unique client ID, hostname and CA validation, credential
  replacement, revocation, bounded payload/rate policy, and secret-free logs.
- Axiom acceptance verifies the scoped ingest token and explicitly records the
  selected Personal plan's governance limitations.

### Physical no-output acceptance

After Host, container, security, and feasibility gates pass, an explicitly
authorized no-output hardware run records boot, heartbeat, Wi-Fi/MQTT
transitions, and direct W5500 link transitions during cable, Printer power, and
long-standby scenarios. It verifies that no diagnostic action prints, feeds,
cuts, reboots, flashes, resets the W5500, or changes Printer networking. A
separate existing Printer probe may be run only as an explicit diagnostic and
must remain labeled Reachable or failed, never Printed.

The run records whether each signal was documented, Host-tested,
simulator-tested, or physically verified. It must not infer the standby root
cause from one event source.

## Delivery and rollback

Deliver in independently reviewable gates:

1. Replace the unused shared schema with the closed event contract, fixtures,
   topic helper, and Host validation tests.
2. Prototype the dedicated telemetry MQTT/TLS client on the purchased Device and
   keep this ADR Proposed until the feasibility gate passes.
3. Add Device transition observation, identity/time handling, bounded
   thread-safe RAM ring, serial diagnostics, and MQTT publication without active
   recovery.
4. Add the API subscription, bounded deduplication, bounded forwarding queue,
   and fake HTTP sink tests.
5. Provision separate development and production MQTT principals, exact ACLs,
   and encrypted API-side Axiom credentials; production remains blocked until
   the security gates pass.
6. Accept Axiom Personal US East 1 and its explicit governance limitations with
   no-output checks, then run the authorized physical diagnostic scenario.

Each gate preserves existing Print Job behavior. Rollback first disables Axiom
forwarding and removes its API-side credential, then rolls back the API image
through ADR 0009's digest mechanism. Device event publication and its telemetry
session can be disabled independently. No rollback republishes, translates, or
retains events. Active recovery requires a separate decision based on captured
evidence.

## Evidence and related decisions

| Evidence | Relevance |
| --- | --- |
| `CONTEXT.md` | Canonical Device, Printer, Reachable, Delivered to Printer, and Printed language |
| `docs/architecture.md` | Existing MQTT 3.1.1 topics, QoS 1/non-retained boundary, one API container, and direct W5500 path |
| `docs/testing.md` | Stale MicroPython LAN-status observation and Host/simulator/physical evidence boundaries |
| `firmware/micropython/src/app.py` | One current Wi-Fi/MQTT polling path and serial-thread composition |
| `firmware/micropython/src/mqtt_adapter.py` | Implemented clean-session MQTT probe/job adapter; synchronous Job Result publication; no event publisher |
| `firmware/micropython/src/ethernet.py` | Implemented current W5500 status and guarded reconnect; no transition history |
| `firmware/micropython/src/logging.py` | Implemented stream-local NDJSON logging only |
| `packages/protocol/schemas/device-event.v1.schema.json` | Permissive unused artifact that must be replaced before activation |
| ADR 0003 | Bounded, versioned semantic trust-boundary precedent |
| ADR 0004 | Honest Printer transport semantics |
| ADR 0007 | Managed MQTT/TLS and broker-neutral MQTT 3.1.1 boundary |
| ADR 0008 | Separate durable Semantic Print Job authority and receipt design |
| ADR 0009 | Existing hardened API container, encrypted API credential, and rollback boundary amended here |
| [MQTT 3.1.1](https://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html) | QoS 1, PUBACK, retained-message, session, and security semantics |
| [MicroPython `time`](https://docs.micropython.org/en/v1.28.0/library/time.html) | Monotonic tick origin, wrap, and clock limitations |
| [MicroPython `umqtt.simple`](https://github.com/micropython/micropython-lib/blob/master/micropython/umqtt.simple/umqtt/simple.py) | Synchronous QoS 1 PUBACK wait, callback behavior, MQTT 3.1.1, clean session, and client limits |
| [NISTIR 8259A device identity](https://pages.nist.gov/FederalProfile-8259A/technical/identity/) | Unique Device identity and authentication capability |
| [NISTIR 8259A data protection](https://pages.nist.gov/FederalProfile-8259A/technical/protection/) | Data minimization, secure storage, and credential-change obligations |
| [OpenTelemetry log data model](https://opentelemetry.io/docs/specs/otel/logs/data-model/) | Event occurrence and observed-time distinction; backend translation only |
| [Axiom ingest API](https://axiom.co/docs/restapi/ingest) | Replaceable structured HTTPS sink |
| [Axiom edge deployments](https://axiom.co/docs/reference/edge-deployments) | Selected US East 1 ingest, storage, and query boundary |
| [Axiom pricing](https://axiom.co/pricing) | Current Personal retention and explicit governance limitations to recheck before rollout |
| [Better Stack HTTP ingest](https://betterstack.com/docs/logs/ingesting-data/http/logs/) | Direct structured HTTPS replacement option |
| [Grafana Cloud OTLP](https://grafana.com/docs/grafana-cloud/send-data/otlp/send-data-otlp/) | Direct OTLP replacement option |

## Open questions

These do not block the decision, but each must be fixed before implementation of
its delivery gate:

- What exact encoded event-byte limit, Device ring capacity, API forwarding
  queue capacity, bounded recent-identity-set capacity and eviction policy,
  timeout, and forwarding retry budget fit measured Device/API memory and
  incident volume?
- Which closed fields and stable error enums belong to each of the seven event
  payloads?
- What capability marker distinguishes event-capable firmware during mixed
  rollout?
- What exact packet-identifier allocation and exhaustion strategy satisfies the
  one-in-flight telemetry client without ambiguity?
- Does Axiom Personal still provide the selected US East 1 ingest, 30-day
  retention, and capacity at implementation time, or should the same
  vendor-neutral HTTPS seam target a paid or replacement sink?
