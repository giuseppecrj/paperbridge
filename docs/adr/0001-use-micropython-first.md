# ADR 0001: Use MicroPython first

- Status: Accepted for bring-up
- Date: 2026-08-01

## Context

The shortest path to validating USB, W5500, TCP, and ESC/POS is interactive
firmware with host-testable Python logic. At decision time, the hardware path
was not yet proven.

## Decision

Use current stable MicroPython 1.28.0 and its ESP32-S3 octal-SPIRAM build after
runtime memory verification. Keep version-sensitive LAN code in one adapter.
ESP-IDF is the production fallback; Arduino is diagnostic-only.

## Migration criteria

Move to ESP-IDF if W5500/USB is absent or unstable; Wi-Fi and Ethernet cannot
coexist or route reliably; MQTT/TLS exhausts or fragments memory; a 72-hour soak
fails; reliable OTA or secure credentials need IDF facilities; normal failures
cause watchdog resets; or status querying needs lower-level control.

## Consequences

Bring-up is fast and observable, but no production reliability claim exists until
physical tests and soak gates pass.
