# Architecture

## Immediate system

The host CLI speaks newline-delimited JSON over USB serial. The private Node.js
service accepts a raw semantic `print-job.v1` at `POST /api/jobs`, validates the
authoritative schema and configured device, and publishes one bounded MQTT job.
Both ingress paths reach one firmware job module and the same coordinator,
renderer, and printer transport. The shared coordinator serializes every
delivery so USB diagnostics and USB/MQTT jobs cannot open overlapping printer
sockets.

When enabled, one station-mode Wi-Fi adapter supplies the MQTT control plane. A
background network thread polls Wi-Fi and one MQTT adapter; only that thread
touches live WLAN/MQTT clients. The USB RPC loop remains blocking and separate.
The W5500 remains dedicated to the directly attached printer on another subnet.

```text
HTTP client --> Node POST /api/jobs --> Mosquitto --> ESP32 Wi-Fi
USB CLI --------------------------------------------> ESP32 RPC
                                                      |
                                                      +--> shared semantic job
                                                           coordinator
                                                      |
ESP32 W5500 -- direct TCP ESC/POS ------------------> RP326
```

Rendering is separate from delivery. The transport uses one socket per payload
and closes deterministically. `delivered_to_printer` means all bytes were
accepted by the printer-facing socket; it does not mean paper emerged.

## MQTT contracts

The tracer remains separate and no-output:

- `v1/devices/{device_id}/jobs` accepts `mqtt_probe`.
- `v1/devices/{device_id}/status` returns `mqtt_probe_status`.

Semantic jobs use distinct topics so they cannot be confused with probes:

- `v1/devices/{device_id}/print-jobs` accepts raw `print-job.v1`.
- `v1/devices/{device_id}/job-results` returns closed `job-result.v1`.

All messages are MQTT 3.1.1, QoS 1, and non-retained. Job payloads are limited
to 1,024 bytes before parsing. Firmware caches a bounded set of terminal results
by `job_id` for one boot, so QoS redelivery replays the result without a second
printer delivery. This is not a durable queue.

The Node broker adapter keeps one result subscription and correlates pending
HTTP requests by `job_id`. A bounded timeout is `unknown`; it does not expire,
fail, or republish the job. The service supports one configured device only.
Remote cut permission is device configuration (`mqtt.allow_cut`, default false),
never a client field.

## Order and non-goals

USB ping/info precedes direct W5500 initialization; printer reachability remains
separate from paper output. MCP, public authentication, MQTT/TLS, durable queues,
automatic retries, multi-device routing, v2/image content, OTA, and production
provisioning remain out of scope.
