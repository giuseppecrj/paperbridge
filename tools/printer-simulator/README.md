# Printer simulator

Run `just printer-simulator`; it listens on `127.0.0.1:9100`, saves raw payloads
under `captures/`, and prints byte counts and SHA-256 values.

Fault flags: `--accept-delay`, `--read-delay`, `--read-size 1`, `--close-after N`,
and `--reset-after N`. Connection refusal is tested by targeting a port with no
server. Use it from an ESP32 only when the Mac and ESP32 share a suitable test
network; it is not required for the direct printer link.
