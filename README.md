# Paperbridge

Paperbridge is a local-first thermal-printer appliance project. The implemented
bring-up path is:

```text
Mac -- USB-C serial JSON RPC --> Waveshare ESP32-S3-ETH
    -- W5500 Ethernet / TCP ESC/POS --> Rongta RP326
```

The Mac never needs a direct network connection to the printer. A successful
socket write is reported as `delivered_to_printer`; it is **not** proof that
paper emerged. No website, backend, MQTT, Wi-Fi, image printing, OTA, or
production provisioning is implemented.

## Status

- Repository foundation and host-only tests: implemented.
- USB discovery physically observed at `/dev/cu.usbmodem101`; esptool detected an
  ESP32-S3 revision v0.2, embedded 8 MB PSRAM, 16 MB flash, and USB-Serial/JTAG.
- Official MicroPython 1.28.0 SPIRAM_OCT is flashed and running on the purchased
  ESP32-S3; USB RPC `system.ping` and `system.info` are physically verified.
- W5500 initialization, repeated static configuration at `192.168.1.50/24`,
  direct-link negotiation, and printer probe are physically verified.
- Printer endpoint `192.168.1.87:9100`, ASCII text, feed, and explicit partial
  cut bytes `1d 56 01` are physically verified on the purchased RP326.
- Local semantic `print-job.v1` USB submission is implemented and
  host-/simulator-tested; it has not been physically verified as structured-job
  output.
- Controlled post-deploy power-cycle smoke and operator-confirmed acceptance
  passed on 2026-08-02; evidence IDs are recorded in `docs/hardware.md`.
- Board photos confirm `ESP32-S3-ETH` silkscreen with no explicit PCB revision;
  the RP326 self-test reports firmware `GD207_V1.14`.
- Ethernet hot reconnect, printer-only and ESP32-only recovery, cover-open, and
  paper-out behavior passed on 2026-08-02. A 27-sample no-output soak trial also
  passed; only the full 72-hour soak remains.

## Mac setup

