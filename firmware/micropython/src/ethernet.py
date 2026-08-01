class EthernetError(Exception):
    pass


class W5500LAN:
    """MicroPython 1.28 adapter; purchased board wiring remains physically unverified."""

    def __init__(self, config):
        self.config = config
        self.lan = None
        self.network = None

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

    def configure_static(self):
        if self.lan is None:
            raise EthernetError("Ethernet is not initialized")
        settings = self.config["ethernet"]
        gateway = settings.get("gateway") or "0.0.0.0"
        dns = settings.get("dns") or "0.0.0.0"
        # Version seam: MicroPython 1.28 retains the four-field ifconfig API.
        self.lan.ifconfig((settings["address"], settings["netmask"], gateway, dns))
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
            address = self.lan.ifconfig()
        except OSError:
            address = None
        return {
            "initialized": True,
            "active": self.lan.active(),
            "link_up": link_up,
            "raw_status": raw,
            "ifconfig": address,
        }
