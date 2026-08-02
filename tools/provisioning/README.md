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

Production device identity and credential provisioning are intentionally not
implemented.
