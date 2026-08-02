# print-job.v1 fixtures

Shared semantic jobs used by host JSON Schema tests and on-device
`validate_job` / `EscPosRenderer` tests.

## Groups

- **Schema-valid** (`valid-*.json`): pass JSON Schema. Device validator and
  renderer accept them under default policy (except cut — see below).
- **Schema-invalid** (`invalid-*.json`): fail JSON Schema and `validate_job`.
  Must not render.
- **Policy / authorization** (`cut-requires-opt-in.json`, and cut blocks in
  `valid-cut.json`): schema-valid cut content that still needs explicit device
  policy at execution. Default policy rejects cut; this is authorization, not
  contract invalidity.
- **Transport boundary** (`valid-at-mqtt-limit.json` and
  `schema-valid-over-mqtt-limit.json`): both are schema-valid; their raw files
  are exactly 1,024 and 1,025 bytes so HTTP/MQTT size rejection is tested
  separately from semantic validation.

`created_at` is bounded opaque metadata for v1 (string length only), not a
parsed timestamp contract.
