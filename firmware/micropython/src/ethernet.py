class EthernetError(Exception):
    pass


class W5500LAN:
    """MicroPython 1.28 W5500 LAN adapter.

    SPI1/GPIO wiring physically verified on the purchased board.
    """

    def __init__(self, config, sleep_ms=None):
        self.config = config
        self.lan = None
        self.network = None
        self.sleep_ms = sleep_ms or self._default_sleep_ms

    @staticmethod
    def _default_sleep_ms(milliseconds):
        time = __import__("time")
        sleep_ms = getattr(time, "sleep_ms", None)
        if sleep_ms is not None:
            sleep_ms(milliseconds)
        else:
            time.sleep(milliseconds / 1000)

    def initialize(self):
        try:
            machine = __import__("machine")
            network = __import__("network")
            pin = machine.Pin
            spi = machine.SPI(1, sck=pin(13), mosi=pin(11), miso=pin(12))
            self.lan = network.LAN(
                spi=spi,
                phy_type=network.PHY_W5500,
                phy_addr=0,
                cs=pin(14),
                int=pin(10),
                reset=pin(9),
            )
            self.network = network
            self.lan.active(True)
            return self.status()
        except Exception as exc:
            raise EthernetError(f"W5500 initialization failed: {exc}") from exc

    def reconnect(self):
        if self.lan is None or self.network is None:
            raise EthernetError("Ethernet is not initialized")
        try:
            self.lan.active(False)
            self.sleep_ms(100)
            self.lan.active(True)
            return self.configure_static()
        except Exception as exc:
            raise EthernetError(f"W5500 reconnect failed: {exc}") from exc

    def configure_static(self):
        if self.lan is None or self.network is None:
            raise EthernetError("Ethernet is not initialized")
        network = self.network
        settings = self.config["ethernet"]
        try:
            resolver = network.ipconfig("dns")
        except (OSError, TypeError, ValueError, AttributeError):
            resolver = None
        desired = (settings["address"], settings["netmask"])
        if tuple(self.lan.ipconfig("addr4")) != desired:
            self.lan.ipconfig(dhcp4=False)
            self.lan.ipconfig(addr4=desired)
        if settings.get("gateway"):
            self.lan.ipconfig(gw4=settings["gateway"])
        resolver = settings.get("dns") or resolver
        if resolver:
            network.ipconfig(dns=resolver)
        return self.status()

    def status(self):
        if self.lan is None:
            return {"initialized": False, "active": False, "link_up": False}
        raw = self.lan.status()
        connected = getattr(self.network, "ETH_CONNECTED", None)
        got_ip = getattr(self.network, "ETH_GOT_IP", None)
        disconnected = getattr(self.network, "ETH_DISCONNECTED", None)
        link_up = raw in (connected, got_ip)
        if raw == disconnected:
            link_up = False
        try:
            addr4 = self.lan.ipconfig("addr4")
            gateway = self.lan.ipconfig("gw4") or "0.0.0.0"
            try:
                network = self.network
                dns = (network.ipconfig("dns") if network is not None else None) or "0.0.0.0"
            except (OSError, TypeError, ValueError, AttributeError):
                dns = "0.0.0.0"
            # RPC shape stays (ip, netmask, gateway, dns).
            address = (addr4[0], addr4[1], gateway, dns)
        except (OSError, TypeError, ValueError, IndexError, AttributeError):
            address = None
        return {
            "initialized": True,
            "active": self.lan.active(),
            "link_up": link_up,
            "raw_status": raw,
            "ifconfig": address,
        }
