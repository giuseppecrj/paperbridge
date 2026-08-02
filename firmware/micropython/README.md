# MicroPython firmware

Milestones 1–4 local firmware: typed USB serial RPC, W5500 adapter, TCP transport,
ASCII ESC/POS tests, and an optional no-output MQTT tracer. Nothing initializes
the direct printer Ethernet or cuts paper at boot. The tracer uses ESP32 Wi-Fi;
the W5500 remains dedicated to the printer, and the tracer has no printer
coordinator reference.

The verified image is MicroPython 1.28.0 `SPIRAM_OCT`; inspect a replacement
board before assuming it has the same memory configuration. See
`docs/micropython-bringup.md`.

For the networked development path, copy `.env.example` to ignored `.env`, set
this machine's non-secret addresses, then run `just configure-device`. The recipe
resolves Wi-Fi and MQTT passwords from project `fnox.toml`/1Password and writes
ignored `firmware/micropython/config.json` without putting passwords in command
arguments. For Ethernet-only use, copy `config.example.json` manually and leave
Wi-Fi/MQTT disabled.

Deploy with `PORT=/dev/cu.usbmodem... just deploy`. Deployment refuses to
proceed without local config and waits for RPC readiness after reset.
`config.show_redacted` never returns either password.
