WiFiStation = __import__("src.wifi", None, None, ("WiFiStation",)).WiFiStation


class FakeWLAN:
    def __init__(self):
        self.active_value = False
        self.connected = False
        self.connect_calls = []
        self.disconnect_calls = 0
        self.raw_status = 0
        self.status_calls = 0

    def active(self, value=None):
        if value is not None:
            self.active_value = value
        return self.active_value

    def connect(self, ssid, password):
        self.connect_calls.append((ssid, password))
        self.raw_status = 1

    def disconnect(self):
        self.disconnect_calls += 1
        self.connected = False
        self.raw_status = 0

    def isconnected(self):
        return self.connected

    def status(self):
        self.status_calls += 1
        return self.raw_status

    def ifconfig(self):
        return ("192.168.1.50", "255.255.255.0", "192.168.1.1", "192.168.1.1")


class TrackingLock:
    def __init__(self):
        self.acquires = 0
        self.depth = 0

    def acquire(self):
        self.acquires += 1
        self.depth += 1

    def release(self):
        self.depth -= 1


def config():
    return {
        "wifi": {
            "enabled": True,
            "ssid": "Paperbridge Test",
            "password": "not-a-real-password",
            "retry_interval_ms": 1000,
        }
    }


def test_poll_activates_station_and_starts_wifi_connection():
    wlan = FakeWLAN()
    station = WiFiStation(config(), wlan_factory=lambda: wlan, clock_ms=lambda: 0)

    station.poll()

    assert wlan.active_value is True
    assert wlan.connect_calls == [("Paperbridge Test", "not-a-real-password")]
    assert station.status() == {
        "enabled": True,
        "initialized": True,
        "active": True,
        "connected": False,
        "suspended": False,
        "raw_status": 1,
        "ifconfig": None,
        "last_error": None,
    }


def test_poll_configures_static_dns_before_connecting():
    wlan = FakeWLAN()
    dns_calls = []
    settings = config()
    settings["wifi"]["dns"] = "192.168.1.1"
    station = WiFiStation(
        settings,
        wlan_factory=lambda: wlan,
        clock_ms=lambda: 0,
        dns_setter=dns_calls.append,
    )

    station.poll()

    assert dns_calls == ["192.168.1.1"]
    assert wlan.connect_calls == [("Paperbridge Test", "not-a-real-password")]


def test_connected_station_reports_wifi_address_without_reconnecting():
    wlan = FakeWLAN()
    wlan.connected = True
    wlan.raw_status = 3
    station = WiFiStation(config(), wlan_factory=lambda: wlan, clock_ms=lambda: 0)

    station.poll()

    assert wlan.connect_calls == []
    assert station.status()["ifconfig"] == (
        "192.168.1.50",
        "255.255.255.0",
        "192.168.1.1",
        "192.168.1.1",
    )


def test_disconnected_station_retries_only_after_the_bounded_interval():
    now = [0]
    wlan = FakeWLAN()
    station = WiFiStation(config(), wlan_factory=lambda: wlan, clock_ms=lambda: now[0])

    station.poll()
    now[0] = 999
    station.poll()
    now[0] = 1000
    station.poll()

    assert wlan.connect_calls == [
        ("Paperbridge Test", "not-a-real-password"),
        ("Paperbridge Test", "not-a-real-password"),
    ]


def test_retry_timing_is_safe_across_wrapped_device_ticks():
    now = [1000]
    differences = []
    wlan = FakeWLAN()

    def ticks_diff(new, old):
        differences.append((new, old))
        return 1000

    station = WiFiStation(
        config(),
        wlan_factory=lambda: wlan,
        clock_ms=lambda: now[0],
        ticks_diff=ticks_diff,
    )
    station.poll()
    now[0] = 5
    station.poll()

    assert differences == [(5, 1000)]
    assert len(wlan.connect_calls) == 2


def test_disconnect_suspends_reconnects_until_an_explicit_reconnect_request():
    now = [0]
    wlan = FakeWLAN()
    wlan.connected = True
    station = WiFiStation(config(), wlan_factory=lambda: wlan, clock_ms=lambda: now[0])
    station.poll()

    assert station.disconnect()["suspended"] is True
    station.poll()
    now[0] = 10_000
    station.poll()

    assert wlan.disconnect_calls == 1
    assert wlan.connect_calls == []
    assert station.status()["connected"] is False

    assert station.reconnect()["suspended"] is False
    station.poll()

    assert wlan.connect_calls == [("Paperbridge Test", "not-a-real-password")]


def test_status_reads_a_locked_snapshot_without_touching_wlan():
    wlan = FakeWLAN()
    lock = TrackingLock()
    station = WiFiStation(config(), wlan_factory=lambda: wlan, clock_ms=lambda: 0, lock=lock)
    station.poll()
    status_calls = wlan.status_calls

    station.status()

    assert wlan.status_calls == status_calls
    assert lock.acquires >= 2
    assert lock.depth == 0
