# ADR 0006: Use a Mac mini and local MQTT for the Phase 2 MVP

- Status: Accepted
- Date: 2026-08-01
- Corrected: 2026-08-02 (Wi-Fi control plane; dedicated printer Ethernet)

## Context

The local USB-to-ESP32-to-printer path proves hardware bring-up, but it does not
yet prove Paperbridge's product loop: an AI agent submits a semantic job through
an application boundary, a remote device receives it, and physical output
emerges. Building public cloud infrastructure, accounts, and a website before
that loop is credible would test infrastructure before the product hypothesis.

Paperbridge is the canonical product name. Its future public website will use
`paperbridge.tech`, but the website is not part of this phase.

## Decision

Build Phase 2 as a private, single-device networked MVP hosted on the existing
Mac mini.

The phases are:

1. Hardware bring-up and physical smoke/acceptance testing.
2. Local networked MVP on the Mac mini.
3. Production API and managed MQTT infrastructure.
4. The creative website experience at `paperbridge.tech`.

### Application boundary

One Node.js service written in TypeScript exposes Streamable HTTP MCP at `/mcp`
and REST job submission at `/api/jobs`. Both transports call the same
application-level job submission behavior; neither connects directly to the
ESP32.

Bun manages JavaScript/TypeScript workspaces, dependencies, and scripts only.
Application and contract code must not depend on Bun-specific runtime APIs.
Existing Python bring-up tools remain Python, and device firmware remains
MicroPython. Rewriting proven Python tooling is not part of Phase 2.

The AI agent running on the Mac mini connects through `localhost`. Tailscale
Serve may expose the same service privately to other tailnet clients. There is
no public HTTP endpoint in Phase 2.

### Broker and network

Run Mosquitto as a separate service on the Mac mini. Paperbridge depends on
standard MQTT 3.1.1 behavior, not Mosquitto- or EMQX-specific APIs, plugins,
rules, registries, or job systems. Use QoS 1 and the versioned per-device topic
shape established in `docs/architecture.md`.

The Mac mini and ESP32 join the home LAN over Wi-Fi. The ESP32 uses Wi-Fi only
for its outbound MQTT control plane. Its W5500 interface remains directly cabled
to the printer and uses a separate private IPv4 subnet with no gateway or DNS.
This keeps the physical inbox install as one device attached to one printer;
the printer itself does not join Wi-Fi or the home router.

Wi-Fi and W5500 must coexist reliably on the purchased ESP32. Failure to keep
MQTT responsive while preserving direct printer reachability is an ESP-IDF
migration signal under ADR 0001.

The broker listens only on the required home-LAN Wi-Fi address, rejects
anonymous connections, and uses development username/password credentials
stored outside the repository. Local MQTT/TLS and production device
provisioning are deferred. Tailscale protects MCP/API access; it does not expose
the MQTT broker to the public internet.

Phase 2 supports exactly one configured device and printer. Topics and jobs keep
their `device_id`, but callers cannot select arbitrary devices. There is no
device registry, pairing flow, account ownership, or multi-device routing.

### Job and rendering boundary

Preserve `print-job.v1` unchanged. Define `print-job.v2` for expressive 80 mm
monochrome receipts composed from controlled blocks:

- styled and aligned text;
- rules and spacing/feed;
- QR codes;
- bounded raster images or logos; and
- explicit cut.

Phase 2 does not promise arbitrary PDF, HTML, color, or page-sized document
printing. Raw ESC/POS remains unavailable at MCP, REST, and MQTT trust
boundaries.

Jobs are self-contained. The API accepts bounded embedded PNG or JPEG input and
performs expensive image decoding, resizing, and monochrome dithering. The
device-facing job carries only bounded, prepared raster content. Firmware
validates the controlled blocks and performs final ESC/POS rendering and printer
delivery. Exact source limits, prepared raster limits, and encoding are set by a
schema-design task plus a physical memory/printing spike rather than by this ADR.

### Delivery behavior

Jobs are non-retained and online-only. The system has no durable queue or replay
after a device reboot. Because MQTT QoS 1 may redeliver, firmware keeps a bounded
in-memory set of recently handled `job_id` values for duplicate suppression
during the current boot.

The MCP print operation waits for a correlated device result up to a bounded
timeout. Success ends at `delivered_to_printer`, meaning all bytes were accepted
by the printer-facing socket. It never reports `printed`. A timeout returns an
unknown result and does not automatically resubmit the job.

Phase 2 is accepted when an MCP client on the Mac mini submits a rich semantic
job through the application service, the job crosses local MQTT, the ESP32
delivers it to the printer, the correlated result returns to MCP, and an operator
physically observes the expected paper and explicit cut.

## Migration boundary

Phase 3 preserves the MCP tools, REST contract, semantic job schemas, topic
shape, `job_id` correlation, device behavior, and delivery vocabulary. It
replaces local infrastructure with a public authenticated API, a managed MQTT
broker, MQTT/TLS, per-device credentials, durable job state, and production
observability.

Broker choice remains replaceable. Provider-specific publishing APIs, webhooks,
rules, authentication, or provisioning must stay behind adapters. Before the
full Phase 3 migration, a focused spike must point the device Wi-Fi interface at
a candidate managed broker and physically verify MQTT/TLS, memory behavior, job
receipt, direct-W5500 printing, and result publication.

## Consequences

The MVP tests the product experience with little infrastructure and reuses the
existing semantic, rendering, and printer-delivery boundaries. It does not prove
public availability, MQTT/TLS, offline delivery, reboot-safe deduplication,
durability, multi-device operation, production security, or the website.

The later move to a serverless API will not be a process-level lift-and-shift:
the Mac mini can keep a persistent MQTT subscription, while a serverless design
may require managed-broker publishing and webhook adapters. Keeping those
mechanisms outside the application contracts limits the migration to
infrastructure adapters rather than a product rewrite.
