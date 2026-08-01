# Hardware

## Controller

- Purchased product: Waveshare ESP32-S3-ETH, board-only SKU (no PoE module).
- Official product page SKU: 28972.
- Officially documented controller: ESP32-S3R8, dual-core LX7 up to 240 MHz.
- Officially documented memory: 16 MB W25Q128 flash and 8 MB octal PSRAM.
- Officially documented Ethernet: W5500 10/100 through SPI.
- Officially documented USB-C: power, firmware download, and debugging.
- **Purchased-board silkscreen/revision:** pending physical inspection.
- **Schematic match on purchased unit:** pending physical inspection.
- **Observed over USB on 2026-08-01:** ESP32-S3 QFN56 revision v0.2, embedded
  8 MB PSRAM, 16 MB flash, and USB-Serial/JTAG mode (`esptool flash-id`).
- **Current firmware:** vendor application emitting `Wait ETH Connect...`; it is
  not MicroPython and does not provide an `mpremote` raw REPL.

Official W5500 signal map for this product page:

| Signal | GPIO |
| --- | ---: |
| SPI controller input (`machine.SPI` keyword `miso`) | 12 |
| SPI controller output (`mosi`) | 11 |
| clock | 13 |
| chip select | 14 |
| reset | 9 |
| interrupt | 10 |
| PHY address | normally 0 |

This table is documented, not physically verified on the purchased revision.
The firmware keeps all version-sensitive `network.LAN` construction in
`firmware/micropython/src/ethernet.py`.

## Printer

Purchased Rongta RP326 interfaces: Ethernet, USB, and RS-232. Expected but not
physically verified: 80 mm paper, about 72 mm/576-dot printable width, 203 dpi,
up to 250 mm/s, ESC/POS compatibility, and cutter. It uses its own 24 V adapter.
Neither device powers the other.

Expected TCP port 9100 and possible factory IP `192.168.1.87` are defaults to
observe, never constants to trust. Read the printer self-test receipt and record
actual IP, port, firmware, and interfaces here before changing configuration.

## Purchased-unit observations

| Fact | Observed value | Date |
| --- | --- | --- |
| Board revision/silkscreen | pending | — |
| Detected chip | ESP32-S3 QFN56 revision v0.2 | 2026-08-01 |
| Detected flash | 16 MB | 2026-08-01 |
| Detected PSRAM | embedded 8 MB | 2026-08-01 |
| USB mode | USB-Serial/JTAG; `/dev/cu.usbmodem101` on test Mac | 2026-08-01 |
| Printer IP/port | pending | — |
| Printer firmware | pending | — |
| Direct-link negotiation | pending | — |
| Verified cutter command | pending | — |
