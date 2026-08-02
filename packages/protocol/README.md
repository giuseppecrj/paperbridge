# Shared protocol

Authoritative versioned schemas and fixtures for serial RPC, semantic print
jobs, correlated device results, and device events. Public clients never supply
raw ESC/POS.

The TypeScript interface in `src/index.ts` loads the authoritative JSON Schemas
with Ajv; it does not reimplement semantic validation manually. It also defines
the 1,024-byte MQTT job transport limit and dedicated `print-jobs` / `job-results`
topic shape.

`cut` remains schema-valid content, but MQTT execution is controlled only by the
device's private `mqtt.allow_cut` policy. Callers cannot grant themselves cut
permission.
