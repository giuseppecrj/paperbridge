import json

from .constants import JOB_RESULT_ERROR_CODES
from .job_ledger import JobLedger  # type: ignore[reportMissingImports]
from .serial_rpc import RpcError

_REJECTION_CODES = {
    "INVALID_PRINT_JOB",
    "WRONG_DEVICE",
    "UNAUTHORIZED_CUT",
    "JOB_TOO_LARGE",
    "ESC_POS_RENDER_FAILED",
}


class MqttTracer:
    """Bounded MQTT probe and semantic-job adapter for the configured device."""

    def __init__(
        self,
        config,
        wifi,
        client_factory=None,
        clock_ms=None,
        ticks_diff=None,
        lock=None,
        job_service=None,
        job_ledger=None,
        before_delivery=None,
        utc_year=None,
        sync_time=None,
    ):
        self.config = config
        self.wifi = wifi
        self.settings = config["mqtt"]
        self.tls = self.settings.get("tls", {"enabled": False})
        self.client_factory = client_factory or self._default_client_factory
        self.clock_ms = clock_ms or self._default_clock_ms
        self.utc_year = utc_year or self._default_utc_year
        self.sync_time = sync_time or self._default_sync_time
        self.ticks_diff = ticks_diff or self._default_ticks_diff
        self._lock = lock or __import__("_thread").allocate_lock()
        self.job_service = job_service
        self.before_delivery = before_delivery
        self.job_ledger = job_ledger or JobLedger(
            config.get("queue", {}).get("max_completed_ids", 100)
        )
        self.allow_cut = self.settings.get("allow_cut", False)
        self.client = None
        self.last_error = None
        self.last_connect_attempt_ms = None
        prefix = self.settings["topic_prefix"].strip("/")
        device_id = config["device_id"]
        self.jobs_topic = (f"{prefix}/{device_id}/jobs").encode()
        self.status_topic = (f"{prefix}/{device_id}/status").encode()
        self.print_jobs_topic = (f"{prefix}/{device_id}/print-jobs").encode()
        self.job_results_topic = (f"{prefix}/{device_id}/job-results").encode()

    @staticmethod
    def _default_client_factory(**settings):
        from . import mqtt_client as mqtt

        tls = settings.get("tls")
        if tls is None:
            return mqtt.MQTTClient(
                settings["client_id"],
                settings["host"],
                port=settings["port"],
                user=settings["username"],
                password=settings["password"],
                keepalive=settings["keepalive_seconds"],
                max_message_bytes=settings["max_message_bytes"],
                max_topic_bytes=settings["max_topic_bytes"],
            )
        ssl = __import__("ssl")
        return mqtt.MQTTClient(
            settings["client_id"],
            settings["host"],
            port=settings["port"],
            user=settings["username"],
            password=settings["password"],
            keepalive=settings["keepalive_seconds"],
            max_message_bytes=settings["max_message_bytes"],
            max_topic_bytes=settings["max_topic_bytes"],
            ssl=True,
            ssl_params={
                "cert_reqs": ssl.CERT_REQUIRED,
                "cadata": tls["ca_certificate"].encode("ascii"),
                "server_hostname": tls["server_hostname"],
            },
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
    def _default_utc_year():
        time = __import__("time")
        return time.gmtime()[0]

    @staticmethod
    def _default_sync_time():
        ntptime = __import__("ntptime")
        ntptime.settime()

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
        tls = self.tls
        if tls["enabled"]:
            try:
                clock_ready = self.utc_year() >= 2020
            except Exception:
                clock_ready = False
            if not clock_ready:
                try:
                    self.sync_time()
                    clock_ready = self.utc_year() >= 2020
                except Exception as exc:
                    self._set_state(None, f"MQTT_TLS_CLOCK_SYNC_FAILED: {exc}")
                    return
            if not clock_ready:
                self._set_state(None, "MQTT_TLS_CLOCK_NOT_READY")
                return
        try:
            settings = {
                "client_id": self.settings["client_id"],
                "host": self.settings["host"],
                "port": self.settings["port"],
                "username": self.settings["username"],
                "password": self.settings["password"],
                "keepalive_seconds": self.settings["keepalive_seconds"],
                "max_message_bytes": self.settings["max_message_bytes"],
                "max_topic_bytes": max(len(self.jobs_topic), len(self.print_jobs_topic)),
            }
            if tls["enabled"]:
                settings["tls"] = tls
            client = self.client_factory(**settings)
            client.set_callback(self._handle_message)
            client.connect()
            client.subscribe(self.jobs_topic, qos=1)
            client.subscribe(self.print_jobs_topic, qos=1)
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

    def _handle_message(self, topic, payload, retained=False):
        if retained:
            self.record_error("RETAINED_MQTT_MESSAGE")
            return
        if topic not in (self.jobs_topic, self.print_jobs_topic):
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
        if topic == self.jobs_topic:
            self._handle_probe(message)
        else:
            self._handle_job(message)

    def _publish(self, topic, response):
        client = self._get_client()
        if client is None:
            self.record_error("MQTT_NOT_CONNECTED")
            return
        client.publish(topic, json.dumps(response), qos=1, retain=False)
        self.record_error(None)

    def _handle_probe(self, message):
        if not self._valid_probe(message):
            self.record_error("INVALID_MQTT_PROBE")
            return
        self._publish(
            self.status_topic,
            {
                "schema_version": 1,
                "kind": "mqtt_probe_status",
                "probe_id": message["probe_id"],
                "device_id": self.config["device_id"],
                "status": "ok",
                "ts_ms": self.clock_ms(),
            },
        )

    def _handle_job(self, job):
        job_id = job.get("job_id") if isinstance(job, dict) else None
        if not isinstance(job_id, str) or not 1 <= len(job_id) <= 128:
            self.record_error("INVALID_MQTT_JOB")
            return
        if self.job_ledger.contains(job_id):
            self._publish(
                self.job_results_topic,
                {
                    "schema_version": "1",
                    "kind": "job_result",
                    "job_id": job_id,
                    "device_id": self.config["device_id"],
                    "status": "duplicate",
                    "error_code": "DUPLICATE_JOB",
                },
            )
            return
        if self.job_service is None:
            self.record_error("MQTT_JOB_DISABLED")
            return

        try:
            delivered = self.job_service.submit(
                job,
                allow_cut=self.allow_cut,
                before_delivery=self.before_delivery,
            )
            result = {
                "schema_version": "1",
                "kind": "job_result",
                "job_id": job_id,
                "device_id": self.config["device_id"],
                "status": "delivered_to_printer",
                "bytes_sent": delivered["bytes_sent"],
            }
        except RpcError as exc:
            result = self._error_result(job_id, exc.code, exc.bytes_sent)
        except Exception:
            result = self._error_result(job_id, "INTERNAL_ERROR")

        self.job_ledger.record(job_id)
        self._publish(self.job_results_topic, result)

    def _error_result(self, job_id, code, bytes_sent=None):
        if code not in JOB_RESULT_ERROR_CODES:
            code = "INTERNAL_ERROR"
        result = {
            "schema_version": "1",
            "kind": "job_result",
            "job_id": job_id,
            "device_id": self.config["device_id"],
            "status": "rejected" if code in _REJECTION_CODES else "failed",
            "error_code": code,
        }
        if isinstance(bytes_sent, int) and bytes_sent > 0:
            result["bytes_sent"] = bytes_sent
        return result

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
