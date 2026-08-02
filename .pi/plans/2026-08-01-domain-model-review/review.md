<!-- markdownlint-disable MD013 -->

# Code Review — Paperbridge Domain Model

**Reviewed:** Integrated Wave 1 working tree and verified hardware results  
**Scope:** Vocabulary, identities, lifecycle, semantic print-job contract, delivery evidence, printer-specific behavior, and future cloud reuse  
**Status:** Reconstructed missing report; Wave 1 contract alignment integrated  
**Verdict:** **V1 CONTRACT ALIGNED; job submission and durable identity remain Wave 3**

## Execution status — 2026-08-01

Resolved in Wave 1:

- JSON Schema, device validation, renderer behavior, examples, and shared fixtures now agree.
- V1 supports plain printable-ASCII text, feed, 48-column rule, and explicit partial cut.
- Unsupported styling, copies, expiry, unknown fields, raw bytes, and control bytes fail instead of being ignored.
- `created_at` remains bounded opaque metadata in v1 rather than a parsed timestamp contract.
- RP326 text width and verified partial-cut bytes are named concrete constants without a profile framework.
- Validation and rendering both require explicit cut authorization.

Operational domain terminology and verified hardware facts are synchronized across README and domain, hardware, printer, protocol, RPC, and testing docs.

Still pending:

- `request_id` replay and durable `job_id` deduplication remain separate Wave 3 concerns.
- No `printer.print_job`, host file command, persistent queue, or job ledger is live.
- Physical acceptance evidence remains separate from automatic `delivered_to_printer` status.

## 1. Current domain map

Paperbridge currently spans four conceptual areas:

1. **Local device control** — a Mac sends operational commands over USB serial RPC.
2. **Printer delivery** — the device renders ESC/POS and writes it to a configured printer endpoint over TCP.
3. **Semantic printing** — a future versioned `PrintJob` describes receipt intent without exposing printer bytes.
4. **Future remote delivery** — cloud ingress eventually delivers the same semantic jobs; it is not implemented.

The physically verified path is:

```text
Mac USB RPC
  → Paperbridge Device (ESP32-S3)
  → W5500 direct Ethernet
  → Printer Endpoint 192.168.1.87:9100
  → Rongta RP326
```

Text printing, line feeding, and the partial cutter sequence `1d 56 01` worked on the purchased printer.

## 2. Recommended ubiquitous language

| Term | Meaning | Current representation |
| --- | --- | --- |
| **Paperbridge Device** | The ESP32 appliance that receives commands and owns printer communication | `device_id`, firmware runtime |
| **RPC Request** | One local transport interaction, correlated by `request_id` | Serial request/response envelope |
| **Device Command** | Operational intent such as ping, initialize Ethernet, probe, or diagnostic print | `command` string in RPC |
| **Print Job** | Durable semantic receipt intent, identified independently of transport | `print-job.v1`, `job_id` |
| **Receipt** | Printable semantic content composed of bounded blocks | `content.kind = receipt` |
| **Block** | One semantic receipt element: text, feed, rule, or verified cut | JSON Schema and renderer |
| **Printer Profile** | Printer-specific capabilities and verified command bytes | Concrete `RP326_*` constants in `escpos.py`; no framework |
| **Printer Endpoint** | Configured TCP host and port | `printer.host`, `printer.port` |
| **Probe** | A successful TCP connect and close | `printer.probe` |
| **Delivery** | All bytes accepted by the printer-facing socket | `delivered_to_printer` |
| **Physical Print Confirmation** | Evidence that paper/feed/cut physically occurred | Human observation today; not a protocol status |
| **Queue** | Pending jobs awaiting execution | In-memory scaffold only |
| **Job Ledger** | Completed job identities used for durable deduplication | Unwired RAM scaffold only |

### Important distinction

`request_id` and `job_id` are not interchangeable:

- `request_id` prevents replay of one serial interaction during the current boot.
- `job_id` must prevent a semantic job from printing twice across retries and eventually across restarts/cloud transports.

## 3. Strengths

- Delivery language is honest: socket completion is not called `printed`.
- Public/future callers cannot supply arbitrary ESC/POS bytes.
- Text is bounded to printable ASCII and rejects control-byte injection.
- Cutter execution is explicit and has now been physically verified.
- Rendering and transport are separate, allowing the same job semantics to survive future transport changes.
- Local RPC and future MQTT are correctly treated as transports, not separate application domains.

## 4. Review findings and disposition

Wave 1 resolved contract drift, unsupported job options, printer-specific constant naming, rule width, and cut authorization. Job identity, lifecycle/persistence, physical confirmation, and production device identity remain intentionally deferred as described below.

