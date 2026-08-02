# Print-job protocol

`packages/protocol/schemas/print-job.v1.schema.json` defines a semantic receipt,
not printer bytes. Version `"1"` requires bounded `job_id`, `device_id`, opaque
`created_at` metadata, and 1–100 receipt blocks. Text is printable ASCII only;
unsupported fields, control bytes, unknown versions/types, and unknown block
types are rejected. Firmware also bounds the rendered output to 32 KiB.

V1 blocks are text, feed, 48-column rule, and partial cut. Cut is schema-valid,
but execution policy and rendering must authorize it. Raw ESC/POS, styling,
copies, expiry, bitmap, and QR blocks are not v1 semantics and fail rather than
being ignored.

## USB ingress

Local USB RPC implements `job.submit`. It validates a submitted v1 job against
the configured `device_id`, renders it through the shared coordinator, and
returns its `job_id` with `delivered_to_printer` when all bytes reached the
printer-facing socket. `allow_cut: true` is an explicit local USB authorization.
Serial `request_id` remains transport correlation/replay only; it is distinct
from `job_id`.

This path is host-/simulator-tested and was physically verified on 2026-08-02:
`job-hello-001` returned `delivered_to_printer` after 28 bytes, and an operator
observed its fixture receipt. `printed` remains absent until reliable printer
status confirmation exists.

## REST and MQTT job ingress

The private single-device service accepts the raw `print-job.v1` object at
`POST /api/jobs`. HTTP rejects a body larger than 1,024 bytes before JSON
parsing. The TypeScript protocol package loads the authoritative JSON Schema
with Ajv; it rejects the same unsupported values as firmware, including
non-integral `feed.lines`.

After validation, the service publishes the compact raw job to
`v1/devices/{device_id}/print-jobs`. Firmware checks the exact topic, payload
limit, schema, configured device, and private cut policy before calling the same
semantic coordinator used by USB. REST/MQTT callers cannot provide `allow_cut`;
`mqtt.allow_cut` defaults to false on the device.

Firmware publishes a non-retained QoS 1 result to
`v1/devices/{device_id}/job-results`. The closed
`packages/protocol/schemas/job-result.v1.schema.json` shape contains:

- string `schema_version: "1"` and `kind: "job_result"`;
- the correlated `job_id` and configured `device_id`;
- terminal `status`: `delivered_to_printer`, `rejected`, or `failed`;
- a stable `error_code` for rejection/failure; and
- `bytes_sent` for success or a partial write.

A bounded in-memory firmware ledger stores terminal results for one device boot.
MQTT QoS 1 redelivery of the same `job_id` replays that result without another
printer socket. It is not a durable queue and does not survive reboot.

The HTTP service maps validation/device rejection, body limit, broker
unavailability, printer failure/partial write, and timeout distinctly. A timeout
is `unknown`: the service removes only its pending waiter and never republishes
the job. The complete REST/MQTT path is host-/simulator-tested with real local
Mosquitto and the real TCP printer simulator. It was also physically verified
on 2026-08-02: `job-hw-acceptance-20260802T203016Z` returned HTTP 200 with
`delivered_to_printer` after 34 bytes, and an operator observed its expected
receipt. The result alone still does not prove paper output.

## MQTT tracer protocol

The optional tracer remains no-output and cannot reach the printer coordinator.
It uses `v1/devices/{device_id}/jobs` for `mqtt_probe` and
`v1/devices/{device_id}/status` for `mqtt_probe_status`. Its numeric
`schema_version: 1` remains a separate tracer contract.

Tracer requests are UTF-8 JSON no larger than 1,024 bytes, require exactly
`schema_version`, `kind`, `probe_id`, `device_id`, and `created_at`, and are
correlated by `probe_id`. A successful status reports tracer receipt only; it
does not indicate job validation, printer delivery, or paper output.
