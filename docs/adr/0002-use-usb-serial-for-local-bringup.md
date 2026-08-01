# ADR 0002: Use USB serial for local bring-up

- Status: Accepted
- Date: 2026-08-01

## Context

The printer must be reachable through the ESP32 without cloud, Wi-Fi, CUPS, a
Raspberry Pi, or a laptop-printer network route.

## Decision

Use bounded UTF-8 newline-delimited JSON over the board's USB serial interface.
The host CLI correlates request IDs. Typed response/log envelopes prevent logs
from masquerading as replies. `mpremote` remains deployment/REPL tooling only.

## Consequences

The complete local hardware path can be isolated. USB behavior still requires
physical stability testing on the purchased board.