### [High] The authoritative Print Job contract is split and already inconsistent

The JSON Schema requires text style fields (`align`, `bold`, `underline`, and size multipliers). Firmware validation only validates text content, and rendering ignores all style fields. A job can therefore be schema-valid while printing with silently different semantics, or firmware-valid while schema-invalid.

**Recommendation:** For v1, narrow the contract to behavior that is actually rendered, or implement every declared style. Prefer narrowing first. Use shared valid/invalid fixtures to prove JSON Schema, firmware validation, and rendering agree.

### [High] Job identity and transport identity need separate deduplication rules

Serial response replay caches `request_id` for one boot. `JobLedger` is not wired and is not persistent. Once `printer.print_job` exists, retrying with a new request ID but the same job ID could print twice.

**Recommendation:** Define at-most-once behavior around `job_id` before queue/persistence work. Transport replay remains a separate concern.

### [High] Diagnostic commands are not Print Jobs

`printer.print_test`, `feed_test`, and `cut_test` are commissioning/recovery commands. They should not become the public semantic job protocol or be accepted from future web clients.

**Recommendation:** Keep these commands under a diagnostic command surface. Add one explicit `printer.print_job` path later that validates the semantic envelope.

### [High] Printer-specific behavior lacks a domain object

The verified partial cutter command is still named `DEFAULT_PARTIAL_CUT` and documented as unverified in code. The domain now knows that this behavior belongs to the purchased RP326 profile, not every ESC/POS printer.

**Recommendation:** Introduce the smallest possible `RP326` profile value containing verified capabilities/bytes. Do not add a profile hierarchy or factory.

### [Medium] Job options are declared but not honored

`copies` is validated but not executed. Text formatting options are ignored. `created_at` and `expires_at` are bounded strings on-device but are not parsed or enforced.

**Recommendation:** Either implement each v1 semantic or remove it from v1. Unsupported semantics must fail rather than be silently discarded.

### [Medium] Job lifecycle exists only as ephemeral implementation state

`StatusTracker` models transitions but no live job command returns or records them. Queue and ledger do not own lifecycle state.

**Recommendation:** When job RPC is added, return the final status and job ID. Do not publish intermediate lifecycle as a stable cloud contract until queue persistence exists.

### [Medium] Physical confirmation is acceptance evidence, not device truth

The user physically verified print/feed/cut, but the printer transport cannot query paper/head/cutter status. Calling such work `printed` in the protocol would still be incorrect.

**Recommendation:** HIL acceptance reports may record operator-confirmed physical output separately from device-reported `delivered_to_printer`.

### [Medium] Device identity is configurable but not provisioned

`device_id` is a local config string. No uniqueness, immutability, or credential binding exists yet.

**Recommendation:** Keep it development-only now. Define production identity during provisioning/cloud work, not during local job implementation.

### [Low] “Rule” width is an implicit printer assumption

The renderer emits 48 characters. That matches a common 80 mm text mode but is not named as a profile capability.

**Recommendation:** Move the width alongside the RP326 profile when structured jobs are wired.

## 5. Verified domain facts to record in project docs

- MicroPython 1.28.0 SPIRAM_OCT is installed and running.
- The Paperbridge Device is reachable over USB RPC.
- Direct Ethernet link negotiation works.
- Device address is `192.168.1.50/24`.
- Printer endpoint `192.168.1.87:9100` is reachable.
- Text, feed, and explicit partial cut physically worked.
- Cutter bytes `1d 56 01` are verified on this purchased RP326.
- `delivered_to_printer` remains the correct automatic status.

## 6. Coordination status

### Completed domain/protocol stream

Own only:

- `packages/protocol/schemas/print-job.v1.schema.json`
- print-job examples/fixtures
- `firmware/micropython/src/job_schema.py`
- `firmware/micropython/src/escpos.py`
- corresponding tests

Delivered: one internally consistent v1 semantic contract. RPC, queue, and persistence were not wired.

### Follow-on, not parallel with the contract stream

After the contract is accepted:

1. Add `printer.print_job` RPC and host file command.
2. Physically test one structured receipt.
3. Define persistent queue and `job_id` deduplication.

## 7. Recorded decisions

1. **Recommended:** narrow v1 text blocks to plain ASCII text first; add styling in a later schema version or explicit compatible extension.
2. **Recommended:** diagnostic commands stay separate from semantic jobs.
3. **Recommended:** add one concrete RP326 profile value, not an abstraction framework.
4. **Required:** `request_id` replay and `job_id` deduplication remain separate concepts.
