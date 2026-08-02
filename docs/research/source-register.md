# Source register

Research performed 2026-08-01. Claims below are documentation facts, not
physical verification of purchased units.

| Topic | Primary source | Recorded fact |
| --- | --- | --- |
| Waveshare ESP32-S3-ETH | <https://www.waveshare.com/wiki/ESP32-S3-ETH> | SKU 28972 board-only option; ESP32-S3R8; 16 MB flash; 8 MB PSRAM; W5500; USB-C; GPIO 12/11/13/14/9/10 mapping. Purchased revision still pending inspection. |
| Waveshare schematic | <https://files.waveshare.com/wiki/ESP32-S3-ETH/ESP32-S3-ETH-Schematic.pdf> | Official schematic to compare with purchased board revision before relying on wiring. |
| MicroPython S3 downloads | <https://micropython.org/download/ESP32_GENERIC_S3/> | Generic S3 firmware auto-detects ordinary SPIRAM; official page directs octal-SPIRAM boards to `spiram-oct`. |
| MicroPython 1.28 release | <https://github.com/micropython/micropython/releases/tag/v1.28.0> | Stable v1.28.0, released 2026-04-06. |
| Selected binary | <https://micropython.org/resources/firmware/ESP32_GENERIC_S3-SPIRAM_OCT-20260406-v1.28.0.bin> | HTTP 200; 1,758,064 bytes; repository-research SHA-256 `67c19ae123d84152019b57526ed5291dd0a2b4edd87655c5f76b46c9a62ff5dd`. Re-verify when downloading. |
| ESP32 LAN API | <https://docs.micropython.org/en/v1.28.0/esp32/quickref.html#lan> | SPI Ethernet uses `network.LAN`; W5500 requires SPI, CS, interrupt, PHY type/address; reset optional; SPI baud is compile-time for Ethernet. |
| v1.28 implementation | <https://github.com/micropython/micropython/blob/v1.28.0/ports/esp32/network_lan.c> | W5500 path and `active`, `status`, `isconnected`, `ifconfig`, and `ipconfig` methods exist when compiled in. Runtime verification remains mandatory. |
| RP326 material | Purchased unit self-test and Rongta material (pending collection) | Firmware details, documented capabilities, and physical status protocol still need primary-source collection. |

## Purchased-unit observations

Physical observations are recorded separately from primary-source facts in
`docs/hardware.md`. On 2026-08-01 the purchased unit accepted TCP at
`192.168.1.87:9100`; text, feed, and explicit partial-cut bytes `1d 56 01` were
physically observed. Printer firmware and first-party manual/configuration
utility details remain pending.
