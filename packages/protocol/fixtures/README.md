# Binary fixtures

`expected-hello-world.bin` is the exact initial test payload: ESC/POS initialize,
printable ASCII text, then three LF bytes. It does not contain a cutter command.
`expected-rich-receipt.bin` is the exact host-/simulator-tested ESC/POS output for
the representative styled-text, rule, QR, and feed receipt; style and QR
appearance remain unverified on the purchased printer.
