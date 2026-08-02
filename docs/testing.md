# Testing

Host-only verification:

```sh
just lint
just format-check
just test
```

Tests cover request parsing/correlation, malformed and oversized JSON, stable
unsupported-command errors, strict diagnostic and semantic-cut authorization,
configuration validation, shared schema/device/renderer fixtures, raw/control
rejection, exact ESC/POS bytes, semantic `job.submit` request replay with a real
printer-simulator socket capture, printer transport failures, Ethernet API
behavior, flash/deploy safety, port ambiguity, bounded FIFO behavior, status
transitions, simulator capture hashing, station-mode Wi-Fi connection/retry
behavior, and the bounded no-output MQTT tracer. The Bun workspace checks Node
TypeScript with `tsc` and runs its tracer contract
tests. When `mosquitto` and `mosquitto_passwd` are installed, integration tests
also run the Node probe through local Mosquitto and a CPython test client using
the firmware `MqttTracer`; otherwise they are reported as skipped.

`just printer-simulator` captures TCP bytes and supports delayed accept/read,
small partial reads, close/reset during transfer, payload recording, and SHA-256.
Connection refusal is represented by targeting a stopped server.

No automated test claims hardware success. This includes the local semantic-job
simulator capture: `delivered_to_printer` is not a physical paper observation.
Manual bring-up physically verified USB RPC, direct Ethernet, printer
reachability, text, feed, and explicit cut on
2026-08-01. Controlled power-cycle acceptance, Ethernet hot reconnect,
printer-only and ESP32-only recovery, cover-open buffering, and paper-out
buffering passed on 2026-08-02. A no-output Wi-Fi/MQTT tracer round trip also
returned its correlated probe while direct W5500 printer reachability remained
available. Evidence IDs and observations are recorded in `hardware.md`; the
72-hour soak and longer Wi-Fi/W5500 coexistence testing remain.

Ordinary `just test` must remain hardware-free. It never opens a serial port or
operates the printer. The Wi-Fi/MQTT tracer tests send no semantic job or
printer bytes. They do not establish purchased-device Wi-Fi/W5500 coexistence
or paper-output evidence.

## Opt-in hardware-in-the-loop (HIL)

Requires a selected board port and real hardware. Evidence JSON is written under
ignored `captures/hardware/`.

### Smoke (no paper output)

```sh
PORT=/dev/cu.usbmodem101 just test-hardware-smoke
```

Expected: `system.ping` ok, `system.info` returned, Ethernet initialized, static
configuration applied twice, bounded wait for `link_up=true`, and
`printer.probe` reachable. Does not print, feed, cut, reboot, erase, or flash.

### Acceptance (operator-confirmed paper path)

```sh
PORT=/dev/cu.usbmodem101 just test-hardware-acceptance
```

Expected interactive flow: smoke first, uniquely identified text, operator yes
on physical text, feed, operator yes on physical feed, exact token `CUT` before
`printer.cut_test` with `confirm=true`, operator yes on physical cut. Any earlier
no/abort stops before the cutter. No noninteractive cutter bypass. Device
results still use honest `delivered_to_printer` language; physical output is an
operator observation in the evidence file.

### Reliability soak (no paper output)

The default is 72 hours with one sample per minute:

```sh
caffeinate -dimsu -- env PORT=/dev/cu.usbmodem101 just test-hardware-soak
```

For a short harness trial, override the duration without changing production
defaults:

```sh
PORT=/dev/cu.usbmodem101 SOAK_DURATION_SECONDS=300 just test-hardware-soak
```

The soak initializes Ethernet once, then samples ping, device heap/reset state,
link status, and printer reachability. It never prints, feeds, cuts, reboots,
erases, or flashes. Running evidence is checkpointed hourly under ignored
`captures/hardware/`; the final summary records sample count and heap range. Any
failed RPC, link-down result, or unreachable probe fails the gate. A 30-second,
27-sample cache-saturation trial passed as `hil-soak-a4a7bba65d04`; heap showed
bounded garbage-collection recovery rather than monotonic exhaustion.
