# Architecture

## Immediate system

The host CLI speaks newline-delimited JSON over USB serial. Firmware dispatches
commands to one shared configuration, W5500 adapter, ESC/POS renderer, and TCP
transport. Rendering is separate from delivery. The transport serializes one
payload per socket and closes deterministically.

```text
paperbridge CLI -> serial RPC -> command router -> print coordinator
                                             |-> ESC/POS renderer
                                             `-> TCP printer transport -> RP326
```

`delivered_to_printer` means all bytes were accepted by the printer-facing TCP
socket. It does not mean paper, head, or cutter success.

## Future contract boundary

Future HTTPS/MQTT ingress must validate the same `print-job.v1` schema and reuse
the renderer, queue, coordinator, status vocabulary, and ledger. A browser or
mobile client will never connect directly to a device over the public internet.
Future topics are `v1/devices/{device_id}/{jobs,commands,status,events,acks}`.
They are contracts only; no cloud system is implemented.

## Order and non-goals

USB ping/info precedes W5500 initialization; link state precedes static address;
probe precedes text; feed and cut are separate. Queue persistence, Wi-Fi, MQTT,
backend, web, image printing, OTA, and production provisioning are out of scope.
