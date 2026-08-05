# print-job.v1 fixtures

Shared semantic jobs used by host JSON Schema tests and on-device
`validate_job` / `EscPosRenderer` tests.

## Groups

- **Device-valid** (`valid-text-*`, `valid-rule-*`, `valid-qr-*`, and
  `valid-rich-*`): pass JSON Schema and firmware validation under default policy
  (except cut — see below).
- **API/MCP source-image** (`valid-image-*-source.json` and
  `valid-image-rich-receipt.json`): pass JSON Schema but require host preparation;
  firmware accepts only the resulting raster representation.
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
parsed timestamp contract. `expected-rich-receipt.bin` is the exact host-tested
ESC/POS output for the representative rich fixture; style and QR appearance
remain unverified on purchased hardware. The rich fixture intentionally omits
cut; add `{ "type": "cut", "mode": "partial" }` as its final block only when
the target device has remote cutting opted in. `expected-image-rich-receipt.bin`
is the exact host-/simulator-tested output after the API prepares the PNG source
in `valid-image-rich-receipt.json`; it is not physical image evidence.
