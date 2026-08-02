import importlib.util
import json
import os
import shutil
import socket
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from urllib.request import Request, urlopen

import pytest
from src.escpos import EscPosRenderer
from src.print_coordinator import PrintCoordinator
from src.printer_transport import PrinterTransport

JobService = __import__("src.job_service", None, None, ("JobService",)).JobService
MqttTracer = __import__("src.mqtt_adapter", None, None, ("MqttTracer",)).MqttTracer

SIMULATOR_SPEC = importlib.util.spec_from_file_location(
    "paperbridge_printer_simulator", Path("tools/printer-simulator/server.py")
)
assert SIMULATOR_SPEC is not None and SIMULATOR_SPEC.loader is not None
simulator = importlib.util.module_from_spec(SIMULATOR_SPEC)
SIMULATOR_SPEC.loader.exec_module(simulator)

mosquitto = shutil.which("mosquitto")
mosquitto_passwd = shutil.which("mosquitto_passwd")


class ConnectedWiFi:
    def poll(self):
        return None

    def status(self):
        return {"connected": True}


class PahoClient:
    def __init__(self, client_id, host, port, username, password, keepalive_seconds):
        mqtt = __import__("paho.mqtt.client", None, None, ("Client",))

        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=client_id,
            protocol=mqtt.MQTTv311,
        )
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
            ConnectedWiFi(),
            client_factory=PahoClient,
        )
        tracer.poll()
        process = subprocess.Popen(
            ["node", "--import", "tsx", "src/main.ts"],
            cwd=Path(__file__).resolve().parents[3] / "apps" / "api",
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
            stderr=subprocess.PIPE,
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


def wait_for_api(port, process):
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        if process.poll() is not None:
            assert process.stderr is not None
            pytest.fail(f"API service exited before listening: {process.stderr.read().strip()}")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                return
        except OSError:
            time.sleep(0.02)
    pytest.fail("API service did not start")


@pytest.mark.skipif(
    not mosquitto or not mosquitto_passwd,
    reason="Mosquitto and mosquitto_passwd are required for this integration test",
)
def test_rest_and_mcp_jobs_round_trip_through_mqtt_firmware_and_printer_simulator(
    tmp_path,
):
    assert mosquitto is not None
    assert mosquitto_passwd is not None
    broker_port = unused_port()
    api_port = unused_port()
    printer_port = unused_port()
    username = "paperbridge-dev-001"
    password = "test-password"

    password_file = tmp_path / "passwd"
    subprocess.run(
        [mosquitto_passwd, "-b", "-c", str(password_file), username, password],
        check=True,
    )
    broker_config = tmp_path / "mosquitto.conf"
    broker_config.write_text(
        f"listener {broker_port} 127.0.0.1\n"
        "allow_anonymous false\n"
        f"password_file {password_file}\n"
        "persistence false\n"
    )
    broker = subprocess.Popen([mosquitto, "-c", str(broker_config)])

    simulator_args = SimpleNamespace(
        host="127.0.0.1",
        port=printer_port,
        capture_dir=tmp_path / "captures",
        accept_delay=0,
        read_delay=0,
        read_size=1024,
        close_after=0,
        reset_after=0,
    )
    simulator_ready = threading.Event()
    simulator_thread = threading.Thread(
        target=simulator.serve,
        args=(simulator_args, 2, simulator_ready),
        daemon=True,
    )
    simulator_thread.start()
    assert simulator_ready.wait(1)

    api = None
    try:
        wait_for_port(broker_port)
        firmware_config = {
            "device_id": username,
            "printer": {
                "host": "127.0.0.1",
                "port": printer_port,
                "connect_timeout_ms": 1000,
                "write_timeout_ms": 1000,
            },
            "mqtt": {
                "host": "127.0.0.1",
                "port": broker_port,
                "client_id": "paperbridge-device-test",
                "username": username,
                "password": password,
                "keepalive_seconds": 30,
                "retry_interval_ms": 10,
                "max_message_bytes": 1024,
                "topic_prefix": "v1/devices",
            },
        }
        job_service = JobService(
            firmware_config,
            PrintCoordinator(EscPosRenderer(), PrinterTransport(firmware_config)),
        )
        tracer = MqttTracer(
            firmware_config,
            ConnectedWiFi(),
            client_factory=PahoClient,
            job_service=job_service,
        )
        tracer.poll()

        api = subprocess.Popen(
            ["node", "--import", "tsx", "src/server.ts"],
            cwd=Path(__file__).resolve().parents[3] / "apps" / "api",
            env={
                **os.environ,
                "PAPERBRIDGE_API_HOST": "127.0.0.1",
                "PAPERBRIDGE_API_PORT": str(api_port),
                "PAPERBRIDGE_DEVICE_ID": username,
                "PAPERBRIDGE_MQTT_HOST": "127.0.0.1",
                "PAPERBRIDGE_MQTT_PORT": str(broker_port),
                "PAPERBRIDGE_MQTT_USERNAME": username,
                "PAPERBRIDGE_MQTT_PASSWORD": password,
                "PAPERBRIDGE_MQTT_CLIENT_ID": "paperbridge-api-test",
                "PAPERBRIDGE_JOB_RESULT_TIMEOUT_MS": "1000",
            },
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        wait_for_api(api_port, api)

        job = Path("packages/protocol/fixtures/print-job-v1/valid-text-feed.json").read_bytes()

        def submit_job():
            request = Request(
                f"http://127.0.0.1:{api_port}/api/jobs",
                data=job,
                headers={"content-type": "application/json"},
                method="POST",
            )
            with urlopen(request, timeout=3) as response:
                return response.status, json.loads(response.read())

        with ThreadPoolExecutor(max_workers=1) as executor:
            submitted = executor.submit(submit_job)
            deadline = time.monotonic() + 3
            while not submitted.done() and time.monotonic() < deadline:
                tracer.poll()
                time.sleep(0.01)
            status, result = submitted.result(timeout=0.1)

        assert status == 200
        assert result == {
            "schema_version": "1",
            "kind": "job_result",
            "job_id": "job-hello-001",
            "device_id": username,
            "status": "delivered_to_printer",
            "bytes_sent": 28,
        }

        mcp_content = {
            "kind": "receipt",
            "blocks": [{"type": "text", "text": "Hello from MCP"}],
        }
        mcp_client = subprocess.Popen(
            [
                "node",
                "--import",
                "tsx",
                "tests/support/call-mcp.ts",
                f"http://127.0.0.1:{api_port}/mcp",
                json.dumps(mcp_content),
            ],
            cwd=Path(__file__).resolve().parents[3] / "apps" / "api",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        deadline = time.monotonic() + 3
        while mcp_client.poll() is None and time.monotonic() < deadline:
            tracer.poll()
            time.sleep(0.01)
        if mcp_client.poll() is None:
            mcp_client.kill()
            pytest.fail("MCP client timed out")
        assert mcp_client.stderr is not None
        assert mcp_client.returncode == 0, mcp_client.stderr.read()
        assert mcp_client.stdout is not None
        mcp_response = json.loads(mcp_client.stdout.read())
        assert mcp_response["tools"] == ["paperbridge_print"]
        assert mcp_response["result"]["structuredContent"] == {
            "schema_version": "1",
            "kind": "job_result",
            "job_id": mcp_response["result"]["structuredContent"]["job_id"],
            "device_id": username,
            "status": "delivered_to_printer",
            "bytes_sent": 17,
        }

        simulator_thread.join(1)
        assert not simulator_thread.is_alive()
        assert {capture.read_bytes() for capture in (tmp_path / "captures").glob("*.bin")} == {
            b"\x1b@Hello from Paperbridge\n\n\n\n",
            b"\x1b@Hello from MCP\n",
        }
    finally:
        if api is not None:
            api.terminate()
            try:
                api.wait(timeout=3)
            except subprocess.TimeoutExpired:
                api.kill()
        broker.terminate()
        broker.wait(timeout=3)
        if simulator_thread.is_alive():
            with socket.create_connection(("127.0.0.1", printer_port), timeout=1):
                pass
            simulator_thread.join(1)
