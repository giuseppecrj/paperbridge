# Local configuration generator

For the current networked development device, copy `.env.example` to ignored
`.env`, set this machine's non-secret addresses, authenticate 1Password, then
run:

```sh
just secrets-check
just configure-device
```

`just configure-device` uses the Fnox `device` profile to inject Wi-Fi and MQTT
values into `generate_device_config.py --from-env`. The generator writes ignored
`firmware/micropython/config.json`; passwords never appear in command arguments.
The generated file necessarily contains device credentials, so never commit or
log it.

The original explicit flags remain available for non-secret Ethernet-only
configuration:

```sh
uv run python tools/provisioning/generate_device_config.py \
  --device-id paperbridge-dev-001 \
  --printer-host 192.168.4.87 \
  --output firmware/micropython/config.json
```

### Remote cut opt-in

`cut` is part of the `print-job.v1` schema and MCP/REST content shape. Put it
last in the receipt content:

```json
{ "type": "cut", "mode": "partial" }
```

Remote cuts are disabled by default. To opt in a development device, set the
non-secret flag in ignored `.env`:

```sh
PAPERBRIDGE_MQTT_ALLOW_CUT=true
```

Then regenerate and deploy the device configuration:

```sh
just secrets-check
just configure-device
PORT=/dev/cu.usbmodem101 just deploy
```

The flag is device policy, not a caller-supplied authorization field. Leave it
`false` when remote senders must not be able to activate the cutter. Local USB
jobs use the separate explicit `--allow-cut` authorization.

Production device identity and credential provisioning are intentionally not
implemented.
