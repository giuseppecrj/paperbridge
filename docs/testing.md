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
behavior, the bounded no-output MQTT tracer, the schema-backed TypeScript
protocol package, HTTP body/device validation, MCP discovery/tool calls and
Host/Origin guards, MQTT result correlation, timeout/cancellation without retry,
QoS duplicate suppression, device cut policy, and partial-write result reporting.
The Bun workspace checks all three TypeScript packages with `tsc` and Node's test
runner. When `mosquitto` and `mosquitto_passwd` are installed, integration tests
also run the Node probe and full REST and MCP job paths through real local
Mosquitto; otherwise those broker tests are reported as skipped.

`just printer-simulator` captures TCP bytes and supports delayed accept/read,
small partial reads, close/reset during transfer, payload recording, and SHA-256.
Connection refusal is represented by targeting a stopped server. The
REST/MCP/MQTT integration test starts this real TCP seam, runs the CPython-hosted
firmware MQTT adapter and shared coordinator, submits through REST and an
official MCP SDK client, and verifies both exact captured ESC/POS payloads plus
correlated results.

No automated test claims hardware success. This includes the local REST and MCP
semantic-job simulator captures: `delivered_to_printer` is not a physical paper
observation. On 2026-08-05, an operator separately confirmed both a 128×24 black
PNG raster with feed/cut and `test.png` rendered at the 576×576 maximum. The
first large-photo host wait returned `unknown`; same-ID duplicate suppression
and the operator observation were recorded without relabeling that result as
delivery. After raising the result wait from 5 to 15 seconds, a final unique job
returned HTTP 200 / `delivered_to_printer` after 41,487 bytes in 5.498 seconds.
JPEG output, broader image quality, QR scan/decode readability, and other styling
remain hardware acceptance work. Manual bring-up physically
verified USB RPC, direct Ethernet, printer
reachability, text, feed, and explicit cut on
2026-08-01. Controlled power-cycle acceptance, Ethernet hot reconnect,
printer-only and ESP32-only recovery, cover-open buffering, and paper-out
buffering passed on 2026-08-02. Full no-output dual-interface recovery passed as
`hil-network-recovery-89867cf401c3`: Wi-Fi/MQTT failure and recovery preserved
direct printer TCP reachability, and direct W5500 failure and recovery preserved
Wi-Fi/MQTT. The private REST/MQTT path was physically verified on 2026-08-02:
`job-hw-acceptance-20260802T203016Z` returned HTTP 200 with
`delivered_to_printer` after 34 bytes, and the operator observed the expected
receipt. A later soft reset left W5500 at `ETH_STARTED`; guarded
`ethernet reconnect --confirm` restored `raw_status: 5` and printer reachability
without a cable reseat. On 2026-08-07, the no-output EMQX TLS spike
`emqx-tls-spike-945ac7ad7d78` physically verified CA/SNI, automatic NTP, one
correlated tracer response, safe rejection of a non-retained 65,000-byte invalid
job before rendering, and direct W5500/printer reachability while MQTT/TLS stayed
connected. Heap recovered to 8,184,624 bytes. Wi-Fi-loss reconnect, EMQX QoS
redelivery behavior, valid semantic delivery, paper output, and long-duration
coexistence remain unverified. Evidence IDs and observations are recorded in
`hardware.md`; the 72-hour soak also remains.

Ordinary `just test` must remain hardware-free. It never opens a serial port or
operates the purchased printer. Real-broker and real-socket simulator tests are
host evidence only. `just secrets-check` is a separate local setup check that
resolves project 1Password references without printing their values; it is not a
test-suite prerequisite. The Wi-Fi/MQTT tracer tests send no semantic job or
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

### Dual-interface network recovery (no paper output)

```sh
PORT=/dev/cu.usbmodem101 just test-hardware-network-recovery
```

The interactive harness first records the operator's confirmation that the Mac
and ESP32 are on home Wi-Fi and the printer is directly cabled to W5500. It then
records a stable `hil-network-recovery-*` test ID and runs a successful
correlated MQTT probe with direct printer probes immediately before and after
that exchange. It then sends guarded `wifi.disconnect` and `wifi.reconnect` RPCs;
the device network thread, not the USB handler, performs the station transition.
The harness requires Wi-Fi/MQTT to become observably unavailable while the direct
W5500 printer probe still succeeds, then requires recovery. Next it asks the
operator to unplug the direct W5500 cable, requires link and printer-probe
failure while a new correlated MQTT probe still succeeds, and requires both
interfaces to recover after reconnection. MicroPython 1.28 can overwrite its LAN
event status with `ETH_STARTED` when station Wi-Fi regains an IP, so the recovered
direct path is proved by the TCP probe rather than that stale event value.

Operator confirmation never counts as proof by itself: every transition must be
observed within the bounded timeout, and every successful MQTT check uses a new
correlation ID. Evidence records the non-secret broker, Wi-Fi, W5500, and printer
endpoints, commands, expected failures, and recovery results. A passing physical
run is classified as `physically_verified`; failed and aborted evidence remains
`not_verified`. Fnox supplies the MQTT password to the child process without
writing it to evidence. The flow is interactive and never prints, feeds, cuts,
reboots, erases, or flashes.

Defaults are a 60-second transition timeout and one-second polling interval. A
hardware-specific run may override them without changing the code:

```sh
PORT=/dev/cu.usbmodem101 \
  NETWORK_RECOVERY_TIMEOUT_SECONDS=90 \
  just test-hardware-network-recovery
```

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
