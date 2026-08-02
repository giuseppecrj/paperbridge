# MicroPython bring-up

## Verified release

Official MicroPython 1.28.0 (released 2026-04-06) is the selected stable line.
The purchased ESP32-S3 runtime exposed 16 MB flash and 8 MB PSRAM, and the
successfully flashed artifact is:

- Source: `https://micropython.org/download/ESP32_GENERIC_S3/`
- File: `ESP32_GENERIC_S3-SPIRAM_OCT-20260406-v1.28.0.bin`
- Direct source URL: `https://micropython.org/resources/firmware/ESP32_GENERIC_S3-SPIRAM_OCT-20260406-v1.28.0.bin`
- Size observed during repository research: 1,758,064 bytes.
- SHA-256 observed from that official URL: `67c19ae123d84152019b57526ed5291dd0a2b4edd87655c5f76b46c9a62ff5dd`.
- Flash offset: 0.

Re-download and verify the hash at bring-up time. The image was physically
flashed and verified on 2026-08-01; still inspect a replacement board before
assuming it has the same memory configuration.

## Runtime verification

`PORT=... just verify-board` confirmed MicroPython, the expected chip memory,
`PHY_W5500`, and `LAN`. USB application RPC, W5500 initialization, repeated
static IPv4 configuration, direct link, and printer probe were also physically
verified on 2026-08-01. The adapter uses the MicroPython 1.28 `ipconfig()` API
behind one version seam and preserves the four-field RPC address response.

Controlled post-deploy power-cycle smoke and paper-path acceptance passed on
2026-08-02. Ethernet reconnect, fault recovery, and the 72-hour soak remain
separate acceptance gates.

## Flash

Exact commands are in the root README. Initial erase requires
`CONFIRM=erase`; flash at 460800 and retry without the high baud if transfer
fails. The normal flash recipe enforces the verified SHA-256.
