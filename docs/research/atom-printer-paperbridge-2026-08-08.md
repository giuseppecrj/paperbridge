# M5Stack ATOM Printer feasibility for Paperbridge

Research date: 2026-08-08  
Status: primary-source research only. This is not an implementation decision,
firmware change, or physical verification of an ATOM Lite or Atom Printer kit.

## Scope and conclusion

This evaluates M5Stack SKU **K118 Atom Printer**: an Atom-Lite
(ESP32-PICO-D4, 4 MB flash, 520 KB SRAM) installed in a 58 mm
thermal-printer kit. The Atom-Lite product page does not list external PSRAM.
It is not a replacement for the purchased Waveshare ESP32-S3-ETH/Rongta path.

**Conclusion:** a small USB-to-UART, text-only Paperbridge proof is feasible.
It needs an Atom-specific composition/profile and a UART printer adapter; it
cannot run the present W5500/TCP profile unchanged. Do not enable the current
65,536-byte serial/MQTT or 576-dot raster limits on this target. Start without
MQTT/TLS, images, or cut. The kit is documented as manual tear-off.

| Claim | Classification | Evidence |
| --- | --- | --- |
| The kit has an Atom-Lite, a 58 mm printer, TTL UART at 9600 8N1, 384 dots/line, 12 V/2.5 A printer power, and manual tear-off. | Documented | [M5Stack Atom Printer product/protocol page](https://docs.m5stack.com/en/atom/atom_printer) |
| Official MicroPython has an `M5STACK_ATOM` target and a v1.28.0 binary. | Documented | [MicroPython Atom download page](https://micropython.org/download/M5STACK_ATOM/); [v1.28.0 source commit `e0e9fbb`](https://github.com/micropython/micropython/tree/e0e9fbb17ed6fd06bb76e266ae554784c9c80804) |
| Current Paperbridge is a USB NDJSON RPC → W5500 → TCP ESC/POS design. | Implemented / physically verified only on the purchased Waveshare/RP326 path | `docs/architecture.md`, `docs/hardware.md`, `firmware/micropython/src/app.py` |
| An Atom UART printer, Atom USB RPC, MQTT, TLS, CTS, raster output, or paper output works with Paperbridge. | **Not verified** | No Atom kit was connected, flashed, deployed, printed to, or otherwise operated for this research. |

The source list contains only M5Stack, MicroPython, and this repository. Links
to GitHub below are fixed commits where possible, so later upstream changes do
not silently change the evidence.

## 1. USB serial, flashing, and runtime path

### Documented path

M5Stack describes Atom-Lite as an ESP32-PICO-D4 with 4 MB flash. Its Atom
Printer guide says to connect USB, install the FTDI driver where required, use
M5Burner, select the port, and burn firmware. The MicroPython Atom page instead
publishes an `M5STACK_ATOM` binary and specifies `esptool.py` erase, then
`write_flash 0x1000 ...bin`; its v1.28.0 release is available from that page.
The retrieved official v1.28.0 artifact was 1,761,168 bytes with SHA-256
`6f6453604665bf2ab8be2eba49672f15fc7d52186cac45456b015150a6aa152c`.
Re-download and verify that value immediately before a future authorized flash.

MicroPython documents the ESP32 REPL on UART0 at 115200 and says that UART is
also used to program the firmware. The v1.28 `M5STACK_ATOM` definition names
ESP32-PICO-D4, uses the standard 4 MiB flash configuration, and deploys at
`0x1000`. Therefore the expected topology is:

```text
Host USB serial <-> Atom USB/serial bridge <-> ESP32 UART0 (flash, REPL, NDJSON RPC)
                                           ESP32 UART2 (GPIO 23/33) <-> kit printer TTL
```

Sources:

- [M5Stack Atom Printer guide](https://docs.m5stack.com/en/guide/hobby_kit/atom_printer/usage)
- [MicroPython Atom install instructions](https://micropython.org/download/M5STACK_ATOM/)
- [MicroPython ESP32 port: programming and UART0 REPL](https://github.com/micropython/micropython/blob/e0e9fbb17ed6fd06bb76e266ae554784c9c80804/ports/esp32/README.md#L147-L210)
- [MicroPython v1.28 Atom board configuration](https://github.com/micropython/micropython/tree/e0e9fbb17ed6fd06bb76e266ae554784c9c80804/ports/esp32/boards/M5STACK_ATOM)

### Fit with Paperbridge

The host-side USB contract can stay NDJSON. `firmware/micropython/main.py`
runs `src.app` over `sys.stdin`/`sys.stdout`; `serial_rpc.py` already bounds
and correlates one request/response line. This is a good fit for the Atom
USB/UART0 console, but is **not host-tested on Atom hardware**.

The current composition root is not a usable Atom runtime: it always constructs
`W5500LAN`, `PrinterTransport` with IPv4 host/port, and Ethernet-link guards.
It catches W5500 boot failure to keep USB diagnostics available, but
`printer.*` and `job.submit` still require a W5500 link. The existing Waveshare
flash/deploy commands also select the S3 SPIRAM image, so they must not be used
for Atom without an explicit target selection.

## 2. Printer UART wiring, electrical boundary, and CTS

M5Stack's product pin map lists the kit printer signals as follows:

| Atom GPIO | Kit printer signal | Meaning from official M5 source |
| ---: | --- | --- |
| 23 | TX | `ATOM_PRINTER::begin` uses TX=23 |
| 33 | RX | `ATOM_PRINTER::begin` uses RX=33 |
| 19 | CTS | Listed by the product pin map, but not configured by M5's library |

The official `ATOM_PRINTER` library defaults to `Serial2`, 9600, 8N1,
`RX=33`, and `TX=23`. Its `begin()` only calls `HardwareSerial::begin` with RX
and TX. It does not set RTS/CTS flow control and does not read GPIO 19.

Sources:

- [M5Stack pin map and 9600 8N1 specification](https://docs.m5stack.com/en/atom/atom_printer)
- [Official library interface, commit `aa35436`](https://github.com/m5stack/ATOM-PRINTER/blob/aa35436b66c42d7091fe3ddfe01572baeb70e7db/src/ATOM_PRINTER.h#L20-L23)
- [Official library UART initialization](https://github.com/m5stack/ATOM-PRINTER/blob/aa35436b66c42d7091fe3ddfe01572baeb70e7db/src/ATOM_PRINTER.cpp#L4-L9)

### CTS decision

For the first prototype, configure only TX=23 and RX=33 at 9600 8N1, with
hardware flow control disabled. This matches the supplied M5 firmware source.
Do not guess a pull-up, active polarity, or a voltage level for CTS: the M5
product page names a TTL interface and maps CTS to GPIO 19, but does not state
its voltage, polarity, or required behaviour. In particular, do not treat the
kit's separately listed RS-232 interface as an ESP32 GPIO electrical level.

MicroPython supports `cts=` and `flow=machine.UART.CTS`; its ESP32 port routes
the selected CTS pin to ESP-IDF hardware flow control. Only enable
`cts=19, flow=UART.CTS` after an authorized physical check proves both the
signal direction/level and that the printer requires it. A future CTS check
must also prove that a held CTS state stops transmission rather than silently
losing bytes.

Sources:

- [MicroPython `machine.UART` flow-control API](https://docs.micropython.org/en/v1.28.0/library/machine.UART.html)
- [v1.28 ESP32 UART CTS implementation](https://github.com/micropython/micropython/blob/e0e9fbb17ed6fd06bb76e266ae554784c9c80804/ports/esp32/machine_uart.c#L236-L251)

## 3. Official printer protocol versus current Paperbridge ESC/POS

M5Stack calls the linked document a protocol/command set. It is binary
ESC/POS-style, not the current Paperbridge semantic job schema. The supplied
M5 library writes those bytes directly to UART.

| Capability | M5Stack documented command set | Current Paperbridge renderer | Atom implication |
| --- | --- | --- | --- |
| Reset | `ESC @` (`1b 40`) | Same `INITIALIZE` bytes | Good first no-paper-motion command to observe, but still needs hardware check. |
| Text and feed | Raw text and LF | Printable-ASCII text and bounded LF feed blocks | Compatible in principle; test first. |
| Position, margin, line spacing, baud | `ESC $`, `GS L`, `ESC 3`, vendor baud command | Not exposed as semantic blocks | Not needed for the first receipt path. |
| Character size / underline | `GS !`, `ESC -` | Same families | Candidate compatibility; appearance remains unverified. |
| Bold | Product table says `ESC G` | Renderer emits `ESC E` | Do not promise bold on Atom until observed. |
| QR | `GS ( k` ECL, store, print | `GS ( k`, fixed model 2, size 1..8, ECL M, store, print | Same family, but M5's library appends a NUL after stored data and does not configure model/size. Validate a short QR before accepting Paperbridge's sequence. |
| 1D barcode | Supported by product and library | No barcode semantic block | Unsupported by Paperbridge v1; do not add it for the prototype. |
| Raster | `GS v 0`; product width is at most 384 dots/line | `GS v 0`; schema permits up to 576 dots and 41,472 bytes | Current maximum is too wide. An Atom profile must cap width at 384 before any image work. |
| Cut | Product says manual tear-off | Current RP326-only partial-cut byte is `GS V 1` | Reject/omit cut for Atom. Do not run the current cut test. |

The product page's command table and the M5 library support the byte-family
comparison above. Paperbridge's renderer is separately host-/simulator-tested
against the RP326 path; only RP326 text/feed/cut, QR, and raster observations
are physical evidence in this repository. They are not evidence for the Atom
printer.

Sources:

- [M5Stack Atom Printer protocol table](https://docs.m5stack.com/en/atom/atom_printer)
- [M5Stack command constants](https://github.com/m5stack/ATOM-PRINTER/blob/aa35436b66c42d7091fe3ddfe01572baeb70e7db/src/ATOM_PRINTER_CMD.h)
- [M5Stack QR and bitmap writes](https://github.com/m5stack/ATOM-PRINTER/blob/aa35436b66c42d7091fe3ddfe01572baeb70e7db/src/ATOM_PRINTER.cpp#L57-L113)
- `firmware/micropython/src/escpos.py`, `docs/protocol.md`,
  `firmware/micropython/tests/test_escpos.py`

## 4. Memory limits: MQTT, JSON/base64, raster, and TLS

### What is documented and what is not

M5Stack documents **520 KB SRAM** and **4 MB flash** for Atom-Lite; the product
page does not list external PSRAM. These are hardware capacities, not a usable
MicroPython heap number. Flash capacity is not a RAM budget.
MicroPython documents that a board with external SPIRAM has megabytes of RAM,
and that ESP32 applications with TLS connections or large buffers can run out
of RAM. The v1.28 Atom board definition selects 4 MiB flash and does not select
a `SPIRAM` configuration; its `CONFIG_SPIRAM_SPEED_80M` line alone is not an
enablement claim. Do not state a numeric Atom heap limit without a runtime
measurement on the exact flashed kit.

The only supported measurement for the proposed firmware is on-device
`gc.mem_free()` / `gc.mem_alloc()`. Paperbridge already exposes those values as
`system.memory`; record them before, during, and after each authorized test.
MicroPython warns that free-memory values may be unavailable (`-1`), and says
the GC threshold is a fragmentation heuristic, not a capacity guarantee.

Sources:

- [M5Stack product specification](https://docs.m5stack.com/en/atom/atom_printer)
- [MicroPython ESP32 memory guidance](https://github.com/micropython/micropython/blob/e0e9fbb17ed6fd06bb76e266ae554784c9c80804/ports/esp32/README.md#L28-L44)
- [MicroPython v1.28 Atom flash configuration](https://github.com/micropython/micropython/blob/e0e9fbb17ed6fd06bb76e266ae554784c9c80804/ports/esp32/boards/sdkconfig.base#L104-L107)
- [MicroPython `gc` API](https://docs.micropython.org/en/v1.28.0/library/gc.html)

### Present Paperbridge ceilings are S3/PSRAM-path ceilings, not Atom limits

| Present implementation | Value | Why it is unsafe to assume on Atom |
| --- | ---: | --- |
| NDJSON request line / MQTT message | 65,536 bytes | The device holds the input bytes, decoded text, parsed JSON graph, and result objects. |
| Prepared raster | 576×576; 41,472 raw bytes | The Atom printer is only 384 dots/line; source base64 is up to 55,296 characters. |
| Rendered payload | 65,536 bytes | `EscPosRenderer` builds a complete `bytearray` then a `bytes` result before transport sends it. |
| TLS CA configuration | up to 16,384 ASCII bytes | TLS also needs Wi-Fi, socket, TLS, MQTT, JSON, and certificate allocations; no Atom measurement exists. |

For a maximum current raster MQTT job, the input payload can be 65,536 bytes,
the base64 field alone is 55,296 characters, decoded raster is 41,472 bytes,
and rendered output can be 65,536 bytes. These objects overlap in the current
message → JSON → base64 decode → render flow. The simple sum of only the
input, base64 text, decoded raster, and rendered output is already 227,840
bytes, before Python object overhead, socket buffers, Wi-Fi, MQTT, TLS, and
heap fragmentation. This is an allocation-risk explanation, **not** a measured
peak or an Atom SRAM claim.

The current host test limits CPython traced peak allocation to three times the
raster byte count. It is host evidence only; it cannot establish MicroPython
heap use.

Sources: `firmware/micropython/config.example.json`,
`firmware/micropython/src/{constants,serial_rpc,job_schema,escpos,mqtt_adapter,config}.py`,
`firmware/micropython/tests/test_escpos.py`, and `apps/api/src/image-preparer.ts`.

### Target policy

1. **Prototype:** USB NDJSON, text only, low line bound (for example 1,024
   bytes), no MQTT, no TLS, no image/raster, no cut.
2. **Then plain MQTT:** set a small independently measured message limit and
   only text/feed jobs. Measure heap across connect, subscribe, receive,
   render, UART write, disconnect, and repeated GC.
3. **Then TLS:** separate physical spike with one CA and a small no-output
   probe before allowing a print job. TLS failure, a reset, or declining heap
   stops this target path.
4. **Raster last:** host-prepare to 384-dot width; choose a small height from
   measured heap. A safe implementation must stream or otherwise bound each
   allocation before raising the current global maxima. Do not accept base64
   raster input merely because the S3 profile accepts it.

## 5. Firmware target/profile versus transport abstraction

Use a separate **Atom printer profile**, not a fork of the semantic job,
renderer, serial-RPC, or MQTT contracts.

Keep shared:

- `serial_rpc.py`, semantic `print-job.v1` validation, `JobService`,
  `PrintCoordinator`, `EscPosRenderer`, and the honest
  `delivered_to_printer` vocabulary;
- the host CLI request correlation; and
- current W5500/RP326 configuration and behaviour unchanged.

Replace in the Atom profile:

- the `W5500LAN` boot/configuration and every Ethernet-link guard;
- IPv4 `printer.host`/`port` configuration and TCP `probe()` semantics;
- `PrinterTransport` with a UART writer configured for GPIO 23/33, 9600 8N1,
  bounded write timeout, and `bytes_sent`; and
- the profile limits: 384-dot maximum, no cut, and conservative serial/MQTT
  size limits.

A new formal transport hierarchy is not needed for the first slice. The
existing coordinator uses only `transport.send(payload)` and tests already use
small duck-typed transports. An Atom UART object can return the same result
shape with an explicit endpoint such as `uart://gpio23-gpio33@9600`. However,
`CommandRouter` currently also calls `transport.endpoint()`, `transport.probe()`,
and hard-codes Ethernet guards. Keep these diagnostics profile-specific rather
than pretending a UART write is a TCP reachability probe. A UART write proves
only that bytes were accepted by the device UART, not that paper emerged.

This is a profile/composition-root change because it selects hardware, limits,
and diagnostics. It is not a reason to alter the shared semantic protocol or
the proven RP326 transport.

Sources: `firmware/micropython/src/{app,printer_transport,print_coordinator,rpc_commands,job_service}.py`,
`firmware/micropython/tests/test_{job_service,printer_transport,print_job_submission}.py`,
and `docs/adr/0004-use-ethernet-escpos-for-printer.md`.

## 6. Smallest host-tested prototype and hardware-validation order

### Host-tested prototype (no hardware)

Implement only after approval:

1. Add an Atom-only UART transport with injected UART writer. It writes the
   supplied bytes, checks full write progress, and returns
   `delivered_to_printer` plus `bytes_sent`. It must never return `printed`.
2. Add one focused host test with the injected writer: submit the existing
   `valid-text-feed.json` through `JobService`/`PrintCoordinator`, assert the
   exact bytes `1b 40` + text + line feeds, the configured UART tuple
   `(2, 9600, tx=23, rx=33)`, and the delivery result. This reuses existing
   semantic/rendering tests rather than creating a new protocol.
3. Add one negative profile test: reject `cut` and raster width greater than
   384. MQTT/TLS are out of this first prototype.

This is deliberately smaller than a transport framework and leaves all current
Waveshare behaviour unchanged. Existing `test_print_job_submission.py` already
proves the same semantic path against the TCP printer simulator; the new test
would prove only Atom profile byte selection with a fake UART, not electrical
or printer success.

### Future authorized hardware sequence

Do not run this sequence under this research task. It has external effects.
When authorized, use the exact selected USB port and record every result as
`physically_verified` only when observed on this kit.

1. **Inventory and power:** confirm kit SKU/revision and the supplied internal
   harness; power the printer only with the documented independent 12 V,
   at-least-2.5 A supply. Do not infer GPIO levels or substitute RS-232 wiring.
2. **USB only:** enumerate the one selected port, flash the official
   `M5STACK_ATOM` artifact only after checksum verification, open the 115200
   REPL, and record board identity, reset cause, and heap. No printer command.
3. **USB RPC only:** deploy the future Atom profile and prove `system.ping`,
   `system.info`, and bounded malformed/oversized NDJSON rejection. No MQTT,
   printer output, feed, or cut.
4. **UART electrical check:** configure UART2 TX=23/RX=33 at 9600 8N1 without
   flow control. Verify idle/active signal behaviour with a suitable instrument
   or the kit's documented harness. Only investigate GPIO19 CTS if the
   no-flow-control check fails or byte loss is observed.
5. **No-output printer check:** send only `ESC @`; observe no unexpected paper
   motion and record that it is not paper-output proof.
6. **Text:** submit one unique short ASCII semantic job. Record UART
   `bytes_sent` as delivery to UART and separately have the operator observe
   paper. Test a second unique text job after a reset.
7. **Feed:** only after text is observed, test bounded feed and have the
   operator observe motion. **Never run the current RP326 cut test:** this kit
   is manual tear-off.
8. **Reliability/memory:** repeat USB text jobs while recording heap/reset
   state. Add plain MQTT text only after that passes; add TLS no-output then
   TLS text; add small 384-dot raster last. A reset, heap decline, message
   corruption, or unexplained duplicate ends the experiment and is not hidden
   by a retry.

## Primary-source register

| Topic | Primary source |
| --- | --- |
| Atom Printer SKU/specification, pin map, protocol table | <https://docs.m5stack.com/en/atom/atom_printer> |
| Atom-Lite SRAM, flash, GPIO, and USB specification | <https://docs.m5stack.com/en/core/ATOM%20Lite> |
| M5Stack flashing/MQTT operating guide | <https://docs.m5stack.com/en/guide/hobby_kit/atom_printer/usage> |
| M5 printer library (fixed commit) | <https://github.com/m5stack/ATOM-PRINTER/tree/aa35436b66c42d7091fe3ddfe01572baeb70e7db> |
| M5 Atom library hardware description (fixed commit) | <https://github.com/m5stack/M5Atom/tree/ebbf736396f9459bf1adc7b588a7f1825b366844> |
| MicroPython Atom downloads/install instructions | <https://micropython.org/download/M5STACK_ATOM/> |
| MicroPython v1.28 source (fixed release commit) | <https://github.com/micropython/micropython/tree/e0e9fbb17ed6fd06bb76e266ae554784c9c80804> |
| MicroPython v1.28 UART API | <https://docs.micropython.org/en/v1.28.0/library/machine.UART.html> |
| MicroPython v1.28 GC API | <https://docs.micropython.org/en/v1.28.0/library/gc.html> |

## Non-claims

- No board, USB port, firmware image, printer, paper, power supply, MQTT
  broker, or TLS endpoint was operated.
- No claim is made that Atom Lite has a particular free heap, PSRAM amount,
  CTS polarity, or TTL voltage level.
- No claim is made that M5's printer accepts every current Paperbridge ESC/POS
  sequence, especially bold, QR model/size, raster, or cut.
- No current Paperbridge source, schema, configuration, test, or hardware
  evidence was changed by this research.
