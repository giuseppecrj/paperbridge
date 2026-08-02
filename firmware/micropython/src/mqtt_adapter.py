import json


class MqttTracer:
    """Bounded no-output MQTT probe responder for the configured device."""

    def __init__(self, config, ethernet, client_factory=None, clock_ms=None):
        self.config = config
        self.ethernet = ethernet
        self.settings = config["mqtt"]
        self.client_factory = client_factory or self._default_client_factory
        self.clock_ms = clock_ms or self._default_clock_ms
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

    def _can_connect(self):
        if not self.ethernet.status().get("link_up"):
            return False
        if self.last_connect_attempt_ms is None:
            return True
        return self.clock_ms() - self.last_connect_attempt_ms >= self.settings["retry_interval_ms"]

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
            self.client = client
            self.last_error = None
        except Exception as exc:
            self.client = None
            self.last_error = f"MQTT_CONNECT_FAILED: {exc}"

    def poll(self):
        if self.client is None:
            if self._can_connect():
                self._connect()
            return
        try:
            self.client.check_msg()
        except Exception as exc:
            self.client = None
            self.last_error = f"MQTT_POLL_FAILED: {exc}"

    def status(self):
        return {
            "enabled": True,
            "connected": self.client is not None,
            "last_error": self.last_error,
        }

    def _handle_message(self, topic, payload):
        if topic != self.jobs_topic:
            self.last_error = "UNEXPECTED_MQTT_TOPIC"
            return
        if not isinstance(payload, bytes) or len(payload) > self.settings["max_message_bytes"]:
            self.last_error = "INVALID_MQTT_PAYLOAD"
            return
        try:
            message = json.loads(payload.decode("utf-8"))
        except (UnicodeError, ValueError):
            self.last_error = "INVALID_MQTT_PAYLOAD"
            return
        if not self._valid_probe(message):
            self.last_error = "INVALID_MQTT_PROBE"
            return
        response = {
            "schema_version": 1,
            "kind": "mqtt_probe_status",
            "probe_id": message["probe_id"],
            "device_id": self.config["device_id"],
            "status": "ok",
            "ts_ms": self.clock_ms(),
        }
        client = self.client
        if client is None:
            self.last_error = "MQTT_NOT_CONNECTED"
            return
        client.publish(self.status_topic, json.dumps(response), qos=1, retain=False)

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
