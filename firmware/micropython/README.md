# MicroPython firmware

Milestones 1–4 local firmware: typed USB serial RPC, W5500 adapter, TCP transport,
and ASCII ESC/POS tests. Nothing initializes Ethernet or cuts paper at boot.

The candidate image is MicroPython 1.28.0 `SPIRAM_OCT`; verify the purchased
board revision and chip before flashing. See `docs/micropython-bringup.md`.

Deploy with `PORT=/dev/cu.usbmodem... just deploy`. The deploy script copies
`config.example.json` as `config.json`; edit the local example first with the
printer endpoint observed on its self-test receipt.
