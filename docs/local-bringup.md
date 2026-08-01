# Local bring-up

Follow the development order; do not skip forward because later code exists.

1. `mise install && just bootstrap && just test`.
2. Connect a known data cable and run `just ports`.
3. Inspect board revision, download/checksum/flash the selected MicroPython image,
   open the REPL, then run `PORT=... just verify-board`.
4. Create ignored `firmware/micropython/config.json` from the example and deploy.
5. Run `device ping`, `device info`, memory, and reset-cause RPCs.
6. Power the RP326 independently, print its self-test, and record endpoint facts.
7. Connect ESP32 Ethernet to printer, inspect LEDs, run `ethernet init`,
   `ethernet link-status`, then `ethernet configure-static`.
8. Run `printer probe`; a TCP connect proves endpoint reachability only.
9. Run text-only print, then feed, then explicit cut last.
10. Power-cycle and disconnect/reconnect each device and repeat.

If direct link has no LEDs, use a crossover cable or a small switch/router before
changing firmware. See `network-topology.md` and `troubleshooting.md`.
