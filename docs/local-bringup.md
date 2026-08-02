# Local bring-up

Follow the development order; do not skip forward because later code exists.
The complete path through explicit partial cut was physically verified on
2026-08-01. Controlled power-cycle acceptance, isolated reconnect/recovery, and
observable cover-open/paper-out behavior passed on 2026-08-02. The 72-hour soak
remains, so repeat this sequence rather than treating the observations as a
production reliability claim.

1. `mise install && just bootstrap && just test`.
2. Connect a known data cable and run `just ports`.
3. Inspect board revision, download/checksum/flash the selected MicroPython image,
   open the REPL, then run `PORT=... just verify-board`.
4. Create ignored `firmware/micropython/config.json` from the example and deploy.
5. Run `device ping`, `device info`, memory, and reset-cause RPCs.
6. Power the RP326 independently, print its self-test, and record endpoint facts.
7. Connect ESP32 Ethernet to printer, inspect the single green indicator, run
   `ethernet init`, `ethernet link-status`, then `ethernet configure-static`.
8. Run `printer probe`; a TCP connect proves endpoint reachability only.
9. Run text-only print, then feed, then explicit cut last.
10. Power-cycle and disconnect/reconnect each device and repeat.
11. Optional repeatable HIL (not part of `just test`):

```sh
PORT=/dev/cu.usbmodem101 just test-hardware-smoke
```

Expected: ping/info/init/static×2/bounded link wait/probe only; no paper motion.

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
