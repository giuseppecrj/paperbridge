# Security

The current trust boundary is local USB plus a private localhost REST/MCP
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
and defaults off. A provisioned development device may opt in with
`PAPERBRIDGE_MQTT_ALLOW_CUT=true`; REST and MCP callers then request a cut by
including the schema's final `{ "type": "cut", "mode": "partial" }` block, not
by supplying an authorization flag.

The service binds to `127.0.0.1` by default and has no public authentication.
The plain Node MCP mount additionally rejects non-loopback Host and Origin
values to prevent DNS rebinding. Keep it local; a future non-loopback/Tailscale
bind requires an explicit allowed-host/origin policy. MQTT/TLS, production
credential provisioning/rotation, public broker exposure, public sender
authorization, signed updates, and OTA remain future work and may trigger
ESP-IDF migration.
