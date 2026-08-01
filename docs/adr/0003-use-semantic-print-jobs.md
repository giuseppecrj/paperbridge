# ADR 0003: Use semantic print jobs

- Status: Accepted
- Date: 2026-08-01

## Context

Exposing raw printer bytes would make future public clients unsafe and couple all
senders to printer details.

## Decision

Use versioned, bounded JSON Schema with receipt blocks. Start with printable
ASCII text, feed, rule, and an explicitly verified cut. Reject raw bytes, unknown
versions/types, control injection, unsupported characters, excessive copies, and
oversized output.

## Consequences

Serial and future cloud ingress can share validation/rendering. Images and QR are
deferred; unsupported content fails explicitly.
