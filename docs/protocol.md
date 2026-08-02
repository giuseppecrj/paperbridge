# Print-job protocol

`packages/protocol/schemas/print-job.v1.schema.json` defines a semantic receipt,
not printer bytes. Version `1` requires bounded `job_id`, `device_id`, opaque
`created_at` metadata, and 1–100 receipt blocks. Text is printable ASCII only;
unsupported fields, control bytes, unknown versions, and unknown block types are
rejected. Firmware also bounds the final rendered byte count.

V1 blocks are text, feed, 48-column rule, and partial cut. Cut is schema-valid
but validation and rendering both require explicit caller authorization. Raw
ESC/POS, styling, copies, expiry, bitmap, and QR blocks are not v1 semantics and
fail rather than being ignored.

The status vocabulary is currently internal scaffolding; no semantic print-job
RPC or durable lifecycle is live. A future job result may end at
`delivered_to_printer`, which means bytes reached the printer-facing socket.
`printed` remains absent until reliable physical status confirmation exists.
