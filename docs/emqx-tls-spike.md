# EMQX MQTT/TLS spike

Status: implemented, host-tested, and physically verified for the bounded
no-output scope on 2026-08-07 as `emqx-tls-spike-945ac7ad7d78`.

## Scope

The optional path keeps MQTT 3.1.1, QoS 1, non-retained jobs and results, and
the direct W5500 printer path. Local Mosquitto remains plain MQTT by default.
When `mqtt.tls.enabled` is true, firmware requires one ASCII PEM CA certificate,
a DNS SNI hostname, `ssl.CERT_REQUIRED`, and a valid device clock. After Wi-Fi
connects, an unready clock is synchronized with MicroPython `ntptime` before the
TLS client is created. The Node job client and no-output tracer use `mqtts`, the
same CA, SNI, and `rejectUnauthorized: true`.

The purchased ESP32-S3 physically connected to EMQX Serverless on port 8883 with
the downloaded DigiCert Global Root G2 CA and SNI. Automatic NTP succeeded. A
correlated no-output probe returned `ok`; a non-retained QoS 1 payload of 65,000
bytes returned `rejected` / `INVALID_PRINT_JOB` before rendering. W5500 recovered
to `192.168.4.50/24`, the printer endpoint was reachable, and MQTT/TLS remained
connected. Free heap moved from 8,197,024 bytes before the spike to 7,922,768
after the large payload, then recovered to 8,184,624. No print, feed, cut, flash,
or erase occurred.

## Configuration

The bounded spike used:

- EMQX deployment `deployment-t1b28b1a` at
  `t1b28b1a.ala.us-east-1.emqxsl.com:8883`;
- device and username `paperbridge-dev-001`;
- the downloaded PEM CA file supplied by EMQX; and
- the checked-in `production` Fnox profile, which resolves only the EMQX MQTT
  password and keeps it separate from local-Mosquitto profiles.

Select only the overlays needed by each process:

```sh
# Host probe/API process: replace the default local password with EMQX.
fnox --no-daemon -P production exec -- <host-command>

# Device configuration: add Wi-Fi password and replace the MQTT password.
fnox --no-daemon -P device,production exec -- <device-command>
```

The `production` overlay replaces the default `PAPERBRIDGE_MQTT_PASSWORD`.
Paperbridge recipes also set `FNOX_CONFIG_DIR=/nonexistent` to exclude unrelated
global Fnox state.

## Evidence and remaining gates

Ignored evidence file
`captures/hardware/emqx-tls-spike-945ac7ad7d78.json` records the non-secret
endpoint, CA fingerprint, probe and invalid-job IDs, memory values, W5500 state,
and safety results.

Still unverified:

- Wi-Fi loss and MQTT/TLS reconnect;
- QoS redelivery duplicate behavior over EMQX after reconnect; and
- long-duration MQTT/TLS and W5500 coexistence.

The later #15 cloud acceptance separately verified one valid semantic job and
physical paper observation through the private MCP → exe.dev → EMQX path. It
must not be attributed to this bounded no-output spike.

A TLS memory failure, unreliable coexistence, or normal-fault reset remains an
ESP-IDF migration signal under ADR 0001. A successful socket write remains
`delivered_to_printer`, not proof that paper emerged.

## Source evidence

- [EMQX ESP32 MicroPython guide][emqx-guide]: Serverless requires TLS on port
  8883 and documents `ssl=True`, `ssl_params`, CA data, `CERT_REQUIRED`, and SNI.
- [MicroPython 1.28 SSL documentation][micropython-ssl]: `CERT_REQUIRED` needs
  correct device time. Client `server_hostname` enables certificate hostname
  validation and SNI.

The EMQX guide uses PEM CA data with `umqtt.simple`; the generic MicroPython SSL
reference describes `cadata` as bytes and documents a single DER certificate.
The exact EMQX PEM guide path was physically verified on the selected
MicroPython 1.28 firmware and purchased ESP32-S3.

[emqx-guide]: https://docs.emqx.com/en/cloud/latest/connect_to_deployments/esp32_with_micropython.html
[micropython-ssl]: https://docs.micropython.org/en/v1.28.0/library/ssl.html
