# Private REST/MQTT service

This portable Node.js TypeScript package implements the private, single-device
Phase 2 `POST /api/jobs` path and retains the no-output MQTT probe. It uses
Node's built-in HTTP server and standard MQTT 3.1.1; Bun is workspace tooling
only.

Start authenticated Mosquitto, set the non-secret `.env` values, then run:

```sh
just api
```

The server defaults to `127.0.0.1:3000`. It accepts a raw `print-job.v1` JSON
body no larger than 1,024 bytes, validates the configured `device_id`, publishes
one QoS 1 non-retained message, and waits for the correlated `job-result.v1`.
A successful response ends at `delivered_to_printer`, never `printed`.

```sh
curl -sS \
  -H 'content-type: application/json' \
  --data-binary @packages/protocol/fixtures/print-job-v1/valid-text-feed.json \
  http://127.0.0.1:3000/api/jobs
```

Timeout returns `unknown` and never republishes automatically. The endpoint is a
private MVP with no public authentication; keep it on localhost or behind the
approved Tailscale boundary. MQTT/TLS, durable delivery, multi-device routing,
and MCP are not implemented.

The separate no-output tracer remains available as `just mqtt-probe`.
