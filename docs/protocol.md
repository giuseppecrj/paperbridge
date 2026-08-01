# Print-job protocol

`packages/protocol/schemas/print-job.v1.schema.json` defines a semantic receipt,
not printer bytes. Version `1` bounds IDs, timestamps, block count, strings,
feed lines, multipliers, copies, and total firmware-rendered bytes. Text starts
as printable ASCII; unsupported characters and control bytes are rejected.
Unknown versions and block types are rejected.

V1 blocks are text, feed, rule, and cut. Cut is contractually represented but
execution requires a physically verified printer profile. Raw ESC/POS and bitmap
blocks are forbidden. QR may follow stable text/cutter behavior; images do not.

Statuses are `received`, `validated`, `rendering`, `connecting_to_printer`,
`sending_to_printer`, `delivered_to_printer`, `failed`, `rejected`, and `expired`.
`printed` is intentionally absent until reliable status confirmation is tested.
