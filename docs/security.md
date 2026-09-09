# Security

The current trust boundary is local USB plus private localhost or
exe.dev-proxied REST/MCP service access, authenticated MQTT, and the configured
printer LAN. USB and HTTP bound input before parsing, validate the authoritative
semantic contract, reject
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

The checked-in candidate container operator keeps Fnox and 1Password on the
operator machine. Its environment template contains only non-secret runtime
configuration and the mounted credential path. The operator removes the local
secret environment variable before it starts SSH and sends the bytes through
SSH stdin. systemd stores the encrypted blob, decrypts it at service start, and
copies it to a root-only transient `/run` directory so dockerd can bind-mount it
read-only. The API reads `PAPERBRIDGE_MQTT_PASSWORD_FILE`; no 1Password
credential, persistent plaintext file, or Docker secret environment variable is
created. Issue #29 accepted this path on `paperbridge-api` and compared the
actual secret in memory against Docker metadata, process state, image history,
logs, encrypted storage, runtime configuration, and tracked repository files.

The ESP32 uses station-mode Wi-Fi to reach an authenticated local Mosquitto
listener; its direct W5500 printer subnet has no gateway or DNS. Semantic MQTT
jobs are non-retained QoS 1 and bounded to 65,536 bytes after host-side image
preparation. The checked-in MQTT client checks PUBLISH lengths before reading
payloads and rejects retained job deliveries before rendering. Its upstream
version and local changes are recorded with the source; firmware deployment
copies this client with the rest of the application. Duplicate suppression is
bounded to one boot, not durable replay protection. Remote cut is device policy
and defaults off. A provisioned development device may opt in with
`PAPERBRIDGE_MQTT_ALLOW_CUT=true`; REST and MCP callers then request a cut by
including the schema's final `{ "type": "cut", "mode": "partial" }` block, not
by supplying an authorization flag.

The service binds to `127.0.0.1` by default and has no public authentication.
The REST job route and MCP mount reject unconfigured Host and Origin values to
defend against DNS rebinding. They allow loopback hosts and loopback development
Origins by default. A private exe.dev deployment must set the non-secret
`PAPERBRIDGE_API_ALLOWED_HOST` hostname and exact HTTPS
`PAPERBRIDGE_API_ALLOWED_ORIGIN`; requests without Origin remain valid for
non-browser clients. Both routes bound HTTP request bytes before parsing,
including chunked requests; semantic field limits do not replace this transport
limit. The proxy must remain private and provide
infrastructure access control. `/health` reports process liveness, while
`/ready` reports application MQTT readiness and whether submissions are
accepted; neither reports Device or Printer state. Keep the Node service bound
to loopback.

Issue #30 records the completed private route cutover; any later token, route,
or DNS change requires separate Owner authorization. Public broker
exposure, public sender authorization, signed updates, and OTA remain future
work and may trigger ESP-IDF migration.

The EMQX path requires CA verification, SNI, automatic NTP, and the Fnox
`production` overlay. Its bounded no-output TLS scope was physically verified
on 2026-08-07; this is not a production security or reliability claim.

## Publication checks

Run `just secrets-scan` before sharing repository history. CI runs the same
pinned Gitleaks scanner against the full fetched Git history, with findings
redacted. The check does not read ignored local credentials. Pattern detection
cannot prove that custom or low-entropy credentials are absent; review issues,
comments, Actions logs, and attachments separately before changing repository
visibility.

Enable GitHub secret scanning and push protection when the repository is
eligible. GitHub rejected enablement for this private repository during the
2026-09-08 security work, so the local and CI scanner is the available guard;
it does not block a secret before it reaches GitHub. Source publication must
not change the private API access boundary.

Production hostnames, network observations, and 1Password reference names are
operational metadata, not credentials. Removing them from the current files
does not remove their copies in history, issues, or logs. Any historical cleanup
requires a separately scoped review and authorization.

## Broker and Device rollout

Local tests are not evidence that the deployed Device or broker has changed.
Before deploying MQTT receive hardening, follow the normal explicit-port,
force-copy firmware workflow and record its hardware acceptance separately.

Broker policy should deny retained publication to job topics, bound MQTT
packet sizes, and give the API and Device separate credentials with directional
topic permissions. The API publishes jobs/probes and subscribes to their
results; the Device has the inverse permissions. A retained-message receive
guard cannot distinguish a live MQTT 3.1.1 publication that the broker forwards
with RETAIN cleared. Broker enforcement therefore remains necessary.

Provisioning separate production principals, rotating credentials, changing
broker policy, and deploying the Device require an approved rollout with exact
targets and Owner authorization. No such production changes are implied by the
host-test results or the repository visibility setting.
