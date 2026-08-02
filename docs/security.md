# Security

The current trust boundary is local USB plus the configured printer LAN. RPC
still bounds line size, validates envelopes/configuration, rejects raw bytes and
control injection, uses explicit timeouts, and redacts the ignored local Wi-Fi
and MQTT passwords from `config.show_redacted`. No credentials are committed.

The no-output tracer uses ESP32 station-mode Wi-Fi to reach an authenticated
local Mosquitto listener on the home LAN. The direct W5500 printer subnet has no
gateway or DNS. Phase 2 requires a password-protected Wi-Fi network; open WLANs
are not supported. MQTT/TLS, production credential provisioning and rotation,
and public broker exposure are not implemented. Future public clients submit semantic jobs
only to an authenticated HTTPS backend. Device identity, TLS validation, replay
protection, signed updates, and OTA remain future work and may trigger ESP-IDF
migration.
