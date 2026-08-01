# MicroPython bring-up

## Candidate release

Official MicroPython 1.28.0 (released 2026-04-06) is the selected stable line.
The official Waveshare documentation identifies ESP32-S3R8 with octal PSRAM, so
the candidate artifact is:

- Source: `https://micropython.org/download/ESP32_GENERIC_S3/`
- File: `ESP32_GENERIC_S3-SPIRAM_OCT-20260406-v1.28.0.bin`
- Direct source URL: `https://micropython.org/resources/firmware/ESP32_GENERIC_S3-SPIRAM_OCT-20260406-v1.28.0.bin`
- Size observed during repository research: 1,758,064 bytes.
- SHA-256 observed from that official URL: `67c19ae123d84152019b57526ed5291dd0a2b4edd87655c5f76b46c9a62ff5dd`.
- Flash offset: 0.

Re-download and verify the hash at bring-up time. Do not use the octal build until
the purchased board revision/chip matches official documentation.

## Runtime verification

Run `PORT=... just verify-board`, then record implementation/version, uname/chip,
reset cause, free heap, filesystem, flash size, observable PSRAM, `PHY_W5500`,
`LAN`, and USB stability. The W5500 adapter follows the 1.28 documented required
arguments and retains legacy four-field `ifconfig` behind one version seam.
Verify initialization, physical link, static IPv4, socket creation, and connect/
write timeout behavior on the actual board.

## Flash

Exact commands are in the root README. Erase first on initial installation;
flash at 460800 and retry without the high baud if transfer fails.
