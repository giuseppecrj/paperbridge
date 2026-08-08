# Fnox and 1Password development secrets

Research performed 2026-08-02 against Fnox 1.31.1 and 1Password CLI 2.35.0,
then updated 2026-08-07 after the production deployment boundary was accepted.
These are operator-workflow findings, not proof that a deployment occurred.

## Decision

Paperbridge uses a checked-in root `fnox.toml` as its secret-name contract. The
file contains 1Password references only, never secret values. Fnox authenticates
through 1Password desktop CLI integration and injects values only into a child
command:

```text
1Password Agent vault -> fnox project mapping -> `fnox exec` -> Paperbridge process
```

The mappings are:

- default local `PAPERBRIDGE_MQTT_PASSWORD` ->
  `op://Agent/paperbridge-mqtt-password/password`;
- Device `PAPERBRIDGE_WIFI_PASSWORD` ->
  `op://Agent/home-router/password`; and
- production `PAPERBRIDGE_MQTT_PASSWORD` ->
  `op://Agent/paperbridge-emqx-token/password`.

The default secrets represent the local Host. The `device` profile inherits the
local MQTT password and adds only the Wi-Fi password. The `production` profile
replaces the local MQTT password. A Device using the production broker composes
`device,production`.

Stable non-secret machine settings belong in ignored `.env`, based on
`.env.example`. These include the serial port, addresses, MQTT username, Device
identity, and Wi-Fi SSID. Generated `firmware/micropython/config.json` is
disposable derived state that contains deployed credentials; regenerate it
through `just configure-device` instead of editing it manually.

`just` is the operator interface. Recipes set `FNOX_CONFIG_DIR=/nonexistent` so
no global Fnox file is loaded and use `--no-daemon` for direct resolution without
shared per-user cache state. Default inheritance is intentional: local Host
commands use the default secrets, Device commands select `device`, and
production commands select `production`.

`just lint` parses the Fnox configuration without resolving secrets. Live checks
are explicit and print no values:

```sh
just secrets-check
just production-secrets-check
```

Neither live check is a test-suite prerequisite or a reason to grant CI access
to 1Password.

## Why project-local configuration

Fnox loads its global configuration and then walks project `fnox.toml` files from
parents to the current directory. The checked-in project file owns the
Paperbridge names and 1Password references. `root = true` prevents unrelated
parent-project configuration from being merged. `FNOX_CONFIG_DIR=/nonexistent`
excludes unrelated global state.

Fnox 1.31.1 supports `env = "exec"`, which keeps mapped secrets out of the
interactive shell and injects them only into `fnox exec` children. Fnox 1.29.0
does not accept that setting, so the repository pins 1.31.1. Product secrets use
`if_missing = "error"`, so a command does not continue with a missing credential.

## 1Password authentication

Enable the 1Password desktop application's CLI integration, unlock the app, and
authenticate when `op` prompts. Do not pass secret values as command-line
arguments because they can appear in shell history and process listings.

## Deployment boundary

Fnox remains an operator-side provisioning tool. Local commands receive
`PAPERBRIDGE_MQTT_PASSWORD` directly. The candidate container operator captures
and removes that environment variable before it starts SSH, then sends the bytes
through SSH stdin for `systemd-creds` encryption. The VM and container do not
install Fnox or receive 1Password credentials.

The checked-in deployment environment template contains only non-secret runtime
configuration and
`PAPERBRIDGE_MQTT_PASSWORD_FILE=/run/secrets/mqtt-password`. That file setting is
deployment configuration and does not belong in local `.env`. systemd decrypts
the credential at service start; a transient root-only `/run` copy lets dockerd
mount it read-only into the container and is removed when the service stops.

## Primary sources

- Fnox configuration hierarchy and `root` behavior:
  <https://fnox.jdx.dev/reference/configuration>
- Fnox profiles and default inheritance:
  <https://fnox.jdx.dev/guide/profiles>
- Fnox 1Password provider and `op://` references:
  <https://fnox.jdx.dev/providers/1password>
- Fnox resolution and `fnox exec` behavior:
  <https://fnox.jdx.dev/guide/how-it-works>
- 1Password secret-reference syntax:
  <https://developer.1password.com/docs/cli/secret-reference-syntax>
- 1Password CLI desktop-app authentication:
  <https://developer.1password.com/docs/cli/get-started/>
