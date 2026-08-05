<!-- markdownlint-disable MD013 -->

# Hardware

## Controller

- Purchased product: Waveshare ESP32-S3-ETH, board-only SKU (no PoE module).
- Official product page SKU: 28972.
- Officially documented controller: ESP32-S3R8, dual-core LX7 up to 240 MHz.
- Officially documented memory: 16 MB W25Q128 flash and 8 MB octal PSRAM.
- Officially documented Ethernet: W5500 10/100 through SPI.
- Officially documented USB-C: power, firmware download, and debugging.
- **Purchased-board silkscreen:** `Waveshare ESP32-S3-ETH`, confirmed from
  top/bottom photos on 2026-08-02.
- **Purchased-board revision:** no explicit PCB revision marking is visible; the
  red `C3` sticker is not treated as revision evidence.
- **Observed over USB on 2026-08-01:** ESP32-S3 QFN56 revision v0.2, embedded
  8 MB PSRAM, 16 MB flash, and USB-Serial/JTAG mode (`esptool flash-id`).
- **Current firmware:** official MicroPython 1.28.0
  `ESP32_GENERIC_S3-SPIRAM_OCT`, physically flashed and verified on 2026-08-01.
- **Observed application path:** USB RPC ping/info, W5500 initialization, static
  IPv4, direct link, and printer probe all succeeded on 2026-08-01. On
  2026-08-02 station-mode Wi-Fi authenticated to local Mosquitto, returned a
  correlated MQTT probe status, and preserved direct-W5500 printer reachability.
  Full no-output Wi-Fi/W5500 disconnect and recovery passed as
  `hil-network-recovery-89867cf401c3`.

Official W5500 signal map for this product page:

| Signal | GPIO |
| --- | ---: |
| SPI controller input | 12 |
| SPI controller output | 11 |
| clock | 13 |
| chip select | 14 |
| reset | 9 |
| interrupt | 10 |
| PHY address | normally 0 |

The mapping is documented by Waveshare and was exercised successfully by the
purchased board's W5500 link. Photos confirm the product silkscreen and layout,
but expose no explicit PCB revision for a revision-specific schematic match.
Firmware keeps version-sensitive `network.LAN` construction in
`firmware/micropython/src/ethernet.py`. The purchased setup exposes one green
Ethernet indicator.

## Printer

Purchased Rongta RP326 interfaces: Ethernet, USB, and RS-232. Marketing values
not independently measured here include 80 mm paper, about 72 mm/576-dot
printable width, 203 dpi, and up to 250 mm/s. ESC/POS text/feed and cutter
behavior were physically exercised. The printer uses its own 24 V adapter;
neither device powers the other.

The purchased printer accepted TCP connections at `192.168.1.87:9100` on
2026-08-01. On 2026-08-02 its dedicated direct-link address was changed to
`192.168.4.87:9100`; the ESP32 W5500 at `192.168.4.50/24` reached it over the
direct cable without printing. These are observed local endpoints, not
universal defaults. The 2026-08-02 self-test reported firmware `GD207_V1.14`
dated `26-01-28`, EPSON
ESC/POS mode, DHCP disabled, 10/100 Ethernet, 48 Font-A or 64 Font-B/C columns,
light density, and default code page CP437.

ASCII text, line feed, and explicit partial cut were physically observed. The
working cutter bytes are `1d 56 01`; automatic or unconfirmed cutting remains
forbidden. An Epson-compatible QR rendered at `module_size: 5` and the following
partial cut were physically observed on this purchased RP326 on 2026-08-02.
Alignment, emphasis, underline, other QR sizes, and QR scan/decode readability
have not been separately verified.

## Image physical-spike candidates

Host/simulator tests bound a prepared raster to 128×24 pixels (384 bytes), with
one-bit `GS v 0` output. On 2026-08-05, a REST/MQTT job rendered a visible
128×24 black PNG raster, fed three lines, and made an operator-confirmed partial
cut on the purchased RP326. The final image spike must still record general PNG/
JPEG appearance, legibility, paper advance, and heap behavior at this bound.

## Purchased-unit observations

