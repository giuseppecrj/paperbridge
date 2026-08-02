# Local Mosquitto tracer

Install Mosquitto outside this repository. Copy
`mosquitto.local.example.conf` to the ignored `mosquitto.local.conf`, replace the
Mac's wired-LAN address and password-file path, then create the credential:

```sh
mosquitto_passwd -c /absolute/path/to/paperbridge-mosquitto.passwd paperbridge-dev-001
mosquitto -c tools/mosquitto/mosquitto.local.conf
```

The broker rejects anonymous clients, has no retained jobs, and must bind only
to the local wired LAN. It is not exposed through Tailscale.
