# Paperbridge Agent Guide

## Project

Paperbridge is a protocol and device platform that lets people, applications,
and AI agents send secure, scheduled physical output to connected printers. Its
product promise is: **Send something real to someone far away.** The recipient’s
experience is a **physical inbox** that works without opening an app.

The currently proven local path is:

```text
Mac host CLI -- USB-C NDJSON RPC ------------------> Waveshare ESP32-S3-ETH
Mac REST/API -- home Wi-Fi MQTT jobs/probes ------>          |
ESP32-S3-ETH -- direct W5500 / TCP ESC/POS -----------------> Rongta RP326
```

The Mac does not need a direct network route to the printer. A successful socket
write is `delivered_to_printer`; it is not proof that paper emerged.

The complete USB and private REST/MQTT v1 print paths, controlled power-cycle
acceptance, isolated Ethernet and device recovery, observable
cover-open/paper-out behavior, and a no-output Wi-Fi/MQTT tracer have been
demonstrated on the purchased hardware. Treat these as bring-up evidence, not a
production-reliability claim: the 72-hour soak remains a separate gate. Never
infer hardware success from host tests or stale documentation.

Not implemented: MCP, web app, public API/authentication, MQTT/TLS, durable job
delivery, OTA, production provisioning, image printing, or an ESP-IDF firmware
port. Do not build these without an approved issue. `apps/api` contains the
private single-device REST/MQTT v1 service and no MCP; `firmware/esp-idf/`
remains a future placeholder.

## Sources of truth

Before changing behavior, read the relevant code and its callers plus:

1. `docs/product.md` — product definition, promise, and target experience.
2. `CONTEXT.md` — canonical domain language.
3. `README.md` — setup, current milestone, and end-to-end bring-up.
4. `docs/architecture.md` — runtime path and future contract boundary.
5. `docs/local-bringup.md` — required hardware-validation order.
6. `docs/hardware.md` — documented facts versus purchased-unit observations.
7. `docs/protocol.md` and `docs/usb-serial-rpc.md` — job and RPC semantics.
8. `docs/testing.md` — host, simulator, and physical test boundaries.
9. `docs/adr/` — accepted decisions and migration gates.
10. `docs/research/source-register.md` — external documentation facts, not
    physical verification.

Classify claims precisely:

- **Documented:** stated by a primary source.
- **Implemented:** present in code.
- **Host-tested:** exercised under CPython, often with fakes.
- **Simulator-tested:** exercised across a real TCP socket without the printer.
- **Physically verified:** observed on the purchased board/printer and recorded
  with the date and exact result.

When documents disagree with code or a newer physical observation, verify the
current behavior and update the affected document. Do not silently preserve a
stale claim.

## Current architecture

- `tools/device-cli/paperbridge_cli/` — host port discovery and serial RPC client.
- `firmware/micropython/main.py` — device entry point.
- `firmware/micropython/src/app.py` — composition root.
- `serial_rpc.py` — bounded NDJSON parsing, response correlation, and replay by
  transport `request_id`.
- `rpc_commands.py` — application command routing and hardware-order guards.
- `ethernet.py` — the single MicroPython/W5500 version and pin seam.
- `wifi.py` — station-mode control-plane connection and locked status snapshot.
- `mqtt_adapter.py` — bounded MQTT probe and semantic-job ingress over Wi-Fi.
- `job_service.py` and `job_ledger.py` — shared semantic submission and bounded
  one-boot MQTT terminal-result replay.
- `escpos.py` — semantic/test content to ESC/POS bytes.
- `print_coordinator.py` — render-then-deliver orchestration.
- `printer_transport.py` — one TCP connection per payload with deterministic
  close and honest delivery results.
- `packages/protocol/` — authoritative schemas, fixtures, and TypeScript
  validators/topic contracts.
- `apps/api/` — portable private REST/MQTT v1 service plus no-output probe; no MCP.
- `tools/mosquitto/` — authenticated local-broker development configuration.
- `tools/provisioning/` — local device-configuration generation.
- `tools/printer-simulator/` — TCP capture and transport-failure testing.
- `tools/firmware/` — flash, verify, and force-copy deployment utilities.

Local USB `job.submit` and private REST/MQTT ingress implement semantic
`print-job.v1` through one shared job service/coordinator. MQTT probe and print
job topics remain distinct. The result ledger is bounded RAM replay for one
boot, not a durable queue. Bring-up commands such as `printer.print_test` are not
print jobs. Queue, health, watchdog, and device-event artifacts must not be
described as live capabilities until they have a real caller and observable
behavior.

