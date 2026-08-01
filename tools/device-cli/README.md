# Device CLI

`paperbridge` discovers likely macOS USB serial devices and sends application
newline-delimited JSON. Set `PAPERBRIDGE_PORT` or pass global `--port`; ambiguous
port lists are never resolved silently.

Examples:

```sh
paperbridge ports list
paperbridge --port /dev/cu.usbmodem101 device ping
paperbridge --json --port /dev/cu.usbmodem101 device info
```
