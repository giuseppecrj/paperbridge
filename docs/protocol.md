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

Local USB RPC implements `job.submit`. It validates a submitted v1 job against
the configured `device_id`, renders it through the shared coordinator, and
returns its `job_id` with `delivered_to_printer` when all bytes reached the
printer-facing socket. `allow_cut: true` is required for a cut block. Serial
`request_id` remains transport correlation/replay only; it is distinct from
`job_id`. There is no durable lifecycle, queue, or job-id deduplication.

This path is host- and simulator-tested and was physically verified on
2026-08-02: `job-hello-001` returned `delivered_to_printer` after 28 bytes, and
an operator observed its fixture receipt. `printed` remains absent until
reliable printer status confirmation exists.
