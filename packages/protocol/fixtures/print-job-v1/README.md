# print-job.v1 fixtures

Shared semantic jobs used by host JSON Schema tests and on-device
`validate_job` / `EscPosRenderer` tests.

## Groups

- **Schema-valid** (`valid-*.json`): pass JSON Schema. Device validator and
  renderer accept them under default policy (except cut — see below).
- **Schema-invalid** (`invalid-*.json`): fail JSON Schema and `validate_job`.
  Must not render.
- **Policy / authorization** (`cut-requires-opt-in.json`, and cut blocks in
  `valid-cut.json`): schema-valid cut content that still needs explicit
  `allow_cut=True` at validate/render boundaries. Default policy rejects cut;
  this is execution authorization, not contract invalidity.

`created_at` is bounded opaque metadata for v1 (string length only), not a
parsed timestamp contract.
