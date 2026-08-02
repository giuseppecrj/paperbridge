# Architecture

## Immediate system

The host CLI speaks newline-delimited JSON over USB serial. Firmware dispatches
commands to one shared configuration, W5500 adapter, ESC/POS renderer, and TCP
transport. `job.submit` validates semantic v1 work at
this boundary; diagnostic print, feed, and cut commands remain separate.
Rendering is separate from delivery. The transport serializes one payload per
socket and closes deterministically. When enabled, one MQTT tracer shares the
W5500 adapter and cooperatively polls alongside USB RPC; it has no coordinator
or printer-transport reference.

```text
paperbridge CLI -> serial RPC -> command router -> print coordinator
                                             |-> ESC/POS renderer
                                             `-> TCP printer transport -> RP326
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

USB ping/info precedes W5500 initialization; link state precedes static address;
the no-output tracer can connect only after that link is ready; probe precedes
text; feed and cut are separate. Queue persistence, Wi-Fi, MQTT job delivery,
backend, web, image printing, OTA, and production provisioning are out of scope.
