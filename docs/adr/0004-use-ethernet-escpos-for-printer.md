# ADR 0004: Use Ethernet ESC/POS for the printer

- Status: Accepted for bring-up
- Date: 2026-08-01

## Context

The RP326 purchased interface includes Ethernet and is expected to accept raw
ESC/POS over TCP, commonly port 9100.

## Decision

The ESP32 owns the configurable TCP connection and sends one rendered job at a
time with connect/write timeouts and deterministic close. Rendering and
transport remain separate. A completed write is `delivered_to_printer`, never
`printed`.

## Consequences

No printer driver or direct Mac network route is needed. Actual endpoint,
protocol compatibility, status behavior, and cutter bytes remain physical tests.
