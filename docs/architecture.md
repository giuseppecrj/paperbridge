# Architecture

## Immediate system

The host CLI speaks newline-delimited JSON over USB serial. Firmware dispatches
commands to one shared configuration, W5500 adapter, ESC/POS renderer, and TCP
transport. `job.submit` validates semantic v1 work at this boundary; diagnostic
print, feed, and cut commands remain separate. Rendering is separate from
delivery. The transport serializes one payload per socket and closes
deterministically.

When enabled, one station-mode Wi-Fi adapter supplies the MQTT control plane.
A background network thread polls Wi-Fi directly or, when MQTT is enabled, the
MQTT tracer that drives it. The original blocking USB RPC loop remains intact;
the tracer has no coordinator or printer-transport reference. The W5500 remains
dedicated to the directly attached printer on a separate subnet.

```text
Mac/Mosquitto -- home Wi-Fi --> ESP32 Wi-Fi -- MQTT probe/status
USB CLI ---------------------> ESP32 RPC
                               ESP32 W5500 -- direct TCP ESC/POS --> RP326
```

`delivered_to_printer` means all bytes were accepted by the printer-facing TCP
socket. It does not mean paper, head, or cutter success.

## MQTT tracer boundary

The live tracer uses standard MQTT 3.1.1 with QoS 1 and non-retained messages:
`v1/devices/{device_id}/jobs` accepts only a bounded `mqtt_probe`, and
`v1/devices/{device_id}/status` returns its correlated `mqtt_probe_status`.
`mqtt.status` exposes connection failure without touching the printer. It is not
MQTT job submission: it has no queue, ledger, delivery lifecycle, or
`print-job.v1` handling. `commands`, `events`, and `acks` remain future topics.

Future HTTPS/MQTT job ingress must validate the same semantic print-job schema
and reuse the renderer and delivery boundary. A browser or mobile client will
never connect directly to a device over the public internet.

## Order and non-goals

USB ping/info precedes direct W5500 initialization; link state precedes static
address; Wi-Fi status precedes MQTT status; printer probe precedes text; feed
and cut are separate. Queue persistence, MQTT job delivery, backend, web, image
printing, OTA, and production provisioning are out of scope.
