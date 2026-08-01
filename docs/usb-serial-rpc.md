# USB serial RPC

Transport is UTF-8 newline-delimited JSON: one request and one response per
line. Requests require `type=request`, `request_id`, `command`, and object
`params`; responses echo the ID. The configured maximum request line is 4096
bytes. Malformed, non-object, oversized, and unsupported requests return stable
errors and do not reset the device.

Responses use `type=response`; logs use `type=log`, so startup noise or logs are
not mistaken for correlated responses. The host ignores non-response lines and
responses for other IDs. Binary printer data is not accepted over RPC.

Initial commands are the `system.*`, `config.*`, `ethernet.*`, `printer.*`, and
`queue.status` commands listed in the schemas and CLI. `printer.cut_test`
requires literal JSON boolean `confirm: true`; it never runs at boot or in unit
tests. `system.reboot` schedules reset after returning its response.

Application RPC and MicroPython deployment are intentionally separate:
`mpremote` manages files/REPL; `paperbridge` manages device behavior.
