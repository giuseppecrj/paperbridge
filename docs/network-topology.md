# Network topology

## Mode A: direct cable

```text
Mac --USB--> ESP32 (192.168.1.50/24) --Ethernet--> printer (observed address)
```

No gateway or DNS is needed. Preserve the printer's observed subnet for the
first attempt and do not change its address before reading the self-test.
Direct-link negotiation and Auto-MDI/MDIX are unverified. Check LEDs and the
W5500 link status. If no link appears, try a crossover cable or Mode B.

## Mode B: switch or router

Connect ESP32 and printer with separate cables to a small switch/router. Use this
when direct negotiation fails, DHCP aids inspection, or the printer utility needs
a shared network. The Mac still controls the ESP32 over USB; Mode B is not a
requirement for the application protocol.

Address, netmask, optional gateway/DNS, printer host, and printer port are
independent configuration fields.
