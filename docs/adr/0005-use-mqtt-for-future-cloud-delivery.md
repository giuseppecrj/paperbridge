# ADR 0005: Use MQTT for future cloud delivery

- Status: Superseded by ADR 0006
- Date: 2026-08-01

## Context

A future backend needs outbound, encrypted device communication without exposing
the ESP32 to public inbound connections.

## Decision

After local milestones and Wi-Fi/Ethernet concurrency pass, evaluate MQTT over
TLS using versioned per-device jobs, commands, status, events, and acknowledgement
topics. Reuse the semantic job and coordinator contracts.

## Consequences

ADR 0006 now governs the local MQTT 3.1.1 tracer: it is limited to an
authenticated no-output probe and does not implement a backend or MQTT job
delivery. TLS, cloud MQTT, and the full credential lifecycle remain deferred.
Failure of memory, routing, TLS, soak, OTA, or credential gates triggers ESP-IDF
evaluation.
