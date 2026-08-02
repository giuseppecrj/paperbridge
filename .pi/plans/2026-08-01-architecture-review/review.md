<!-- markdownlint-disable MD013 -->

# Code Review — Paperbridge Architecture

**Reviewed:** Integrated Wave 1 and Wave 2 working tree (`cfeec74` plus uncommitted fixes)  
**Evidence:** 135 host tests, Ruff, formatting, wheel build, controlled HIL smoke and acceptance  
**Verdict:** **WAVES 1–2 COMPLETE; reconnect/recovery/soak gates remain**

## Execution status — 2026-08-02

| Wave | Stream | Status |
| --- | --- | --- |
| 1A | Firmware runtime integrity | Integrated, host-verified, uncommitted |
| 1B | Infrastructure safety | Integrated, host-verified, uncommitted |
| 1C | Domain/protocol alignment | Integrated, host-verified, uncommitted |
| 2D | Opt-in HIL harness | Complete; controlled smoke and acceptance passed |
| 2E | Documentation synchronization | Completed for integrated behavior |
| 3 | Structured print-job delivery | Not started; separately approved feature |

Wave 2 deployed the integrated firmware, then completed a clean printer/device power cycle. The first controlled smoke exposed a one-shot link-negotiation race; a bounded retry and regression test were added. The rerun passed as `hil-smoke-4a18d01b6f2b`, followed by operator-confirmed text/feed/cut acceptance `hil-acceptance-16ee54e70f65`. Reconnect, fault-recovery, and soak gates remain outside Wave 2.

Resolved in Wave 1: package-relative imports and direct `RpcError` handling, `ipconfig()` status reads, DNS reporting, unused live RPC wiring, printer transport error tests, flash/erase safety, repository-anchored tooling paths, port validation, application-RPC deploy readiness, generated metadata cleanup, and one aligned `print-job.v1` contract with explicit cut authorization.

## 1. Current architecture

```text
Mac CLI
  → USB serial NDJSON
  → SerialRpcServer
  → CommandRouter
      → W5500LAN
      → PrintCoordinator
          → EscPosRenderer
          → PrinterTransport
              → TCP printer endpoint
```

The runtime remains shallow and appropriately local-first. Cloud, MQTT, web, Wi-Fi, OTA, and ESP-IDF are still deferred.

## 2. Facts changed since the previous review

The prior report was stale in several places. Current verified state:

- Official MicroPython 1.28.0 SPIRAM_OCT is flashed and running.
- USB RPC `system.ping` and `system.info` work on the actual device.
- `network.PHY_W5500` and `network.LAN` are available.
- Static configuration now uses the physically verified `ipconfig()` API.
- `ethernet.configure_static` succeeds repeatedly without `0x5001`.
- Direct Ethernet link reaches `link_up: True`.
- Printer `192.168.1.87:9100` is reachable.
- Text, feed, and partial cutter behavior physically work.
- Deployment now performs a MicroPython preflight and force-copies only `src/*.py`.
- Hatchling wheel build succeeds.
- CLI eager access to the cut-only confirmation argument is fixed.

## 3. Strengths to preserve

- One composition root (`build_app`) wires the local path.
- Rendering is separate from printer transport.
- Printer communication is owned by the device, not the Mac.
- RPC lines, text, queues, and output bytes are bounded.
- Stable errors cross the serial protocol.
- `delivered_to_printer` correctly avoids false physical-print claims.
- Hardware-specific construction is localized in `ethernet.py`.
- Host CLI, deployment tooling, and application RPC remain separate concepts.
- No cloud infrastructure is needed for local printing.

## 4. Review findings and disposition

Wave 1 implementation resolved the import, contract-drift, unused-wiring, Ethernet-status, deploy-readiness, command-surface, transport-test, and documentation findings below. HIL remains Wave 2 work; lifecycle/persistence remains Wave 3 work.

### [High] Firmware import style is mixed

`app.py` and `print_coordinator.py` use `from src...`; most firmware modules use relative imports. This risks duplicate module/class identities on MicroPython, especially for `RpcError`.

**Smallest fix:** Use relative imports everywhere inside `src/`; keep only `main.py` as the absolute package entry. Restore direct `except RpcError` followed by `except Exception` after module identity is normalized.

### [High] Print-job contracts diverge

JSON Schema, firmware validation, and rendering disagree about required text style fields and supported behavior. This must be reconciled before adding `printer.print_job`.

**Smallest fix:** Narrow v1 to implemented semantics and make shared fixtures pass through schema validation, firmware validation, and rendering.

### [High] No repeatable HIL acceptance harness exists

The live commands found real failures that host tests could not: erased flash, stale deploy copies, CLI command mapping, deprecated network configuration, and USB reset timing. Current evidence is manual/session-bound.

**Smallest fix:** Add opt-in hardware smoke and operator-confirmed acceptance commands after foundational fixes. Never run cutter/printing in ordinary `just test` or generic CI.

### [High] Operational documentation contradicts verified reality

