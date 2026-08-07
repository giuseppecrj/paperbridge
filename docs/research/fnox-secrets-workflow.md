# Fnox and 1Password development secrets

Research performed 2026-08-02 against Fnox 1.31.1 and 1Password CLI 2.35.0.
These are development-workflow findings, not a production provisioning design.

## Decision

Paperbridge uses a checked-in root `fnox.toml` as the development secret-name
contract. The file contains 1Password references only, never secret values.
Fnox resolves those references and injects values only into a child command:

```text
1Password Agent vault -> fnox project mapping -> `fnox exec` -> Paperbridge process
```

The machine-local 1Password service-account token remains an optional bootstrap
credential in the OS keychain. It is marked `env = false`, so Paperbridge child
processes receive the requested Paperbridge secrets but not the bootstrap token.
Developers using 1Password desktop-app integration may omit the service-account
token.

The current mappings are:

- `PAPERBRIDGE_WIFI_SSID` -> `op://Agent/home-router/name`
- `PAPERBRIDGE_WIFI_PASSWORD` -> `op://Agent/home-router/password`
- local `PAPERBRIDGE_MQTT_PASSWORD` ->
  `op://Agent/paperbridge-mqtt-password/password`
- production `PAPERBRIDGE_MQTT_PASSWORD` ->
  `op://Agent/paperbridge-emqx-token/password`

The `host` profile exposes only the local MQTT password. The `device` profile
exposes that password plus Wi-Fi name/password. The `production` profile
exposes only the managed-broker MQTT password and is composed with `host` for
the private production service. Recipes set `FNOX_CONFIG_DIR` to an
empty location so no global Fnox file is loaded, use `--no-defaults` to select
only the named project profile, and use `--no-daemon` for direct resolution
without shared per-user cache state. Non-secret, machine-local settings such
as serial port and broker address belong
in ignored `.env`, based on `.env.example`. MQTT username and device identity
also remain ordinary configuration, not secrets.

`just` is the operator interface. Recipes that need secrets invoke Fnox; direct
`paperbridge` CLI commands remain available for parameterized USB diagnostics.
MCP is live product ingress at `/mcp`, not an operator diagnostic or substitute
for the USB CLI.

## Why project-local configuration

Fnox loads the global config first and then walks project `fnox.toml` files from
parents to the current directory. A checked-in project file therefore owns the
Paperbridge names and 1Password references. `root = true` prevents unrelated
parent-project configuration from being merged. Fnox normally loads its global
file even with `root = true`, so Paperbridge recipes follow Fnox's documented
isolation mechanism: point `FNOX_CONFIG_DIR` at an empty location and select an
explicit profile with `--no-defaults`. The optional 1Password service-account
token is still resolved directly from the OS keychain by the project mapping.

Fnox 1.31.1 supports `env = "exec"`, which keeps mapped secrets out of the
interactive shell and injects them only into `fnox exec` children. Fnox 1.29.0
does not accept that setting, so the repository pins 1.31.1. The optional
`OP_SERVICE_ACCOUNT_TOKEN` mapping has `env = false`: Fnox may use it to reach
1Password, but the launched Paperbridge process cannot read it.

## 1Password authentication

For interactive local development, enable the 1Password desktop application's
CLI integration and authenticate when `op` prompts. For unattended local
operation, use a least-privilege service account scoped to the development
vault. Store `OP_SERVICE_ACCOUNT_TOKEN` in the OS keychain, not this repository.
Do not pass secret values as command-line arguments: Fnox documents that they
can appear in shell history and process listings.

## Future Cloudflare boundary

Cloudflare will be a separate runtime secret store. Fnox remains a local
operator tool: it may supply a value to a future deployment command, but
Cloudflare receives and stores the runtime binding. Keep stable
`PAPERBRIDGE_*` names where the meaning is unchanged; do not make a Worker depend
on Fnox or 1Password at runtime. Device Wi-Fi credentials are provisioning data
and should not become Cloudflare Worker bindings.

## Primary sources

- Fnox configuration hierarchy, project/local files, and `root` behavior:
  <https://fnox.jdx.dev/reference/configuration>
- Fnox 1Password provider and `op://` references:
  <https://fnox.jdx.dev/providers/1password>
- Fnox resolution and `fnox exec` behavior:
  <https://fnox.jdx.dev/guide/how-it-works>
- 1Password secret-reference syntax:
  <https://developer.1password.com/docs/cli/secret-reference-syntax>
- 1Password CLI desktop-app authentication:
  <https://developer.1password.com/docs/cli/get-started/>
