# MicroPython firmware

Milestones 1–4 local firmware: typed USB serial RPC, W5500 adapter, TCP transport,
and ASCII ESC/POS tests. Nothing initializes Ethernet or cuts paper at boot.

The verified image is MicroPython 1.28.0 `SPIRAM_OCT`; inspect a replacement
board before assuming it has the same memory configuration. See
`docs/micropython-bringup.md`.

Create ignored `firmware/micropython/config.json` from `config.example.json`,
set the observed printer endpoint, then deploy with
`PORT=/dev/cu.usbmodem... just deploy`. Deployment refuses to proceed without
the local config and waits for application RPC readiness after reset.
