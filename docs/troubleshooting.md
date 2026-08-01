# Troubleshooting

- **No serial port:** verify a data cable, try another USB port, inspect System
  Information, and enter bootloader mode per Waveshare/Espressif instructions.
- **Several ports:** pass `--port` or set `PAPERBRIDGE_PORT`; selection is never
  arbitrary.
- **Flash fails at 460800:** retry at esptool's default baud.
- **RPC timeout after reset:** wait for USB re-enumeration, confirm `main.py` and
  `config.json`, then use `mpremote` REPL to inspect typed startup errors.
- **No Ethernet LEDs/link:** do not rewrite application code first. Check power,
  cable, board revision/pins, crossover cable, switch/router, then raw link state.
- **Link but no probe:** compare subnet/mask and self-test endpoint; gateway/DNS
  are unnecessary on direct link; distinguish timeout from refusal.
- **Bytes delivered but no receipt:** check printer power, paper, cover, endpoint,
  ESC/POS compatibility, and code page. Delivery is not physical confirmation.
- **Unexpected cut:** stop; cuts are never part of text/feed payloads. Verify the
  configured profile and only use the explicit confirmed command.
