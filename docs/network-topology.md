# Network topology

## Product topology: Wi-Fi control, direct printer Ethernet

```text
HTTP client --> Mac mini REST service --> Mosquitto
                                         |
                                         +-- Wi-Fi --> router --> ESP32
USB-C (bring-up only) ---------------------------------------------> |
                                                                    |
ESP32 W5500 (192.168.4.50/24) --> printer (192.168.4.87:9100)
```

The private REST service binds to localhost by default and publishes semantic
jobs through Mosquitto. The ESP32 Wi-Fi interface is the MQTT control plane. The
W5500 interface is printer-only and has no gateway or DNS. The printer does not
join Wi-Fi or the home router.

The two interfaces must use different IPv4 subnets so socket routing is
unambiguous. The purchased setup uses the home LAN's `192.168.1.0/24` over
Wi-Fi and the dedicated `192.168.4.0/24` direct-printer network. These are local
observations/configuration, not universal defaults.

## Bring-up fallback: printer on router or switch

The printer may be temporarily connected to the home router to inspect or change
its embedded Ethernet configuration page. This is a setup tool, not the intended
installation. Reconnect it directly to the ESP32 after configuration.

The original direct link at `192.168.1.50 -> 192.168.1.87:9100` was physically
verified before Wi-Fi was introduced. On 2026-08-02 the direct network was moved
to `192.168.4.50 -> 192.168.4.87:9100`; W5500 link and printer reachability were
physically verified without printing.
