# Printer bring-up

1. Power the RP326 only from its 24 V adapter.
2. Produce a self-test receipt and record IP, TCP port, firmware, paper width,
   and interfaces in `hardware.md`.
3. Probe TCP from the ESP32. Connection success is `reachable`, not printed.
4. Send ESC/POS initialize, printable ASCII, and three line feeds. No cut.
5. Test feed separately.
6. Only then run `printer cut-test --confirm` and record the exact working bytes.

Text rejects control bytes and non-ASCII rather than silently replacing them.
On 2026-08-01 the purchased RP326 accepted text and feed at its initial
`192.168.1.87:9100` address, and partial-cut bytes `1d 56 01` physically cut the
paper. The dedicated direct-printer network now uses W5500 `192.168.4.50/24`
and printer `192.168.4.87:9100`, with no gateway or DNS. Reachability on that
subnet was physically verified without repeating paper output.

For dual-interface checks, verify `wifi status` first, then initialize/configure
W5500 and run the printer probe before MQTT. This sequence is specific to the
verified RP326 behavior and always requires explicit caller confirmation before
paper output. There is no bitmap, Unicode, arbitrary code-page, or status-query
support yet.
