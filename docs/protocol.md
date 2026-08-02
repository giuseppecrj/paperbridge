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

## MQTT tracer protocol

The optional local tracer is not a semantic print job and cannot reach the
printer coordinator. It uses the ESP32 Wi-Fi control plane with authenticated
MQTT 3.1.1, QoS 1, and non-retained messages; the direct W5500 printer link is
not involved. The device subscribes only to `v1/devices/{device_id}/jobs` and
publishes only to `v1/devices/{device_id}/status`.

A request is UTF-8 JSON no larger than the configured 1024-byte default:

```json
{
  "schema_version": 1,
  "kind": "mqtt_probe",
  "probe_id": "probe-001",
  "device_id": "paperbridge-dev-001",
  "created_at": "2026-08-02T00:00:00Z"
}
```

The device requires exactly these fields, matching `device_id`, a 1–128
character `probe_id`, and a 1–64 character opaque `created_at`; wrong topic,
device, malformed JSON, oversized payload, and unknown fields are rejected
without a response or printer call. A successful correlated response is:

```json
{
  "schema_version": 1,
  "kind": "mqtt_probe_status",
  "probe_id": "probe-001",
  "device_id": "paperbridge-dev-001",
  "status": "ok",
  "ts_ms": 123
}
```

This reports only tracer receipt. It does not indicate job validation,
`delivered_to_printer`, or physical paper output.
