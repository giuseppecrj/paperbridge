# Source register

Research performed 2026-08-01 and 2026-08-02. Claims below are documentation
facts, not physical verification of purchased units.

| Topic | Primary source | Recorded fact |
| --- | --- | --- |
| Waveshare ESP32-S3-ETH | <https://www.waveshare.com/wiki/ESP32-S3-ETH> | SKU 28972 board-only option; ESP32-S3R8; 16 MB flash; 8 MB PSRAM; W5500; USB-C; GPIO 12/11/13/14/9/10 mapping. Purchased photos confirm the product silkscreen but expose no explicit PCB revision. |
| Waveshare schematic | <https://files.waveshare.com/wiki/ESP32-S3-ETH/ESP32-S3-ETH-Schematic.pdf> | Official schematic to compare with purchased board revision before relying on wiring. |
| MicroPython S3 downloads | <https://micropython.org/download/ESP32_GENERIC_S3/> | Generic S3 firmware auto-detects ordinary SPIRAM; official page directs octal-SPIRAM boards to `spiram-oct`. |
| MicroPython 1.28 release | <https://github.com/micropython/micropython/releases/tag/v1.28.0> | Stable v1.28.0, released 2026-04-06. |
| Selected binary | <https://micropython.org/resources/firmware/ESP32_GENERIC_S3-SPIRAM_OCT-20260406-v1.28.0.bin> | HTTP 200; 1,758,064 bytes; repository-research SHA-256 `67c19ae123d84152019b57526ed5291dd0a2b4edd87655c5f76b46c9a62ff5dd`. Re-verify when downloading. |
| ESP32 LAN API | <https://docs.micropython.org/en/v1.28.0/esp32/quickref.html#lan> | SPI Ethernet uses `network.LAN`; W5500 requires SPI, CS, interrupt, PHY type/address; reset optional; SPI baud is compile-time for Ethernet. |
| ESP32 WLAN API | <https://docs.micropython.org/en/v1.28.0/library/network.WLAN.html> | Station mode uses `network.WLAN(network.WLAN.IF_STA)`, `active(True)`, `connect`, `status`, and `isconnected`; DHCP supplies its address. This documents the API, not purchased-device Wi-Fi/W5500 coexistence. |
| v1.28 implementation | <https://github.com/micropython/micropython/blob/v1.28.0/ports/esp32/network_lan.c> | W5500 path and `active`, `status`, `isconnected`, `ifconfig`, and `ipconfig` methods exist when compiled in. `network.LAN` returns one initialized singleton, and `active(True)` is a no-op while already active; an explicit `active(False)` / `active(True)` cycle restarts it. Runtime verification remains mandatory. |
| RP32X manual | <https://file.globalso.com/file_manage/4365/20260416/rp32x-series-user-manual_v1-3_en.pdf> | Official family manual covering RP326: hold FEED during power-on and release within about five seconds for self-test; the receipt reports software, interfaces, and printer configuration. |
| Epson ESC/POS QR commands | <https://download4.epson.biz/sec_pubs/pos/reference_en/escpos/gs_lparen_lk.html> | Official ESC/POS references document QR model, module size, error-correction, store-data, and print commands using `GS ( k`; store length is data bytes plus three control bytes. |
| Fnox configuration | <https://fnox.jdx.dev/reference/configuration> | Checked-in `fnox.toml` supports hierarchical project configuration, remote references, profiles, local overrides, and exec-only injection; Fnox 1.31.1 is required for the selected `env = "exec"` setting. |
| Fnox 1Password provider | <https://fnox.jdx.dev/providers/1password> | A secret mapping may contain an `op://vault/item/field` reference rather than a value; resolution uses 1Password CLI authentication. |
| 1Password CLI | <https://developer.1password.com/docs/cli/secret-reference-syntax> | `op://` references identify vault/item/field locations and resolve the latest stored value without embedding plaintext in configuration. |
| Epson ESC/POS text commands | <https://download4.epson.biz/sec_pubs/pos/reference_en/escpos/> | Official ESC/POS references document `ESC a`, `ESC E`, `ESC -`, and `GS !` for alignment, emphasis, underline, and character size. |
| MCP TypeScript SDK v2 | <https://ts.sdk.modelcontextprotocol.io/v2/serving/http.html> | `@modelcontextprotocol/server` provides stateless per-request `createMcpHandler`; `@modelcontextprotocol/node` adapts it to plain Node HTTP. Tool cancellation is exposed as `ctx.mcpReq.signal`; plain mounts must add Host/Origin validation and close the handler during shutdown. |

## Purchased-unit observations

Physical observations are recorded separately from primary-source facts in
`docs/hardware.md`. On 2026-08-01 the purchased unit accepted TCP at
`192.168.1.87:9100`; text, feed, and explicit partial-cut bytes `1d 56 01` were
physically observed. On 2026-08-02 the dedicated direct network moved to W5500
`192.168.4.50/24` and printer `192.168.4.87:9100`; reachability was physically
observed without printing. Station-mode Wi-Fi also completed a correlated local
MQTT probe while direct-printer reachability remained available. On 2026-08-02
the official self-test procedure reported firmware `GD207_V1.14`;
purchased-board photos confirmed `ESP32-S3-ETH` silkscreen without an explicit
PCB revision.
