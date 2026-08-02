import json
from argparse import Namespace

from paperbridge_cli.main import _rpc


def test_ping_mapping_does_not_require_cut_confirmation_argument():
    assert _rpc(Namespace(group="device", action="ping")) == ("system.ping", {})


def test_wifi_status_mapping():
    assert _rpc(Namespace(group="wifi", action="status")) == ("wifi.status", {})


def test_mqtt_status_mapping():
    assert _rpc(Namespace(group="mqtt", action="status")) == ("mqtt.status", {})


def test_ethernet_reconnect_mapping_requires_explicit_confirmation():
    assert _rpc(Namespace(group="ethernet", action="reconnect", confirm=True)) == (
        "ethernet.reconnect",
        {"confirm": True},
    )


def test_submit_job_loads_json_file_and_keeps_cut_authorization_separate(tmp_path):
    job = {"job_id": "job-1"}
    job_path = tmp_path / "job.json"
    job_path.write_text(json.dumps(job))

    assert _rpc(Namespace(group="job", action="submit", job_file=job_path, allow_cut=False)) == (
        "job.submit",
        {"job": job, "allow_cut": False},
    )