README and hardware docs still mention vendor firmware and pending printer/cutter/link facts.

**Smallest fix:** Update observed facts now; retain only real unknowns such as silkscreen revision, printer firmware version, and soak duration.

### [Medium] Future modules are half-wired

`JobQueue` is constructed but only status is reachable; `JobLedger`, `health`, and `watchdog` have no live owners; `PrintCoordinator.execute` has no command caller.

**Recommendation:** Do not expand them opportunistically. Keep contract scaffolding for the imminent milestone, but remove live `queue.status`/composition wiring until a real job lifecycle is specified, or clearly mark it non-production.

### [Medium] Configuration reload is partial

The shared config dict updates transport/network readers, but constructed state such as queue capacity does not change. The CLI does not expose reload.

**Smallest fix:** For bring-up, document that deploy/reboot is the supported structural reload and remove the unused RPC reload command, rather than building a config service.

### [Medium] Ethernet status still reads the deprecated API

Static writes use `ipconfig()`, but status still queries `ifconfig()`. Reads currently work physically, yet the adapter now mixes API families.

**Smallest fix:** Query address and gateway with `ipconfig()` and preserve the existing RPC result shape. Extend the fake LAN test.

### [Medium] Deployment reset readiness is not coordinated

An immediate command after deploy once hit `SERIAL_READ_FAILED` while USB re-enumerated. `SerialClient` retries opening, but not a disconnect after opening the stale device node.

**Smallest fix:** Make deploy wait for the application RPC to become ready, or make one request safely reconnect/retry with the same `request_id`. Prefer one bounded readiness check in deploy.

### [Medium] Device and CLI command surfaces differ

The device exposes memory, reset cause, config reload, and fixture commands that the CLI does not consistently expose. `printer.send_fixture` duplicates `print_test`.

**Smallest fix:** Delete aliases/unused commands; add only bring-up commands explicitly required by docs.

### [Low] Job status vocabulary is internal-only

`StatusTracker` transitions are not returned or persisted. That is acceptable until semantic jobs exist, but docs should not imply a stable externally observable lifecycle yet.

### [Low] Printer transport error mapping needs a focused unit test

`socket_module` is already injectable. Add one table-driven test for timeout, refusal, reset, and partial writes.

## 5. Resolved findings

- **Resolved:** W5500 constructor/static API uncertainty for MicroPython 1.28.
- **Resolved:** `configure-static` repeat failure (`0x5001`).
- **Resolved:** stale deploy source caused by mpremote “up to date” behavior; files are force-copied.
- **Resolved:** recursive deploy copied host bytecode; deploy now selects `src/*.py` only.
- **Resolved:** deploy gives a clear error when MicroPython is absent.
- **Resolved:** CLI `_rpc` read cut-only arguments for all commands.
- **Resolved:** hatchling wheel layout; current wheel builds successfully.

## 6. Safe architecture debt to defer

- MQTT/TLS/cloud transport
- Wi-Fi coexistence
- ESP-IDF migration
- OTA and production credentials
- Persistent queue implementation until job semantics are accepted
- Image and QR rendering
- Printer status querying
- Web/API application code

## 7. Coordination plan and conflict boundaries

### Wave 1 — parallel-safe

**A. Firmware runtime integrity**  
Owns: `src/app.py`, `print_coordinator.py`, `serial_rpc.py`, `ethernet.py`, `rpc_commands.py`, runtime tests.  
Goals: normalize imports/error identity, finish `ipconfig` status, simplify unused command/runtime wiring, define deploy/reboot readiness expectation.

**B. Infrastructure safety**  
Owns: `justfile`, `tools/firmware`, `tools/provisioning`, `.gitignore`, packaging/tooling config.  
Goals: flash/erase safety, path anchoring, port unification, generated metadata cleanup, deploy readiness.

**C. Domain/protocol alignment**  
Owns: print-job schema/examples, `job_schema.py`, `escpos.py`, protocol tests.  
Goals: one v1 contract matching rendered behavior; concrete RP326 profile facts. Do not wire RPC.

These streams should not edit each other’s file sets.

### Wave 2 — after Wave 1 integration

**D. HIL test harness — completed**  
`test-hardware-smoke` performs ping/info/init/static twice/bounded link wait/probe without paper output. `test-hardware-acceptance` adds interactive text/feed/exact cutter authorization and records local evidence. Neither runs from ordinary host tests. Controlled smoke and acceptance passed on 2026-08-02.

**E. Documentation synchronization — completed**  
README and hardware, printer, network, protocol, RPC, runtime, testing, and source-register docs now distinguish implemented, host-tested, physically verified, and still-pending gates.

### Wave 3 — separately approved feature

Wire semantic print-job RPC/CLI, physically test one job, then design persistence/deduplication.

## 8. Top next actions

1. Review and commit the uncommitted Waves 1–2 baseline only when explicitly approved.
2. Record board silkscreen and printer firmware details.
3. Run reconnect, fault-recovery, and 72-hour soak gates before production claims.
4. Start semantic print-job delivery only when explicitly approved.
