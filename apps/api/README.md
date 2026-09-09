# Private REST/MCP/MQTT service

This portable Node.js TypeScript package implements Paperbridge's private,
single-device Phase 2 REST and Streamable HTTP MCP ingress plus the no-output
MQTT probe. It uses one built-in Node HTTP server. Bun manages the workspace and
bundles the production JavaScript; Node remains the application runtime.

Start authenticated Mosquitto, set the non-secret `.env` values, then run the
TypeScript source for local development:

```sh
just api
```

Build and run the same server as the production Node artifact with:

```sh
bun run --filter @paperbridge/api build
bun run --filter @paperbridge/api start:production
```

The build writes `dist/server.js` for the API and `dist/main.js` for the
no-output MQTT tracer. It keeps `sharp` external so Node can load its native
binary. Application code does not use Bun runtime APIs.

Build the digest-pinned Bun/Node image and run its explicit local acceptance
check with Docker, Mosquitto, and `mosquitto_passwd` available:

```sh
just test-api-container
```

The check runs one API container as the image's non-root user with a read-only
root filesystem, no capabilities, `no-new-privileges`, bridged networking, and
host-loopback-only port publication. It mounts a temporary MQTT password file
read-only, verifies that the value is absent from image history, environment
metadata, arguments, and logs, and exercises health, readiness, REST limits,
MCP, Linux-native `sharp` image preparation, MQTT correlation, and SIGTERM.
Its MQTT peer is a Host test client; it does not contact a Device or Printer and
cannot prove physical output. The checked-in candidate-VM operator exists, but
running and accepting it remains issue #29.

Local Fnox commands continue to provide `PAPERBRIDGE_MQTT_PASSWORD` directly.
A deployed runtime may instead set `PAPERBRIDGE_MQTT_PASSWORD_FILE` to a
non-empty mounted credential. The API and no-output probe read the file once at
startup without trimming it. Set exactly one of these variables; neither value
is included in startup errors.

The server defaults to `127.0.0.1:3000` and exposes:

- `POST /api/jobs`, accepting a complete source `print-job.v1` body no larger
  than 2,101,248 bytes; prepared MQTT jobs remain limited to 65,536 bytes;
- Streamable HTTP MCP at `/mcp`, with one `paperbridge_print` tool accepting v1
  receipt `content` and generating a fresh `job_id`, configured `device_id`, and
  timestamp; its complete HTTP body, including the JSON-RPC envelope, is also
  limited to 2,101,248 bytes before SDK parsing;
- the separate `just mqtt-probe` no-output diagnostic;
- `GET /health`, which reports only Node process liveness; and
- `GET /ready`, which reports MQTT readiness and whether the application accepts
  new submissions.

REST and MCP call the same `JobSubmissionService`, publish one QoS 1 non-retained
MQTT message, and wait up to 15 seconds by default for the correlated result.
Successful delivery ends at `delivered_to_printer`, never `printed`. PNG/JPEG
`image` blocks are accepted
only at REST/MCP: the Node `sharp` adapter validates and prepares a bounded
monochrome `raster` before MQTT. The device never decodes source images.

```sh
curl -sS \
  -H 'content-type: application/json' \
  --data-binary @packages/protocol/fixtures/print-job-v1/valid-text-feed.json \
  http://127.0.0.1:3000/api/jobs
```

MCP uses the official v2 TypeScript SDK's stateless per-request handler. Both
the REST job route and MCP mount reject unconfigured Host and Origin values. They allow
`localhost`, `127.0.0.1`, and `[::1]` loopback hosts by default; a private proxy
may add one hostname with `PAPERBRIDGE_API_ALLOWED_HOST` and its exact HTTPS
origin with `PAPERBRIDGE_API_ALLOWED_ORIGIN`. Requests without an Origin are
allowed for non-browser clients. Loopback development Origins use a
loopback hostname and may use HTTP or HTTPS with a local port. The configured
proxy Origin must be HTTPS and have no path, query, or fragment.

Both submission routes count actual request bytes, including chunked bodies,
and reject oversized bodies with HTTP 413 before parsing or submitting work.

`/health` remains 200 when MQTT is disconnected. `/ready` is 200 only after the
application MQTT client has connected and subscribed to job results and while
the application accepts new submissions; otherwise it is 503. Neither route
probes or reports Device or Printer state.

On SIGINT or SIGTERM, the application starts draining before it closes MCP,
MQTT, or HTTP resources. New REST and MCP submissions fail with
`SERVICE_DRAINING` and do not publish MQTT work. Already accepted submissions
can receive their correlated result or reach the existing timeout without a
republish. `/health` remains live and `/ready` remains unavailable until draining
finishes, after which the resources close in order. The default 15-second result
wait fits within the 20-second systemd stop allowance.

Timeout returns `unknown` and never republishes; cancellation releases only the
host waiter, so it does not invent a device outcome. Device duplicate suppression
is bounded to one boot and returns `duplicate` / `DUPLICATE_JOB` without another
printer connection.

This remains a private MVP with no public authentication. The exe.dev proxy
must remain private and must provide the infrastructure access control. Keep the
Node service bound to loopback. For deployed private REST/MCP client setup, see
[`../../docs/private-cloud-access.md`](../../docs/private-cloud-access.md).
The optional MQTT/TLS configuration was physically verified for the bounded
no-output EMQX scope on 2026-08-07; plain local Mosquitto remains the default.
Durable delivery, public OAuth, multi-device routing, and automatic retry are not
implemented.