| Fact | Observed value | Date |
| --- | --- | --- |
| Board revision/silkscreen | `ESP32-S3-ETH`; no explicit PCB revision visible | 2026-08-02 |
| Detected chip | ESP32-S3 QFN56 revision v0.2 | 2026-08-01 |
| Detected flash | 16 MB | 2026-08-01 |
| Detected PSRAM | embedded 8 MB | 2026-08-01 |
| USB mode | USB-Serial/JTAG; `/dev/cu.usbmodem101` on test Mac | 2026-08-01 |
| MicroPython runtime | 1.28.0 SPIRAM_OCT | 2026-08-01 |
| USB application RPC | `system.ping` and `system.info` succeeded | 2026-08-01 |
| Initial device static IPv4 | `192.168.1.50/24`, repeated configuration succeeded | 2026-08-01 |
| Initial printer IP/port | `192.168.1.87:9100` | 2026-08-01 |
| Dedicated direct printer subnet | W5500 `192.168.4.50/24` reached printer `192.168.4.87:9100` | 2026-08-02 |
| Wi-Fi + MQTT tracer | Wi-Fi obtained `192.168.1.110`; lock-protected firmware returned correlated probe `1e087965-b790-4cd9-a4ef-950c1ab86183`; USB RPC and direct printer probe still succeeded | 2026-08-02 |
| Dual-interface recovery | Guarded Wi-Fi/MQTT disconnect/reconnect preserved direct printer TCP reachability; direct W5500 disconnect/reconnect preserved Wi-Fi/MQTT; `hil-network-recovery-89867cf401c3` | 2026-08-02 |
| Guarded W5500 reconnect | After a soft reset remained at `ETH_STARTED`, `ethernet reconnect --confirm` cycled the LAN singleton; link returned as `raw_status: 5` and printer probe succeeded without a cable reseat | 2026-08-02 |
| Printer firmware | `GD207_V1.14`, self-test date `26-01-28` | 2026-08-02 |
| Direct-link negotiation | `link_up: true` | 2026-08-01 |
| Printer text/feed | physically observed | 2026-08-01 |
| Semantic v1 USB job | `job-hello-001` delivered 28 bytes; fixture receipt physically observed | 2026-08-02 |
| REST/MQTT semantic v1 job | `job-hw-acceptance-20260802T203016Z` returned HTTP 200 and delivered 34 bytes; expected receipt physically observed | 2026-08-02 |
| Verified cutter command | partial cut `1d 56 01` | 2026-08-01 |
| QR size and cut | USB job `job-qr-size5-cut-manual-20260802` delivered 93 bytes; operator confirmed its `module_size: 5` QR and following partial cut | 2026-08-02 |
| PNG raster, feed, and cut | REST/MQTT `job-visible-image-cut-ad8d4247-544b-4129-8519-d9aaeca41733` delivered 400 bytes; visible 128×24 black raster, three feed lines, and partial cut operator-confirmed | 2026-08-05 |
| Controlled HIL smoke | passed; `hil-smoke-4a18d01b6f2b` | 2026-08-02 |
| Controlled HIL acceptance | text/feed/cut observed; `hil-acceptance-16ee54e70f65` | 2026-08-02 |
| Ethernet cable disconnected | link-down failure recorded; `hil-smoke-507b76745250` | 2026-08-02 |
| Ethernet hot reconnect | link/probe recovered; `hil-smoke-882e486ddcc8` | 2026-08-02 |
| Printer-only power loss | link-down failure recorded; `hil-smoke-7b5e2b805f40` | 2026-08-02 |
| Printer-only recovery | link/probe recovered; `hil-smoke-9b72f507ee59` | 2026-08-02 |
| ESP32-only recovery | RPC/link/probe recovered; `hil-smoke-23d9e6335df7` | 2026-08-02 |
| Cover open | bytes delivered; no output until cover closed, then buffered text printed | 2026-08-02 |
| Paper out | bytes delivered; no output until paper reloaded, then buffered text printed | 2026-08-02 |
| Post-inspection restore | RPC/link/probe recovered; `hil-smoke-17213f1fe6ac` | 2026-08-02 |
| Short soak trial | 27 samples; no reset/link/probe failure; bounded heap GC; `hil-soak-a4a7bba65d04` | 2026-08-02 |
