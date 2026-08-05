# Paperbridge

Paperbridge is a local-first thermal-printer appliance project. The implemented
bring-up path is:

```text
Mac -- USB-C serial JSON RPC -----------------------> Waveshare ESP32-S3-ETH
Mac/Mosquitto -- home Wi-Fi MQTT probe ------------>          |
ESP32-S3-ETH -- direct W5500 Ethernet / TCP ESC/POS ----------> Rongta RP326
```

The Mac never needs a direct network connection to the printer. A successful
socket write is reported as `delivered_to_printer`; it is **not** proof that
paper emerged. The private single-device REST/MQTT v1 and MCP paths are
implemented, simulator-tested, and physically verified on the purchased
device/printer. MCP uses the same application path. Image preparation is host-/
simulator-tested to 576×576, and `test.png` was physically observed at that
bound through REST/MQTT on 2026-08-05. A smaller PNG feed/cut job was also
observed. JPEG and broader image-quality acceptance remain unverified. No website,
public backend, OTA, or production provisioning is implemented.

## Status

- Repository foundation and host-only tests: implemented.
- USB discovery physically observed at `/dev/cu.usbmodem101`; esptool detected an
  ESP32-S3 revision v0.2, embedded 8 MB PSRAM, 16 MB flash, and USB-Serial/JTAG.
- Official MicroPython 1.28.0 SPIRAM_OCT is flashed and running on the purchased
  ESP32-S3; USB RPC `system.ping` and `system.info` are physically verified.
- The dedicated direct-printer network at
  `192.168.4.50 -> 192.168.4.87:9100` has physically verified W5500 link and
  reachability. ASCII text, feed, and explicit partial-cut bytes `1d 56 01`
  were physically verified before the subnet change.
- Local semantic `print-job.v1` USB submission is implemented, host-/simulator-
  tested, and physically verified on 2026-08-02: `job-hello-001` delivered 28
  bytes and its fixture receipt was observed on the purchased printer.
- Controlled post-deploy power-cycle smoke and operator-confirmed acceptance
  passed on 2026-08-02; evidence IDs are recorded in `docs/hardware.md`.
- Board photos confirm `ESP32-S3-ETH` silkscreen with no explicit PCB revision;
  the RP326 self-test reports firmware `GD207_V1.14`.
- Ethernet hot reconnect, printer-only and ESP32-only recovery, cover-open, and
  paper-out behavior passed on 2026-08-02. A 27-sample no-output soak trial also
  passed; only the full 72-hour soak remains.
- The no-output MQTT 3.1.1 tracer over ESP32 Wi-Fi is implemented, host-tested,
  and physically verified on 2026-08-02. Guarded Wi-Fi/MQTT recovery preserved
  direct printer TCP reachability, and direct W5500 cable recovery preserved
  Wi-Fi/MQTT as `hil-network-recovery-89867cf401c3`.
- `POST /api/jobs` validates and delivers bounded `print-job.v1` through
  authenticated local MQTT to the same firmware coordinator. On 2026-08-02,
  `job-hw-acceptance-20260802T203016Z` returned HTTP 200 with
  `delivered_to_printer` after 34 bytes, and an operator observed the expected
  receipt on the purchased printer.
- Streamable HTTP MCP at `/mcp` exposes one `paperbridge_print` tool through the
  same application service. It is host-/simulator-tested and was physically
  verified on 2026-08-02: job `6e46f155-c3f2-4b11-9c56-46f9261f2abe`
  delivered 42 bytes, and an operator observed the expected receipt.

## Mac setup

