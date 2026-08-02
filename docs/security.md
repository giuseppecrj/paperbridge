# Security

The current trust boundary is local USB plus the configured printer LAN. RPC
still bounds line size, validates envelopes/configuration, rejects raw bytes and
control injection, uses explicit timeouts, and redacts the ignored local Wi-Fi
and MQTT passwords from `config.show_redacted`. No credential values are
committed.

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

The no-output tracer uses ESP32 station-mode Wi-Fi to reach an authenticated
local Mosquitto listener on the home LAN. The direct W5500 printer subnet has no
gateway or DNS. Phase 2 requires a password-protected Wi-Fi network; open WLANs
are not supported. MQTT/TLS, production credential provisioning and rotation,
and public broker exposure are not implemented. Future public clients submit
semantic jobs only to an authenticated HTTPS backend. Device identity, TLS
validation, replay
protection, signed updates, and OTA remain future work and may trigger ESP-IDF
migration.
