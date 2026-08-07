# Print-job protocol

`packages/protocol/schemas/print-job.v1.schema.json` defines a semantic receipt,
not printer bytes. Version `"1"` requires bounded `job_id`, `device_id`, opaque
`created_at` metadata, and 1–100 receipt blocks. Text is printable ASCII only;
unsupported fields, control bytes, unknown versions/types, and unknown block
types are rejected. Firmware also bounds the rendered output to 64 KiB.

V1 is a pre-release semantic receipt contract that evolves compatibly in place.
Existing text, feed, 48-column rule, and partial-cut jobs remain valid. Text is
word-wrapped at the configured printer width before rendering; words longer than
the width are hard-wrapped. Text may add bounded alignment, bold, single
underline, and 1–2× width/height multipliers. A QR block accepts printable
ASCII up to 256 bytes and renders with fixed model 2, bounded module size 1..8
(default 3), error correction M, and centered alignment. Set the optional `module_size` to any
integer from 1 to 8; it defaults to 3. Cut is schema-valid and must be the final
block when present:

```json
{ "type": "cut", "mode": "partial" }
```

Execution still requires the configured device policy to authorize it. Raw
ESC/POS, copies, expiry, bitmap, color, and arbitrary layout remain unsupported
and fail rather than being ignored.

An API/MCP-only `image` block accepts a PNG or JPEG `data_base64` source of at
most 2,097,152 base64 characters. The Node adapter verifies the declared
signature, bounds decoded sources to 4,000,000 pixels, auto-orients, resizes
within 576×576 pixels, flattens transparency to white, converts to grayscale,
and uses deterministic Floyd–Steinberg monochrome packing. It replaces the
source before MQTT with a `raster` block: `width` 1..576, `height` 1..576, and
canonical `data_base64` whose decoded length is exactly
`ceil(width / 8) * height` and at most 41,472 bytes. The 576-dot width matches
the RP326's documented printable width; the equal height lets square images use
that full width while leaving JSON-envelope headroom under the 65,536-byte MQTT
limit. It is a one-job policy bound, not the printer's vertical paper limit.
Direct USB/MQTT source-image blocks are rejected; firmware accepts and renders
only prepared rasters. Newly generated device configuration raises serial and
MQTT input bounds for these jobs. Older lower bounds remain boot-compatible but
must be regenerated and deployed before maximum rasters can use that ingress.

The renderer uses Epson-compatible `ESC a`, `ESC E`, `ESC -`, `GS !`, and `GS ( k`
sequences. It resets neutral style after styled text and QR blocks, and bounds
each append against the 64 KiB rendered-output limit. Rasters use Epson `GS v 0`
with one-bit black pixels. A `module_size: 5` QR and following partial cut were
physically observed on the purchased RP326 on 2026-08-02. On 2026-08-05, an
operator observed `test.png` printed as a 576×576 raster through REST/MQTT.
JPEG appearance, other style/size appearance, and QR scan/decode readability
remain hardware acceptance work.

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

## REST, MCP, and MQTT job ingress

The private single-device service accepts the raw `print-job.v1` object at
`POST /api/jobs`. HTTP rejects a source job body larger than 2,101,248 bytes
before JSON parsing. After image preparation, the MQTT job is limited to 65,536
bytes. The TypeScript protocol package loads the authoritative JSON Schema
with Ajv; it rejects the same unsupported values as firmware, including
non-integral `feed.lines`.

After validation, the service publishes the compact raw job to
`v1/devices/{device_id}/print-jobs`. Firmware checks the exact topic, payload
limit, schema, configured device, and private cut policy before calling the same
semantic coordinator used by USB. REST/MCP/MQTT callers express a cut in the
job content; they do not provide a separate `allow_cut` command. To enable
remote cuts for a provisioned development device, set
`PAPERBRIDGE_MQTT_ALLOW_CUT=true` in ignored `.env`, then run
`just configure-device` and deploy. The setting defaults to false, so a cut
block returns an explicit rejection until the device is opted in.

Firmware publishes a non-retained QoS 1 result to
`v1/devices/{device_id}/job-results`. The closed
`packages/protocol/schemas/job-result.v1.schema.json` shape contains:

- string `schema_version: "1"` and `kind: "job_result"`;
- the correlated `job_id` and configured `device_id`;
- terminal `status`: `delivered_to_printer`, `rejected`, `failed`, or
  `duplicate`;
- a stable `error_code` for rejection, failure, or `DUPLICATE_JOB`; and
- `bytes_sent` for success or a partial write.

A bounded in-memory firmware ledger stores completed `job_id` values for one
boot. MQTT QoS 1 redelivery of the same `job_id` publishes `duplicate` /
`DUPLICATE_JOB` without another printer socket. It is not a durable queue and
does not survive reboot.

Streamable HTTP MCP is mounted at `/mcp`. Its `paperbridge_print` tool accepts
the authoritative v1 receipt `content`; the service generates a fresh `job_id`,
configured `device_id`, and timestamp before calling the same
`JobSubmissionService` as REST. The transport is stateless per request. Client
cancellation removes only the host waiter and does not label the device outcome.

The REST and MCP service maps validation/device rejection, body limit, broker
unavailability, printer failure/partial write, and timeout distinctly. A timeout
is `unknown`: the service removes only its pending waiter and never republishes
the job. The development result wait defaults to 15 seconds. The complete REST/MCP/MQTT path is host-/simulator-tested with real
local Mosquitto and the real TCP printer simulator. REST/MQTT was physically
verified on 2026-08-02: `job-hw-acceptance-20260802T203016Z` returned HTTP 200
with `delivered_to_printer` after 34 bytes, and an operator observed its expected
receipt. MCP was physically verified the same day through a Pi MCP client: job
`6e46f155-c3f2-4b11-9c56-46f9261f2abe` returned `delivered_to_printer` after 42
bytes, and an operator observed its expected receipt. Results alone still do not
prove paper output.

## MQTT tracer protocol

The optional tracer remains no-output and cannot reach the printer coordinator.
It uses `v1/devices/{device_id}/jobs` for `mqtt_probe` and
`v1/devices/{device_id}/status` for `mqtt_probe_status`. Its numeric
`schema_version: 1` remains a separate tracer contract.

Tracer requests are UTF-8 JSON no larger than 1,024 bytes, require exactly
`schema_version`, `kind`, `probe_id`, `device_id`, and `created_at`, and are
correlated by `probe_id`. A successful status reports tracer receipt only; it
does not indicate job validation, printer delivery, or paper output.
