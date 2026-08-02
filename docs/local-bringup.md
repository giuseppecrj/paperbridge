# Local bring-up

Follow the development order; do not skip forward because later code exists.
The complete path through explicit partial cut was physically verified on
2026-08-01. Controlled power-cycle acceptance, isolated reconnect/recovery, and
observable cover-open/paper-out behavior passed on 2026-08-02. The 72-hour soak
remains, so repeat this sequence rather than treating the observations as a
production reliability claim.

1. `mise install && just bootstrap && just test`.
2. Copy `.env.example` to ignored `.env`, set this machine's non-secret values,
   unlock 1Password, and run `just secrets-check`.
3. Connect a known data cable and run `just ports`.
4. Inspect board revision, download/checksum/flash the selected MicroPython image,
   open the REPL, then run `PORT=... just verify-board`.
5. Run `just configure-device`, inspect only `config show`'s redacted result, and
   deploy to the explicitly selected port.
6. Run `device ping`, `device info`, memory, and reset-cause RPCs.
7. For the no-output control plane, check `wifi status`, then `mqtt status`, then
   run `just mqtt-probe`.
8. Power the RP326 independently, print its self-test, and record endpoint facts.
9. Connect ESP32 Ethernet to printer, inspect the single green indicator, run
   `ethernet init`, `ethernet link-status`, then `ethernet configure-static`.
10. Run `printer probe`; a TCP connect proves endpoint reachability only.
11. Run text-only print, then feed, then explicit cut last.
12. Power-cycle and disconnect/reconnect each device and repeat.
13. Optional repeatable HIL (not part of `just test`):

```sh
PORT=/dev/cu.usbmodem101 just test-hardware-smoke
```

Expected: ping/info/init/static×2/bounded link wait/probe only; no paper motion.

```sh
PORT=/dev/cu.usbmodem101 just test-hardware-network-recovery
```

Expected: a no-output flow that uses guarded device Wi-Fi disconnect/reconnect
RPCs to observe Wi-Fi/MQTT down and back while W5500 remains usable, then
interactively observes W5500/printer down and back while Wi-Fi/MQTT remains
usable. The harness, not the operator confirmation, decides whether each bounded
transition passed. Fnox supplies the MQTT password, and one ignored evidence file
records the complete run.

```sh
PORT=/dev/cu.usbmodem101 just test-hardware-acceptance
```

Expected: smoke, then interactive text → feed → exact `CUT` token → cut, with
operator confirmation at each physical step. Evidence lands in
`captures/hardware/`.

```sh
caffeinate -dimsu -- env PORT=/dev/cu.usbmodem101 just test-hardware-soak
```

Expected: 72 hours of ping/info/link/probe sampling without paper output. See
`testing.md` before starting it.

If the direct link indicator stays dark, use a crossover cable or a small
switch/router before changing firmware. See `network-topology.md` and
`troubleshooting.md`.