Install [mise](https://mise.jdx.dev/) first, then:

```sh
mise trust
mise install
just bootstrap
just lint
just test
```

`mise.toml` pins Python, `uv`, and `just`; `uv.lock` pins Python packages.

## Discover the ESP32 serial port

Connect a known USB-C **data** cable, then run:

```sh
just ports
# or
mise exec -- uv run paperbridge ports list
```

Likely macOS names include `/dev/cu.usbmodem*`, `/dev/cu.usbserial*`, and
`/dev/cu.wchusbserial*`. If more than one candidate exists, the CLI refuses to
choose. Select one explicitly:

```sh
export PAPERBRIDGE_PORT=/dev/cu.usbmodem101
# Every just recipe also accepts: PORT=/dev/cu.usbmodem101
```

## Select and flash MicroPython

First inspect the purchased board silkscreen and exact chip/board revision. The
official Waveshare SKU 28972 documentation says ESP32-S3R8, 16 MB flash, and 8
MB octal PSRAM. The purchased chip and memory matched those runtime requirements;
the selected and verified image is official MicroPython 1.28.0:

```sh
mkdir -p firmware/downloads
curl -fL \
  https://micropython.org/resources/firmware/ESP32_GENERIC_S3-SPIRAM_OCT-20260406-v1.28.0.bin \
  -o firmware/downloads/ESP32_GENERIC_S3-SPIRAM_OCT-20260406-v1.28.0.bin
printf '%s  %s\n' \
  67c19ae123d84152019b57526ed5291dd0a2b4edd87655c5f76b46c9a62ff5dd \
  firmware/downloads/ESP32_GENERIC_S3-SPIRAM_OCT-20260406-v1.28.0.bin \
  | shasum -a 256 -c -

PORT="$PAPERBRIDGE_PORT" CONFIRM=erase just erase-device
PORT="$PAPERBRIDGE_PORT" \
FIRMWARE=firmware/downloads/ESP32_GENERIC_S3-SPIRAM_OCT-20260406-v1.28.0.bin \
  just flash-micropython
PORT="$PAPERBRIDGE_PORT" just repl
PORT="$PAPERBRIDGE_PORT" just verify-board
```

Do not flash this variant solely from the marketing memory configuration. See
[`docs/micropython-bringup.md`](docs/micropython-bringup.md).

## Configure and deploy firmware

Read the RP326 self-test receipt before changing its address. Create an ignored
local configuration and replace the example endpoint with observed values:

```sh
cp firmware/micropython/config.example.json firmware/micropython/config.json
$EDITOR firmware/micropython/config.json
PORT="$PAPERBRIDGE_PORT" just deploy
```

Deployment and application RPC are separate: `mpremote` copies files; the
`paperbridge` CLI sends requests.

## Exercise the local path

```sh
PORT="$PAPERBRIDGE_PORT" just device-ping
PORT="$PAPERBRIDGE_PORT" just device-info

mise exec -- uv run paperbridge --port "$PAPERBRIDGE_PORT" ethernet init
mise exec -- uv run paperbridge --port "$PAPERBRIDGE_PORT" ethernet configure-static
PORT="$PAPERBRIDGE_PORT" just ethernet-status

PORT="$PAPERBRIDGE_PORT" just printer-probe
PORT="$PAPERBRIDGE_PORT" TEXT='Hello from my Mac' just print-test
mise exec -- uv run paperbridge --port "$PAPERBRIDGE_PORT" printer feed-test
PORT="$PAPERBRIDGE_PORT" just cut-test  # explicit confirmation; run last
mise exec -- uv run paperbridge --port "$PAPERBRIDGE_PORT" \
  job submit packages/protocol/fixtures/print-job-v1/valid-text-feed.json
```

Do not run the cut test until plain text and feed tests succeed. The included
partial-cut sequence is verified only on the purchased RP326 and still requires
explicit confirmation every time. `job submit` returns `delivered_to_printer`,
not proof that paper emerged. A semantic cut job additionally requires
`--allow-cut`.

### Opt-in hardware smoke and acceptance

Ordinary `just test` is host-only and never operates hardware. With a selected
port:

```sh
PORT=/dev/cu.usbmodem101 just test-hardware-smoke
```

Expected: ping, info, Ethernet init, static config twice, link up, printer probe.
No print/feed/cut.

```sh
PORT=/dev/cu.usbmodem101 just test-hardware-acceptance
```

Expected: runs smoke, prints uniquely identified text, asks you to confirm paper
output, feeds, asks again, requires typing exact token `CUT` before cut, then
asks for cut confirmation. Evidence JSON is written under ignored
`captures/hardware/`.

For machine-readable output:

```sh
mise exec -- uv run paperbridge --json --port "$PAPERBRIDGE_PORT" device info
```

## Simulator

```sh
just printer-simulator
# captures payloads under captures/ and reports SHA-256
```

The ESP32 can target the simulator only when it can route to the Mac on a shared
test network. The direct ESP32-to-printer mode does not depend on the simulator.

## Remaining physical check

Run the 72-hour no-output soak and review its reset, reachability, and heap
summary before treating MicroPython as production-capable. See `docs/testing.md`.

## ESP-IDF migration gates

Migrate if W5500 or USB is unstable; Wi-Fi and Ethernet cannot coexist reliably;
routing is unreliable; MQTT/TLS exhausts or fragments memory; a 72-hour soak
fails; OTA or secure credentials need ESP-IDF facilities; normal network faults
cause watchdog resets; or printer status needs lower-level control. See
[`docs/adr/0001-use-micropython-first.md`](docs/adr/0001-use-micropython-first.md).

## Documentation

Start with [`docs/local-bringup.md`](docs/local-bringup.md),
[`docs/hardware.md`](docs/hardware.md), and
[`docs/usb-serial-rpc.md`](docs/usb-serial-rpc.md).
