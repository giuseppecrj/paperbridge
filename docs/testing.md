# Testing

Host-only verification:

```sh
just lint
just format-check
just test
```

Tests cover request parsing/correlation, malformed and oversized JSON, stable
unsupported-command errors, strict cut confirmation, configuration validation,
shared schema/device/renderer fixtures, raw/control rejection, exact ESC/POS
bytes, printer transport failures, Ethernet API behavior, flash/deploy safety,
port ambiguity, bounded FIFO behavior, status transitions, and simulator capture
hashing.

`just printer-simulator` captures TCP bytes and supports delayed accept/read,
small partial reads, close/reset during transfer, payload recording, and SHA-256.
Connection refusal is represented by targeting a stopped server.

No automated test claims hardware success. Manual bring-up physically verified
USB RPC, direct Ethernet, printer reachability, text, feed, and explicit cut on
2026-08-01. Controlled post-deploy power-cycle smoke and operator-confirmed HIL
acceptance passed on 2026-08-02. Those observations and evidence IDs are recorded
in `hardware.md`; reconnect, fault-recovery, and 72-hour soak gates remain.

Ordinary `just test` must remain hardware-free. It never opens a serial port or
operates the printer.

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
