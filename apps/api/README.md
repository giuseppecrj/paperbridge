# Private REST/MCP/MQTT service

This portable Node.js TypeScript package implements Paperbridge's private,
single-device Phase 2 REST and Streamable HTTP MCP ingress plus the no-output
MQTT probe. It uses one built-in Node HTTP server; Bun remains workspace tooling
only.

Start authenticated Mosquitto, set the non-secret `.env` values, then run:

```sh
just api
```

The server defaults to `127.0.0.1:3000` and exposes:

- `POST /api/jobs`, accepting a complete source `print-job.v1` body no larger
  than 2,101,248 bytes; prepared MQTT jobs remain limited to 65,536 bytes;
- Streamable HTTP MCP at `/mcp`, with one `paperbridge_print` tool accepting v1
  receipt `content` and generating a fresh `job_id`, configured `device_id`, and
  timestamp; and
- the separate `just mqtt-probe` no-output diagnostic.

REST and MCP call the same `JobSubmissionService`, publish one QoS 1 non-retained
MQTT message, and wait up to 15 seconds by default for the correlated result. Successful delivery ends at
`delivered_to_printer`, never `printed`. PNG/JPEG `image` blocks are accepted
only at REST/MCP: the Node `sharp` adapter validates and prepares a bounded
monochrome `raster` before MQTT. The device never decodes source images.

```sh
curl -sS \
  -H 'content-type: application/json' \
  --data-binary @packages/protocol/fixtures/print-job-v1/valid-text-feed.json \
  http://127.0.0.1:3000/api/jobs
```

MCP uses the official v2 TypeScript SDK's stateless per-request handler. The
plain Node mount rejects non-loopback Host and Origin values. Timeout returns
`unknown` and never republishes; cancellation releases only the host waiter, so
it does not invent a device outcome. Device duplicate suppression is bounded to
one boot and returns `duplicate` / `DUPLICATE_JOB` without another printer
connection.

This remains a private MVP with no public authentication. Keep it on localhost.
The optional MQTT/TLS configuration was physically verified for the bounded
no-output EMQX scope on 2026-08-07; plain local Mosquitto remains the default.
Durable delivery, public OAuth, multi-device routing, and automatic retry are not
implemented.
