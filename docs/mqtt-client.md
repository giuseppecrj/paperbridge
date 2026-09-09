# Firmware MQTT receive boundary

`firmware/micropython/src/mqtt_client.py` is the checked-in MicroPython client
used by `MqttTracer`. It is derived from micropython-lib `umqtt.simple` 1.8.0
at commit `5e49b1bd41d312d9d2a8e4f19d7bd6a918896abc`:

- [Upstream source](https://github.com/micropython/micropython-lib/blob/5e49b1bd41d312d9d2a8e4f19d7bd6a918896abc/micropython/umqtt.simple/umqtt/simple.py)
- Original source SHA-256:
  `3cfd101ef774e0c6f9543425650ddc36168a7bbf4b8b8b71667e27023dfd951f`
- [Upstream license](https://github.com/micropython/micropython-lib/blob/5e49b1bd41d312d9d2a8e4f19d7bd6a918896abc/LICENSE)

The MIT notice is retained in the deployed source. Paperbridge adds bounded
PUBLISH decoding, retain metadata in callbacks, malformed-packet rejection,
and socket closure on receive failure. It also removes unused debug imports
and uses an instance-local TLS options dictionary. There is no runtime download
or dependency on a separately installed `umqtt.simple` version. Updates must
preserve these guards and pass the wire-level tests in
`firmware/micropython/tests/test_mqtt.py`.

## Bounds and retention

Before reading a topic or payload, the client validates the MQTT Remaining
Length encoding (at most four bytes), the topic length, and the available space
for the QoS packet ID. The maximum Remaining Length is
`mqtt.max_message_bytes + longest subscribed topic length + 4`. A second check
limits the payload itself to `mqtt.max_message_bytes` even for a shorter topic.
Malformed or oversized packets close the connection; the existing retry
interval controls reconnection. These bounds constrain individual reads and
payloads, not total heap usage or traffic rate.

The callback carries the PUBLISH RETAIN flag. The adapter rejects retained
probes and print jobs before JSON parsing or delivery, without recording a
completed job ID. Valid bounded retained messages are acknowledged at QoS 1 but
produce no job result. This prevents a stored retained job from replaying when
a Device reconnects or reboots. MQTT 3.1.1 brokers clear RETAIN for forwarding
a new publication to an already subscribed client, so this check cannot detect
all publishers that send with retention enabled.
See [MQTT 3.1.1 section 3.3.1.3](https://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html)
for the broker's RETAIN forwarding rules.

Separate API and Device broker principals, direction-specific topic ACLs, a
broker packet-size limit, and a policy rejecting retained command/job
publications remain deployment work. Confirm the active broker policy and clear
existing retained command/job records only under an approved issue and explicit
Owner authorization. The source change does not update broker policy.

## Deployment and evidence

The default factory imports `.mqtt_client` from the firmware package. The
existing `tools/firmware/deploy.py` includes it in its individual `.py` force-copy
list; no recursive copy or separate library installation is needed. Deploying
and resetting the Device still require explicit hardware authorization and the
usual configuration and USB-port checks.

Host tests exercise the checked-in decoder against fake sockets and the real
job service/renderer with a recording printer transport. They cover retained
replay across fresh Device instances, normal job delivery afterward, malformed
lengths, oversized payloads before allocation, maximum-size payload acceptance,
and QoS 0/1 handshakes. The existing Mosquitto integration tests use a Paho
adapter and do not establish MicroPython socket/TLS behavior. The new receive
guards have not been deployed to or physically verified on the purchased board.
The earlier hardware observations do not establish their behavior.
