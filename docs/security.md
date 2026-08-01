# Security

The current trust boundary is local USB plus the configured printer LAN. RPC
still bounds line size, validates envelopes/configuration, rejects raw bytes and
control injection, uses explicit timeouts, and hides future secrets behind a
redaction seam. No credentials are needed or committed.

Future public clients submit semantic jobs only to an authenticated HTTPS
backend. Devices initiate outbound MQTT over TLS; no public inbound device port
or browser-to-device connection is planned. Device identity, credential storage,
rotation, TLS validation, replay protection, signed updates, and OTA are future
work and may trigger ESP-IDF migration.
