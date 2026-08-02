class WiFiStation:
    """ESP32 station-mode Wi-Fi adapter with bounded reconnect attempts."""

    def __init__(
        self,
        config,
        wlan_factory=None,
        clock_ms=None,
        ticks_diff=None,
        lock=None,
    ):
        self.settings = config["wifi"]
        self.wlan_factory = wlan_factory or self._default_wlan_factory
        self.clock_ms = clock_ms or self._default_clock_ms
        self.ticks_diff = ticks_diff or self._default_ticks_diff
        self._lock = lock or __import__("_thread").allocate_lock()
        self.wlan = None
        self.last_connect_attempt_ms = None
        self.last_error = None
        self._status = {
            "enabled": True,
            "initialized": False,
            "active": False,
            "connected": False,
            "raw_status": None,
            "ifconfig": None,
            "last_error": None,
        }

    @staticmethod
    def _default_wlan_factory():
        network = __import__("network")
        wlan_class = network.WLAN
        station_id = getattr(wlan_class, "IF_STA", getattr(network, "STA_IF", 0))
        return wlan_class(station_id)

    @staticmethod
    def _default_clock_ms():
        time = __import__("time")
        ticks_ms = getattr(time, "ticks_ms", None)
        if ticks_ms:
            return ticks_ms()
        try:
            return int(time.monotonic() * 1000)
        except AttributeError:
            return int(time.time() * 1000)

    @staticmethod
    def _default_ticks_diff(new, old):
        time = __import__("time")
        ticks_diff = getattr(time, "ticks_diff", None)
        return ticks_diff(new, old) if ticks_diff else new - old

    def _initialize(self):
        if self.wlan is None:
            self.wlan = self.wlan_factory()
            self.wlan.active(True)

    def _should_connect(self):
        if self.last_connect_attempt_ms is None:
            return True
        elapsed = self.ticks_diff(self.clock_ms(), self.last_connect_attempt_ms)
        return elapsed >= self.settings["retry_interval_ms"]

    def _store_status(self, active, connected, raw_status, address, error):
        self._lock.acquire()
        try:
            self.last_error = error
            self._status = {
                "enabled": True,
                "initialized": self.wlan is not None,
                "active": active,
                "connected": connected,
                "raw_status": raw_status,
                "ifconfig": address,
                "last_error": error,
            }
        finally:
            self._lock.release()

    def _refresh_status(self, error=None):
        wlan = self.wlan
        if wlan is None:
            self._store_status(False, False, None, None, error)
            return
        try:
            active = wlan.active()
            connected = wlan.isconnected()
            raw_status = wlan.status()
            address = wlan.ifconfig() if connected else None
        except Exception as exc:
            active = False
            connected = False
            raw_status = None
            address = None
            if error is None:
                error = f"WIFI_STATUS_FAILED: {exc}"
        self._store_status(active, connected, raw_status, address, error)

    def record_error(self, message):
        self._lock.acquire()
        try:
            self.last_error = message
            self._status["last_error"] = message
        finally:
            self._lock.release()

    def poll(self):
        try:
            self._initialize()
            wlan = self.wlan
            if wlan is None:
                raise RuntimeError("Wi-Fi station failed to initialize")
            if not wlan.isconnected() and self._should_connect():
                self.last_connect_attempt_ms = self.clock_ms()
                wlan.connect(self.settings["ssid"], self.settings["password"])
            self._refresh_status()
        except Exception as exc:
            self._refresh_status(f"WIFI_CONNECT_FAILED: {exc}")

    def status(self):
        self._lock.acquire()
        try:
            return dict(self._status)
        finally:
            self._lock.release()
