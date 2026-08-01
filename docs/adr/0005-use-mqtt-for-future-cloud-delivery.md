# ADR 0005: Use MQTT for future cloud delivery

- Status: Proposed; implementation deferred
- Date: 2026-08-01

## Context

A future backend needs outbound, encrypted device communication without exposing
the ESP32 to public inbound connections.

## Decision

After local milestones and Wi-Fi/Ethernet concurrency pass, evaluate MQTT over
TLS using versioned per-device jobs, commands, status, events, and acknowledgement
topics. Reuse the semantic job and coordinator contracts.

## Consequences

No MQTT broker, client, backend, or website is initialized now. Failure of
memory, routing, TLS, soak, OTA, or credential gates triggers ESP-IDF evaluation.
