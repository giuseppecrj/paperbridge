# Printer bring-up

1. Power the RP326 only from its 24 V adapter.
2. Produce a self-test receipt and record IP, TCP port, firmware, paper width,
   and interfaces in `hardware.md`.
3. Probe TCP from the ESP32. Connection success is `reachable`, not printed.
4. Send ESC/POS initialize, printable ASCII, and three line feeds. No cut.
5. Test feed separately.
6. Only then run `printer cut-test --confirm` and record the exact working bytes.

Text rejects control bytes and non-ASCII rather than silently replacing them.
The candidate partial-cut sequence is `1d 56 01`; it is not verified on the
purchased RP326 and may require a printer profile change. There is no bitmap,
Unicode, arbitrary code-page, or status-query support yet.