Install [mise](https://mise.jdx.dev/) first, then:

```sh
mise trust
mise install
just bootstrap
just lint
just test
```

`mise.toml` pins Python, `uv`, `just`, Node, Bun, Fnox, and the 1Password CLI;
`uv.lock` and `bun.lock` pin their respective packages.

## Development configuration and secrets

Copy the non-secret local settings and replace the example broker address and
serial port for this machine:

```sh
cp .env.example .env
$EDITOR .env
```

The checked-in `fnox.toml` maps Paperbridge development secret names to 1Password
references in the `Agent` vault. Enable 1Password desktop-app CLI integration,
unlock the app, and verify the mappings without printing values:

```sh
op vault list
just secrets-check
```

Fnox injects secrets only into the recipes that need them. `.env`,
`fnox.local.toml`, and generated firmware `config.json` are ignored. An optional
machine-local `OP_SERVICE_ACCOUNT_TOKEN` may live in the OS keychain for
unattended use; it is never injected into Paperbridge child processes. See
[`docs/research/fnox-secrets-workflow.md`](docs/research/fnox-secrets-workflow.md).

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
  'https://micropython.org/resources/firmware/'\
'ESP32_GENERIC_S3-SPIRAM_OCT-20260406-v1.28.0.bin' \
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

Read the RP326 self-test receipt before changing its address. For the current
Wi-Fi/MQTT development path, generate the ignored device configuration from
non-secret `.env` settings and project-scoped Fnox values:

```sh
just configure-device
PORT="$PAPERBRIDGE_PORT" just deploy
```

For an Ethernet-only setup, copy `config.example.json` manually and leave Wi-Fi
and MQTT disabled. Deployment and application RPC are separate: `mpremote`
copies files; the `paperbridge` CLI sends requests. `config show` redacts both
passwords.

## Exercise the local path

```sh
PORT="$PAPERBRIDGE_PORT" just device-ping
PORT="$PAPERBRIDGE_PORT" just device-info

mise exec -- uv run paperbridge --port "$PAPERBRIDGE_PORT" ethernet init
mise exec -- uv run paperbridge --port "$PAPERBRIDGE_PORT" ethernet configure-static
PORT="$PAPERBRIDGE_PORT" just ethernet-status
# If a soft reset leaves ETH_STARTED without link, explicitly cycle the LAN:
mise exec -- uv run paperbridge --port "$PAPERBRIDGE_PORT" ethernet reconnect --confirm

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
PORT=/dev/cu.usbmodem101 just test-hardware-network-recovery
```

Expected: a no-output loop that uses guarded device Wi-Fi disconnect/reconnect
RPCs to verify Wi-Fi/MQTT failure and recovery without losing direct W5500
printer reachability, then interactively verifies W5500 failure and recovery
without losing Wi-Fi/MQTT. Operator answers trigger only the W5500 steps; they
do not count as proof. The recipe uses Fnox for the MQTT password and writes one
`hil-network-recovery-*` evidence file under ignored `captures/hardware/`.

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

## Private REST/MCP/MQTT path

Set up authenticated local Mosquitto from
[`tools/mosquitto/README.md`](tools/mosquitto/README.md), put the Mac's
home-LAN broker address, Wi-Fi SSID, and non-placeholder credentials in ignored
`firmware/micropython/config.json`, enable Wi-Fi and MQTT, and deploy only with
explicit hardware authorization. `mqtt.allow_cut` defaults to false and is
device policy; REST callers cannot override it. Start the private API and submit
a fixture with:

```sh
just api
curl -sS -H 'content-type: application/json' \
  --data-binary @packages/protocol/fixtures/print-job-v1/valid-text-feed.json \
  http://127.0.0.1:3000/api/jobs
```

Source REST jobs are limited to 2,101,248 bytes; prepared MQTT jobs are limited
to 65,536 bytes. A timeout is
reported as `unknown` and does not republish the job. Once the device is
connected, inspect both control-plane layers over USB and run the no-output host
probe:

```sh
paperbridge --port "$PAPERBRIDGE_PORT" wifi status
paperbridge --port "$PAPERBRIDGE_PORT" mqtt status
just mqtt-probe
```

`just mqtt-probe` reads non-secret host, username, and device settings from
`.env`, resolves `PAPERBRIDGE_MQTT_PASSWORD` through Fnox, and reports a
correlated tracer response—not printer delivery or paper output. MCP clients
connect to `http://127.0.0.1:3000/mcp` and call `paperbridge_print` with a v1
receipt `content` object; the service supplies the job envelope and waits for the
same honest result as REST.

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
