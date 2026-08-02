# MQTT tracer

This Node.js TypeScript package is the Phase 2 no-output MQTT tracer, not an API
service yet. `bun` manages the workspace; the probe runs with Node.js and uses
standard MQTT 3.1.1.

```sh
just mqtt-probe
```

The recipe loads non-secret host, username, and device identity from ignored
`.env` and resolves `PAPERBRIDGE_MQTT_PASSWORD` through the checked-in Fnox
project mapping. It publishes one QoS 1, non-retained `mqtt_probe` and waits for
the matching `mqtt_probe_status`.
It neither submits a print job nor contacts a printer.

Run the authenticated broker from [`tools/mosquitto`](../../tools/mosquitto).
