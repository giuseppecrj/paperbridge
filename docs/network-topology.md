# Network topology

## Mode A: direct cable

```text
Mac --USB--> ESP32 (192.168.1.50/24) --Ethernet--> printer (observed address)
```

No gateway or DNS is needed. Preserve the printer's observed subnet for the
first attempt and do not change its address before reading the self-test.
The purchased ESP32 and RP326 negotiated a direct link on 2026-08-01; W5500
status reported `link_up: true`, and `192.168.1.87:9100` accepted a probe. Treat
those as purchased-unit observations, not universal cable or printer defaults.
If a replacement setup has no link, try a crossover cable or Mode B.

## Mode B: switch or router

Connect ESP32 and printer with separate cables to a small switch/router. Use this
when direct negotiation fails, DHCP aids inspection, the printer utility needs a
shared network, or the optional local MQTT tracer needs to reach the Mac mini.
The Mac still controls the ESP32 over USB; Mode B is not a requirement for the
USB application path.

Address, netmask, optional gateway/DNS, printer host, printer port, and MQTT
broker host are independent configuration fields.
