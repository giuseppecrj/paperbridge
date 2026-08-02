from src.ethernet import W5500LAN


class FakeLAN:
    def __init__(self, current, fail_on_set=False):
        self.current = current
        self.fail_on_set = fail_on_set
        self.set_calls = 0
        self.ipconfig_calls = []
        self.active_calls = []
        self.raw_status = 5
        self.enabled = True

    def ifconfig(self, value=None):
        raise AssertionError("status and configure must not use deprecated ifconfig")

    def ipconfig(self, param=None, **settings):
        if param == "addr4":
            return self.current[:2]
        if param == "gw4":
            return self.current[2]
        self.ipconfig_calls.append(settings)
        if "addr4" in settings:
            self.current = (*settings["addr4"], *self.current[2:])
        if "gw4" in settings:
            self.current = (*self.current[:2], settings["gw4"], self.current[3])

    def status(self):
        return self.raw_status

    def active(self, enabled=None):
        if enabled is None:
            return self.enabled
        self.active_calls.append(enabled)
        self.enabled = enabled
        self.raw_status = 5 if enabled else 2


class FakeNetwork:
    ETH_CONNECTED = 3
    ETH_DISCONNECTED = 4
    ETH_GOT_IP = 5

    def __init__(self, dns=None, fail_dns=False):
        self.dns = dns
        self.fail_dns = fail_dns

    def ipconfig(self, param=None, **settings):
        if param == "dns":
            if self.fail_dns:
                raise OSError("dns unavailable")
            return self.dns
        if "dns" in settings:
            self.dns = settings["dns"]
            return None
        return None


def config():
    return {
        "ethernet": {
            "address": "192.168.1.50",
            "netmask": "255.255.255.0",
            "gateway": None,
            "dns": None,
        }
    }


def make_adapter(current, fail_on_set=False, dns=None, fail_dns=False):
    value = W5500LAN(config())
    lan = FakeLAN(current, fail_on_set=fail_on_set)
    value.lan = lan
    value.network = FakeNetwork(dns=dns if dns is not None else current[3], fail_dns=fail_dns)
    return value, lan


def test_reconnect_restarts_the_existing_lan_and_reapplies_static_configuration():
    sleeps = []
    value, lan = make_adapter(("192.168.1.50", "255.255.255.0", "0.0.0.0", "0.0.0.0"))
    value.sleep_ms = sleeps.append
    lan.raw_status = 1

    result = value.reconnect()

    assert lan.active_calls == [False, True]
    assert sleeps == [100]
    assert result["link_up"] is True
    assert result["ifconfig"] == (
        "192.168.1.50",
        "255.255.255.0",
        "0.0.0.0",
        "0.0.0.0",
    )


def test_configure_static_uses_ipconfig_instead_of_deprecated_ifconfig_setter():
    value, lan = make_adapter(("0.0.0.0", "0.0.0.0", "0.0.0.0", "0.0.0.0"), fail_on_set=True)

    result = value.configure_static()

    assert result["ifconfig"] == (
        "192.168.1.50",
        "255.255.255.0",
        "0.0.0.0",
        "0.0.0.0",
    )
    assert lan.ipconfig_calls == [
        {"dhcp4": False},
        {"addr4": ("192.168.1.50", "255.255.255.0")},
    ]
    assert lan.set_calls == 0


def test_configure_static_does_not_reapply_identical_configuration():
    value, lan = make_adapter(
        ("192.168.1.50", "255.255.255.0", "0.0.0.0", "0.0.0.0"),
        fail_on_set=True,
    )

    result = value.configure_static()
    assert result["ifconfig"] == (
        "192.168.1.50",
        "255.255.255.0",
        "0.0.0.0",
        "0.0.0.0",
    )
    assert lan.ipconfig_calls == []
    assert lan.set_calls == 0


def test_status_reads_address_gateway_and_dns_via_ipconfig():
    value, _lan = make_adapter(("192.168.1.50", "255.255.255.0", "192.168.1.1", "8.8.8.8"))

    status = value.status()

    assert status["ifconfig"] == (
        "192.168.1.50",
        "255.255.255.0",
        "192.168.1.1",
        "8.8.8.8",
    )
    assert status["initialized"] is True
    assert status["link_up"] is True


def test_status_falls_back_when_dns_query_fails():
    value, _lan = make_adapter(
        ("192.168.1.50", "255.255.255.0", "192.168.1.1", "8.8.8.8"),
        fail_dns=True,
    )

    status = value.status()

    assert status["ifconfig"] == (
        "192.168.1.50",
        "255.255.255.0",
        "192.168.1.1",
        "0.0.0.0",
    )
