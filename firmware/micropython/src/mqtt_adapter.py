import json


class MqttTracer:
    """Bounded no-output MQTT probe responder for the configured device."""

    def __init__(
        self,
        config,
        wifi,
        client_factory=None,
        clock_ms=None,
        ticks_diff=None,
        lock=None,
    ):
        self.config = config
        self.wifi = wifi
        self.settings = config["mqtt"]
        self.client_factory = client_factory or self._default_client_factory
        self.clock_ms = clock_ms or self._default_clock_ms
        self.ticks_diff = ticks_diff or self._default_ticks_diff
        self._lock = lock or __import__("_thread").allocate_lock()
        self.client = None
        self.last_error = None
        self.last_connect_attempt_ms = None
        prefix = self.settings["topic_prefix"].strip("/")
        device_id = config["device_id"]
        self.jobs_topic = (f"{prefix}/{device_id}/jobs").encode()
        self.status_topic = (f"{prefix}/{device_id}/status").encode()

    @staticmethod
    def _default_client_factory(**settings):
        mqtt = __import__("umqtt.simple", None, None, ("MQTTClient",))
        return mqtt.MQTTClient(
            settings["client_id"],
            settings["host"],
            port=settings["port"],
            user=settings["username"],
            password=settings["password"],
            keepalive=settings["keepalive_seconds"],
        )

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

    def _get_client(self):
        self._lock.acquire()
        try:
            return self.client
        finally:
            self._lock.release()

    def _set_state(self, client, error):
        self._lock.acquire()
        try:
            self.client = client
            self.last_error = error
        finally:
            self._lock.release()

    def record_error(self, message):
        self._lock.acquire()
        try:
            self.last_error = message
        finally:
            self._lock.release()

    def _can_connect(self):
        if not self.wifi.status().get("connected"):
            return False
        if self.last_connect_attempt_ms is None:
            return True
        elapsed = self.ticks_diff(self.clock_ms(), self.last_connect_attempt_ms)
        return elapsed >= self.settings["retry_interval_ms"]

    def _connect(self):
        self.last_connect_attempt_ms = self.clock_ms()
        try:
            client = self.client_factory(
                client_id=self.settings["client_id"],
                host=self.settings["host"],
                port=self.settings["port"],
                username=self.settings["username"],
                password=self.settings["password"],
                keepalive_seconds=self.settings["keepalive_seconds"],
            )
            client.set_callback(self._handle_message)
            client.connect()
            client.subscribe(self.jobs_topic, qos=1)
            self._set_state(client, None)
        except Exception as exc:
            self._set_state(None, f"MQTT_CONNECT_FAILED: {exc}")

    def poll(self):
        self.wifi.poll()
        if not self.wifi.status().get("connected"):
            self._set_state(None, "WIFI_DISCONNECTED")
            return
        client = self._get_client()
        if client is None:
            if self._can_connect():
                self._connect()
            return
        try:
            client.check_msg()
        except Exception as exc:
            self._set_state(None, f"MQTT_POLL_FAILED: {exc}")

    def status(self):
        self._lock.acquire()
        try:
            return {
                "enabled": True,
                "connected": self.client is not None,
                "last_error": self.last_error,
            }
        finally:
            self._lock.release()

    def _handle_message(self, topic, payload):
        if topic != self.jobs_topic:
            self.record_error("UNEXPECTED_MQTT_TOPIC")
            return
        if not isinstance(payload, bytes) or len(payload) > self.settings["max_message_bytes"]:
            self.record_error("INVALID_MQTT_PAYLOAD")
            return
        try:
            message = json.loads(payload.decode("utf-8"))
        except (UnicodeError, ValueError):
            self.record_error("INVALID_MQTT_PAYLOAD")
            return
        if not self._valid_probe(message):
            self.record_error("INVALID_MQTT_PROBE")
            return
        response = {
            "schema_version": 1,
            "kind": "mqtt_probe_status",
            "probe_id": message["probe_id"],
            "device_id": self.config["device_id"],
            "status": "ok",
            "ts_ms": self.clock_ms(),
        }
        client = self._get_client()
        if client is None:
            self.record_error("MQTT_NOT_CONNECTED")
            return
        client.publish(self.status_topic, json.dumps(response), qos=1, retain=False)
        self.record_error(None)

    def _valid_probe(self, message):
        if not isinstance(message, dict) or set(message) != {
            "schema_version",
            "kind",
            "probe_id",
            "device_id",
            "created_at",
        }:
            return False
        return (
            message["schema_version"] == 1
            and message["kind"] == "mqtt_probe"
            and isinstance(message["probe_id"], str)
            and 1 <= len(message["probe_id"]) <= 128
            and message["device_id"] == self.config["device_id"]
            and isinstance(message["created_at"], str)
            and 1 <= len(message["created_at"]) <= 64
        )
