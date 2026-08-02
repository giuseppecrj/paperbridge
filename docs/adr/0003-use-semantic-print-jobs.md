# ADR 0003: Use semantic print jobs

- Status: Accepted
- Date: 2026-08-01

## Context

Exposing raw printer bytes would make future public clients unsafe and couple all
senders to printer details.

## Decision

Use versioned, bounded JSON Schema with receipt blocks. The pre-release v1
contract supports printable ASCII text, bounded text styling, feed, rule, fixed
policy QR, and an explicitly authorized cut. Reject raw bytes, unknown
versions/types, control injection, unsupported characters/options, and oversized
output.

## Consequences

Serial and future cloud ingress can share validation/rendering. Raster images and
other arbitrary document content remain deferred; unsupported content fails
explicitly.
