# Device CLI

`paperbridge` discovers likely macOS USB serial devices and sends application
newline-delimited JSON. Set `PAPERBRIDGE_PORT` or pass global `--port`; ambiguous
port lists are never resolved silently.

Examples:

```sh
paperbridge ports list
paperbridge --port /dev/cu.usbmodem101 device ping
paperbridge --json --port /dev/cu.usbmodem101 device info
paperbridge --port /dev/cu.usbmodem101 \
  job submit packages/protocol/fixtures/print-job-v1/valid-text-feed.json
```

`job submit` sends semantic JSON only. Its optional `--allow-cut` authorizes a
cut block; it does not enable raw ESC/POS. `--request-id` selects the serial
transport correlation ID, while the returned `job_id` comes from the submitted
semantic job.
