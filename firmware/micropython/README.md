# MicroPython firmware

Milestones 1–4 local firmware: typed USB serial RPC, W5500 adapter, TCP transport,
ASCII ESC/POS tests, and an optional no-output MQTT tracer. Nothing initializes
the direct printer Ethernet or cuts paper at boot. The tracer uses ESP32 Wi-Fi;
the W5500 remains dedicated to the printer, and the tracer has no printer
coordinator reference.

The verified image is MicroPython 1.28.0 `SPIRAM_OCT`; inspect a replacement
board before assuming it has the same memory configuration. See
`docs/micropython-bringup.md`.

Create ignored `firmware/micropython/config.json` from `config.example.json`,
set the observed printer endpoint, then deploy with
`PORT=/dev/cu.usbmodem... just deploy`. Deployment refuses to proceed without
the local config and waits for application RPC readiness after reset. Wi-Fi and
MQTT are disabled by default; enable them only after configuring the Wi-Fi and
local Mosquitto credentials in the ignored config. `config.show_redacted` never
returns either password.