Keep these identities distinct:

- `request_id`: serial transport correlation and replay.
- `job_id`: semantic job identity and future job idempotency.
- Device: the ESP32 appliance.
- Host: the Mac running the CLI.
- Printer: the RP326 or simulator TCP endpoint.
- Reachable: TCP connection succeeded.
- Delivered: all bytes were accepted by the printer-facing socket.
- Printed: intentionally unsupported until printer status can prove it.

## Development setup and checks

Use the repository toolchain; do not substitute global Python commands:

```sh
mise trust
mise install
just bootstrap
just lint
just format-check
just test
```

`mise.toml` pins the tools, `uv.lock` and `bun.lock` pin dependencies, and
`justfile` is the repeatable operator interface. Use the `paperbridge` CLI for
parameterized USB diagnostics and jobs rather than adding a `just` wrapper for
every command. MCP is a planned product ingress, not a live operator path.

Development passwords resolve from 1Password through the checked-in project
`fnox.toml`; non-secret machine settings come from ignored `.env`. Recipes that
need secrets invoke `fnox exec`, which keeps values out of command arguments and
the interactive shell. Never print resolved values or commit `.env`,
`fnox.local.toml`, or generated firmware configuration. See
`docs/research/fnox-secrets-workflow.md`.

For non-trivial behavior, add or identify the smallest failing behavioral check,
make it pass, then refactor. Run focused tests during work and all three checks
above before completion. Inspect `git diff` and `git status`; preserve unrelated
working-tree changes.

Firmware under `firmware/micropython/src/` must remain compatible with the
selected MicroPython runtime as well as host-testable CPython. Keep hardware
imports lazy or injectable. Use relative imports inside the `src` package so
MicroPython cannot load duplicate module/class identities. Do not add a host-only
dependency to device code.

## Hardware and deployment safety

Hardware commands are external effects. Do not erase, flash, deploy, reboot,
print, feed, cut, or alter printer networking unless the user explicitly asks.
Before doing so:

1. Resolve and repeat the exact `/dev/cu...` port; never guess among devices.
2. Confirm the purchased board and selected firmware variant match.
3. Verify the downloaded firmware SHA-256 from
   `docs/micropython-bringup.md` immediately before flashing.
4. Generate ignored `firmware/micropython/config.json` through the project Fnox
   workflow when networking is enabled; never commit it, `.env`,
   `fnox.local.toml`, credentials, firmware downloads, or captures accidentally.
5. Power the printer from its 24 V adapter and the board from USB; never cross
   power them.
6. Follow the order: ping/info → Ethernet init/link/address → probe → text →
   feed → explicit cut last.

A probe proves reachability only. A socket write proves delivery only. Physical
paper output is a manual hardware integration/acceptance observation.

Deployment must force-copy individual `.py` files. Do not replace it with a
recursive copy: that previously left stale firmware and copied host
`__pycache__`/bytecode onto the ESP32.

## Agent skills

### Issue tracker

GitHub Issues are the work source of truth. GitHub Projects is the roadmap and
status view across issues. See `docs/agents/issue-tracker.md`.

- Put the problem, scope/non-goals, acceptance criteria, dependencies, and
  verification evidence in the issue.
- Keep one independently reviewable concern or vertical slice per issue.
- Record hardware verification separately from host-test acceptance criteria.
- Use Project fields for status, priority, milestone, and dependency visibility;
  do not duplicate the issue body in Project notes.
- Read the linked issue before implementation and report deviations rather than
  silently expanding scope.
- Reference the issue from branches and pull requests when those are requested.
- Do not create, close, relabel, move, commit, push, or submit work unless the
  user explicitly requests it.

### Triage labels

Use `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, and
`wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Paperbridge is single-context: use root `CONTEXT.md` and system-wide ADRs under
`docs/adr/`. See `docs/agents/domain.md`.

## Design constraints

- Prefer the smallest complete vertical path over scaffolding for future stages.
- Reuse the existing composition root, adapters, schemas, fixtures, and test
  seams before adding abstractions.
- Keep rendering separate from printer delivery.
- Reject raw ESC/POS at public/job trust boundaries.
- Keep cut explicit; never add it to boot or ordinary text/feed paths.
- Preserve stable RPC error codes and bounded input handling.
- Keep printer endpoint, network address, timeouts, and hardware-sensitive values
  configurable; observed addresses are not universal defaults.
- Add an ADR only for a hard-to-reverse, surprising decision involving a real
  trade-off.
- Do not migrate to ESP-IDF unless an ADR 0001 gate is observed.
