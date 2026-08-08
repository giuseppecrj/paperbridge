# Security

The current trust boundary is local USB plus a private localhost REST/MCP
service, authenticated local MQTT, and the configured printer LAN. USB and HTTP
bound input before parsing, validate the authoritative semantic contract, reject
raw printer bytes/control injection, and use explicit timeouts. Device
`config.show_redacted` hides ignored Wi-Fi and MQTT passwords. No credential
values are committed.

Development passwords live in 1Password. Checked-in `fnox.toml` contains only
remote references, authenticates through 1Password desktop CLI integration, and
injects values into bounded child commands. Stable non-secret machine
configuration, including the Wi-Fi SSID, lives in ignored `.env`. Generated
Device `config.json` is disposable ignored state that necessarily contains the
credentials deployed to the ESP32; regenerate it instead of editing it.

The implemented local API image runs as non-root from a read-only root
filesystem with no capabilities, `no-new-privileges`, no Docker socket, bridged
networking, and host-loopback-only publication. Its Host acceptance mounts a
temporary MQTT password file read-only and checks image history, environment
metadata, arguments, and logs for the value. This is local image evidence, not a
VM or production security claim.

The target container deployment keeps Fnox and 1Password on the deployment
operator's machine. Its checked-in environment file will contain only non-secret
runtime configuration and the mounted credential path. Systemd will decrypt the
MQTT credential for the API runtime, which will read it through
`PAPERBRIDGE_MQTT_PASSWORD_FILE`; no 1Password credential belongs on the VM or in
the container. Issue #28 owns that deployment slice.

The ESP32 uses station-mode Wi-Fi to reach an authenticated local Mosquitto
listener; its direct W5500 printer subnet has no gateway or DNS. Semantic MQTT
jobs are non-retained QoS 1 and bounded to 65,536 bytes after host-side image
preparation. Duplicate suppression is
bounded to one boot, not durable replay protection. Remote cut is device policy
and defaults off. A provisioned development device may opt in with
`PAPERBRIDGE_MQTT_ALLOW_CUT=true`; REST and MCP callers then request a cut by
including the schema's final `{ "type": "cut", "mode": "partial" }` block, not
by supplying an authorization flag.

The service binds to `127.0.0.1` by default and has no public authentication.
The plain Node MCP mount rejects unconfigured Host and Origin values to prevent
DNS rebinding. It allows loopback hosts and loopback development Origins by
default. A private exe.dev deployment must set the non-secret
`PAPERBRIDGE_API_ALLOWED_HOST` hostname and exact HTTPS
`PAPERBRIDGE_API_ALLOWED_ORIGIN`; requests without Origin remain valid for
non-browser MCP clients. The proxy must remain private and provide
infrastructure access control. `/health` reports process liveness, while
`/ready` reports application MQTT readiness and whether submissions are
accepted; neither reports Device or Printer state. Keep the Node service bound
to loopback.
Production credential provisioning/rotation, public broker exposure, public
sender authorization, signed updates, and OTA remain future work and may
trigger ESP-IDF migration.
The EMQX path requires CA verification, SNI, automatic NTP, and the Fnox
`production` overlay. Its bounded no-output TLS scope was physically verified
on 2026-08-07; this is not a production security or reliability claim.
