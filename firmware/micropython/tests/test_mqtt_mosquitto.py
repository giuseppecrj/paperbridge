import json
import os
import shutil
import socket
import subprocess
import time
from pathlib import Path

import pytest

MqttTracer = __import__("src.mqtt_adapter", None, None, ("MqttTracer",)).MqttTracer

mosquitto = shutil.which("mosquitto")
mosquitto_passwd = shutil.which("mosquitto_passwd")


class PahoClient:
    def __init__(self, client_id, host, port, username, password, keepalive_seconds):
        mqtt = __import__("paho.mqtt.client", None, None, ("Client",))

        self.client = mqtt.Client(client_id=client_id, protocol=mqtt.MQTTv311)
        self.host = host
        self.port = port
        self.keepalive_seconds = keepalive_seconds
        self.client.username_pw_set(username, password)
        self.callback = None
        self.client.on_message = self._on_message

    def set_callback(self, callback):
        self.callback = callback

    def connect(self):
        self.client.connect(self.host, self.port, self.keepalive_seconds)

    def subscribe(self, topic, qos=0):
        self.client.subscribe(topic.decode("utf-8"), qos=qos)

    def check_msg(self):
        self.client.loop(timeout=0)

    def publish(self, topic, payload, qos=0, retain=False):
        self.client.publish(topic.decode("utf-8"), payload, qos=qos, retain=retain)

    def _on_message(self, _client, _userdata, message):
        if self.callback is not None:
            self.callback(message.topic.encode("utf-8"), message.payload)


def unused_port():
    with socket.socket() as value:
        value.bind(("127.0.0.1", 0))
        return value.getsockname()[1]


def wait_for_port(port):
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                return
        except OSError:
            time.sleep(0.02)
    pytest.fail("Mosquitto did not start")


@pytest.mark.skipif(
    not mosquitto or not mosquitto_passwd,
    reason="Mosquitto and mosquitto_passwd are required for this integration test",
)
def test_node_probe_round_trips_through_the_firmware_mqtt_tracer(tmp_path):
    assert mosquitto is not None
    assert mosquitto_passwd is not None
    port = unused_port()
    password_file = tmp_path / "passwd"
    username = "paperbridge-dev-001"
    password = "test-password"
    subprocess.run(
        [mosquitto_passwd, "-b", "-c", str(password_file), username, password],
        check=True,
    )
    config = tmp_path / "mosquitto.conf"
    config.write_text(
        f"listener {port} 127.0.0.1\n"
        "allow_anonymous false\n"
        f"password_file {password_file}\n"
        "persistence false\n"
    )
    broker = subprocess.Popen([mosquitto, "-c", str(config)])
    try:
        wait_for_port(port)
        tracer = MqttTracer(
            {
                "device_id": username,
                "mqtt": {
                    "host": "127.0.0.1",
                    "port": port,
                    "client_id": "paperbridge-device-test",
                    "username": username,
                    "password": password,
                    "keepalive_seconds": 30,
                    "retry_interval_ms": 10,
                    "max_message_bytes": 1024,
                    "topic_prefix": "v1/devices",
                },
            },
            type("Ethernet", (), {"status": lambda _self: {"link_up": True}})(),
            client_factory=PahoClient,
        )
        tracer.poll()
        process = subprocess.Popen(
            ["bun", "run", "mqtt:probe"],
            cwd=Path(__file__).resolve().parents[3],
            env={
                **os.environ,
                "PAPERBRIDGE_MQTT_HOST": "127.0.0.1",
                "PAPERBRIDGE_MQTT_PORT": str(port),
                "PAPERBRIDGE_MQTT_USERNAME": username,
                "PAPERBRIDGE_MQTT_PASSWORD": password,
                "PAPERBRIDGE_DEVICE_ID": username,
                "PAPERBRIDGE_MQTT_CLIENT_ID": "paperbridge-host-test",
            },
            stdout=subprocess.PIPE,
            text=True,
        )
        deadline = time.monotonic() + 3
        while process.poll() is None and time.monotonic() < deadline:
            tracer.poll()
            time.sleep(0.01)
        if process.poll() is None:
            process.kill()
            pytest.fail("Node MQTT probe timed out")
        assert process.returncode == 0
        assert process.stdout is not None
        assert json.loads(process.stdout.read())["status"] == "ok"
    finally:
        broker.terminate()
        broker.wait(timeout=3)
