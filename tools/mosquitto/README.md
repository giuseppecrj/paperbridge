# Local Mosquitto tracer

Install Mosquitto outside this repository. Copy
`mosquitto.local.example.conf` to ignored `mosquitto.local.conf`, replace the
Mac's home-LAN address and password-file path, then initialize the broker's
password file interactively:

```sh
mkdir -p "$HOME/.config/paperbridge"
mosquitto_passwd -c \
  "$HOME/.config/paperbridge/mosquitto.passwd" \
  paperbridge-dev-001
mosquitto -c tools/mosquitto/mosquitto.local.conf
```

Use the password stored in the 1Password
`Agent/paperbridge-mqtt-password/password` field at the hidden prompts. Do not use
`mosquitto_passwd -b`: batch mode places the password in process arguments. To
rotate an existing entry, omit `-c`; `-c` overwrites the file.

The checked-in `fnox.toml` maps that same 1Password field to
`PAPERBRIDGE_MQTT_PASSWORD`. After setting non-secret broker values in ignored
`.env`, verify and run the no-output host probe with:

```sh
just secrets-check
just mqtt-probe
```

The broker rejects anonymous clients, has no retained jobs, and must bind only
to the local home LAN. It is not exposed through Tailscale.
