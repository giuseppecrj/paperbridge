# Security

The current trust boundary is local USB plus a private localhost/Tailscale REST
service, authenticated local MQTT, and the configured printer LAN. USB and HTTP
bound input before parsing, validate the authoritative semantic contract, reject
raw printer bytes/control injection, and use explicit timeouts. Device
`config.show_redacted` hides ignored Wi-Fi and MQTT passwords. No credential
values are committed.

Development values live in 1Password. Checked-in `fnox.toml` contains only
remote references and injects values into bounded child commands; the optional
1Password service-account bootstrap remains in the OS keychain and is not
injected into Paperbridge processes. Non-secret machine configuration lives in
ignored `.env`; generated device `config.json` is also ignored but necessarily
contains the credentials deployed to the ESP32.

A future Cloudflare deployment will store runtime bindings in Cloudflare's
secret manager. Fnox may supply values to a deployment command, but Workers must
not depend on Fnox or 1Password at runtime. Keep `PAPERBRIDGE_*` names stable
where their meaning survives the migration; device Wi-Fi credentials remain
provisioning data, not Worker bindings.

The ESP32 uses station-mode Wi-Fi to reach an authenticated local Mosquitto
listener; its direct W5500 printer subnet has no gateway or DNS. Semantic MQTT
jobs are non-retained QoS 1 and bounded to 1,024 bytes. Duplicate suppression is
bounded to one boot, not durable replay protection. Remote cut is device policy
and defaults off; REST callers cannot grant it.

The REST service binds to `127.0.0.1` by default and has no public authentication.
Keep it local or behind the approved Tailscale boundary. MQTT/TLS, production
credential provisioning/rotation, public broker exposure, public sender
authorization, signed updates, and OTA remain future work and may trigger
ESP-IDF migration.
