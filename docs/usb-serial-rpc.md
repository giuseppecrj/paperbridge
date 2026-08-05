# USB serial RPC

Transport is UTF-8 newline-delimited JSON: one request and one response per
line. Requests require `type=request`, `request_id`, `command`, and object
`params`; responses echo the ID. Newly generated configuration permits request
lines up to 65,536 bytes so one maximum prepared raster plus its RPC envelope
fits. Existing smaller configured bounds remain valid. Malformed, non-object,
oversized, and unsupported requests return stable errors and do not reset the
device.

Responses use `type=response`; logs use `type=log`, so startup noise or logs are
not mistaken for correlated responses. The host ignores non-response lines and
responses for other IDs. Binary printer data is not accepted over RPC.

Live commands are:

- `system.ping`, `system.info`, `system.memory`, `system.reset_cause`, and
  `system.reboot`
- `config.show_redacted`
- `wifi.status`, which reports the station-mode control-plane connection
- `wifi.disconnect` and `wifi.reconnect`, guarded station-control diagnostics
  that require literal JSON boolean `confirm: true`; their requests are applied
  by the network polling thread, not the USB handler
- `mqtt.status`, which reports the optional tracer's connection state and last
  error without contacting the printer
- `ethernet.initialize`, guarded `ethernet.reconnect`, `ethernet.status`,
  `ethernet.link_status`, and `ethernet.configure_static`
- `printer.endpoint`, `printer.probe`, `printer.print_test`,
  `printer.feed_test`, and `printer.cut_test`
- `job.submit` with `params.job` containing a semantic `print-job.v1` and an
  optional literal `allow_cut: true` for cut blocks

`printer.cut_test`, `wifi.disconnect`, `wifi.reconnect`, and
`ethernet.reconnect` require literal JSON boolean `confirm: true`. Ethernet
reconnect synchronously stops and restarts the existing MicroPython LAN singleton
and reapplies static configuration; callers must still verify link status or TCP
reachability. Wi-Fi-control replies acknowledge the requested intent; the
network poller changes the live interface asynchronously, so the recovery HIL
waits for its bounded status transition. Wi-Fi controls never
contact the printer; they are used by the explicit no-output recovery HIL only.
`job.submit` checks the
configured `device_id` before printer delivery and returns the semantic `job_id`;
its serial `request_id`
continues to provide bounded response replay. `wifi.status` and `mqtt.status`
report disabled when their adapters are not configured. `system.reboot`
schedules reset after returning its response. Queue, config reload, fixture
aliases, and durable
job-id deduplication are not live RPC commands.

Application RPC and MicroPython deployment are intentionally separate:
`mpremote` manages files/REPL; `paperbridge` manages device behavior.
