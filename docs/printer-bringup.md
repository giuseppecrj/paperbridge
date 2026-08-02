# Printer bring-up

1. Power the RP326 only from its 24 V adapter.
2. Produce a self-test receipt and record IP, TCP port, firmware, paper width,
   and interfaces in `hardware.md`.
3. Probe TCP from the ESP32. Connection success is `reachable`, not printed.
4. Send ESC/POS initialize, printable ASCII, and three line feeds. No cut.
5. Test feed separately.
6. Only then run `printer cut-test --confirm` and record the exact working bytes.

Text rejects control bytes and non-ASCII rather than silently replacing them.
On 2026-08-01 the purchased RP326 accepted text and feed at
`192.168.1.87:9100`, and partial-cut bytes `1d 56 01` physically cut the paper.
That sequence is specific to the verified RP326 behavior and always requires an
explicit caller confirmation. There is no bitmap, Unicode, arbitrary code-page,
or status-query support yet.
