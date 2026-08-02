# MQTT tracer

This Node.js TypeScript package is the Phase 2 no-output MQTT tracer, not an API
service yet. `bun` manages the workspace; the probe runs with Node.js and uses
standard MQTT 3.1.1.

```sh
just mqtt-probe
```

It requires `PAPERBRIDGE_MQTT_HOST`, `PAPERBRIDGE_MQTT_USERNAME`,
`PAPERBRIDGE_MQTT_PASSWORD`, and `PAPERBRIDGE_DEVICE_ID`. It publishes one QoS
1, non-retained `mqtt_probe` and waits for the matching `mqtt_probe_status`.
It neither submits a print job nor contacts a printer.

Run the authenticated broker from [`tools/mosquitto`](../../tools/mosquitto).
