# Testing

Host-only verification:

```sh
just lint
just format-check
just test
```

Tests cover request parsing/correlation, malformed and oversized JSON, stable
unsupported-command errors, strict cut confirmation, configuration validation,
schema rejection of raw blocks, exact ESC/POS bytes, ASCII/control sanitization,
bounded FIFO behavior, status transitions, port ambiguity, and simulator
capture hashing.

`just printer-simulator` captures TCP bytes and supports delayed accept/read,
small partial reads, close/reset during transfer, payload recording, and SHA-256.
Connection refusal is represented by targeting a stopped server.

No automated test claims hardware success. The 20-step purchased-hardware
checklist is in the root README and `local-bringup.md`. A 72-hour soak is a
MicroPython production gate.
