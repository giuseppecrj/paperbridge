import json

import pytest

from hardware.hil import (
    CUT_AUTHORIZATION_TOKEN,
    OUTPUT_COMMANDS,
    SMOKE_COMMANDS,
    SOAK_COMMANDS,
    AcceptanceAborted,
    HardwareInTheLoop,
    NonInteractiveError,
    main,
    require_cli_port,
    run_acceptance,
    run_smoke,
    run_soak,
)


class FakeClock:
    def __init__(self, start=0.0, step=1.0):
        self._now = start
        self._step = step
        self.sleeps = []

    def time(self):
        value = self._now
        self._now += self._step
        return value

    def sleep(self, seconds):
        self.sleeps.append(seconds)


class ManualClock:
    def __init__(self, start=0.0):
        self.now = start
        self.sleeps = []

    def time(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


STATIC_STATUS = {
    "initialized": True,
    "active": True,
    "link_up": True,
    "raw_status": 3,
    "ifconfig": ["192.168.1.50", "255.255.255.0", "192.168.1.1", "1.1.1.1"],
}


class RecordingClient:
    def __init__(self, responses=None, errors=None):
        self.calls = []
        self.responses = dict(responses or {})
        self.errors = dict(errors or {})
        self._static_calls = 0

    def request(self, command, params=None):
        params = params or {}
        self.calls.append((command, params))
        if command in self.errors:
            raise self.errors[command]
        if command in self.responses:
            value = self.responses[command]
            return value(params) if callable(value) else value
        if command == "system.ping":
            return {"status": "ok"}
        if command == "system.info":
            return {
                "firmware_version": "0.1.0",
                "device_id": "paperbridge-dev-001",
                "implementation": "micropython",
                "memory": {"heap_allocated_bytes": 50_000, "heap_free_bytes": 8_000_000},
                "reset_cause": 1,
            }
        if command == "ethernet.initialize":
            return {"initialized": True, "active": True, "link_up": False}
        if command == "ethernet.configure_static":
            self._static_calls += 1
            return dict(STATIC_STATUS)
        if command == "ethernet.link_status":
            return {"link_up": True, "raw_status": 3}
        if command == "printer.probe":
            return {"reachable": True, "printer_endpoint": "192.168.1.87:9100"}
        if command == "printer.print_test":
            return {
                "status": "delivered_to_printer",
                "bytes_sent": 32,
                "printer_endpoint": "192.168.1.87:9100",
            }
        if command == "printer.feed_test":
            return {
                "status": "delivered_to_printer",
                "bytes_sent": 4,
                "printer_endpoint": "192.168.1.87:9100",
            }
        if command == "printer.cut_test":
            return {
                "status": "delivered_to_printer",
                "bytes_sent": 3,
                "printer_endpoint": "192.168.1.87:9100",
            }
        raise AssertionError(f"unexpected command {command}")


def _answers(*values):
    queue = list(values)

    def prompt(_message):
        assert queue, "unexpected prompt"
        return queue.pop(0)

    return prompt


def test_smoke_command_order_and_repeated_static_configuration():
    client = RecordingClient()
    evidence = run_smoke(
        port="/dev/cu.usbmodem101",
        client=client,
        clock=FakeClock(start=1_700_000_000.0),
        evidence_dir=None,
    )

    assert [command for command, _params in client.calls] == [
        "system.ping",
        "system.info",
        "ethernet.initialize",
        "ethernet.configure_static",
        "ethernet.configure_static",
        "ethernet.link_status",
        "printer.probe",
    ]
    assert client.calls.count(("ethernet.configure_static", {})) == 2
    assert evidence["outcome"] == "passed"
    assert evidence["port"] == "/dev/cu.usbmodem101"
    assert evidence["system_info"]["device_id"] == "paperbridge-dev-001"
    assert evidence["system_info"]["implementation"] == "micropython"
    assert evidence["link_status"]["link_up"] is True
    assert evidence["probe"]["reachable"] is True


def test_smoke_waits_for_link_negotiation():
    attempts = {"count": 0}

    def link_status(_params):
        attempts["count"] += 1
        return {"link_up": attempts["count"] == 3, "raw_status": 5 if attempts["count"] == 3 else 1}

    clock = FakeClock()
    client = RecordingClient(responses={"ethernet.link_status": link_status})
    evidence = run_smoke(
        port="/dev/cu.test",
        client=client,
        clock=clock,
        evidence_dir=None,
    )

    assert attempts["count"] == 3
    assert clock.sleeps == [0.5, 0.5]
    assert evidence["link_status"] == {"link_up": True, "raw_status": 5}


def test_smoke_has_no_output_commands():
    for command in SMOKE_COMMANDS:
        assert command not in OUTPUT_COMMANDS
    client = RecordingClient()
    run_smoke(port="/dev/cu.test", client=client, evidence_dir=None)
    issued = {command for command, _params in client.calls}
    assert issued.isdisjoint(OUTPUT_COMMANDS)


def test_soak_initializes_once_then_polls_without_output(tmp_path):
    client = RecordingClient()
    clock = ManualClock(start=1_700_000_000.0)

    evidence = run_soak(
        port="/dev/cu.test",
        duration_seconds=2,
        interval_seconds=1,
        client=client,
        clock=clock,
        evidence_dir=tmp_path,
        test_id="hil-soak-test",
    )

    assert [command for command, _params in client.calls[: len(SMOKE_COMMANDS)]] == list(
        SMOKE_COMMANDS
    )
    assert [command for command, _params in client.calls[len(SMOKE_COMMANDS) :]] == list(
        SOAK_COMMANDS
    ) * 2
    assert {command for command, _params in client.calls}.isdisjoint(OUTPUT_COMMANDS)
    assert clock.sleeps == [1, 1]
    assert evidence["outcome"] == "passed"
    assert evidence["summary"] == {
        "sample_count": 2,
        "first_heap_free_bytes": 8_000_000,
        "last_heap_free_bytes": 8_000_000,
        "minimum_heap_free_bytes": 8_000_000,
        "maximum_heap_free_bytes": 8_000_000,
        "heap_change_bytes": 0,
    }
    assert json.loads((tmp_path / "hil-soak-test.json").read_text())["outcome"] == "passed"


def test_interrupted_soak_writes_aborted_evidence(tmp_path):
    client = RecordingClient(errors={"system.ping": KeyboardInterrupt()})

    with pytest.raises(KeyboardInterrupt):
        run_soak(
            port="/dev/cu.test",
            duration_seconds=60,
            interval_seconds=1,
            client=client,
            clock=ManualClock(start=1_700_000_000.0),
            evidence_dir=tmp_path,
            test_id="hil-soak-interrupted",
        )

    evidence = json.loads((tmp_path / "hil-soak-interrupted.json").read_text())
    assert evidence["outcome"] == "aborted"
    assert evidence["error"] == "operator interrupted soak"
    assert evidence["summary"]["sample_count"] == 0


def test_smoke_rejects_bad_initialize():
    client = RecordingClient(responses={"ethernet.initialize": {"initialized": False}})
    with pytest.raises(RuntimeError, match="ethernet.initialize"):
        run_smoke(port="/dev/cu.test", client=client, evidence_dir=None)


def test_smoke_rejects_bad_static_address():
    client = RecordingClient(
        responses={"ethernet.configure_static": {"initialized": True, "ifconfig": None}}
    )
    with pytest.raises(RuntimeError, match="usable ifconfig"):
        run_smoke(port="/dev/cu.test", client=client, evidence_dir=None)


@pytest.mark.parametrize(
    "ifconfig",
    [
        ["0.0.0.0", "255.255.255.0", "0.0.0.0", "0.0.0.0"],
        ["192.168.1.50", "0.0.0.0", "0.0.0.0", "0.0.0.0"],
    ],
)
def test_smoke_rejects_unusable_static_address(ifconfig):
    client = RecordingClient(
        responses={"ethernet.configure_static": {"initialized": True, "ifconfig": ifconfig}}
    )
    with pytest.raises(RuntimeError, match="usable address"):
        run_smoke(port="/dev/cu.test", client=client, evidence_dir=None)


def test_smoke_rejects_static_mismatch():
    calls = {"n": 0}

    def varying(_params):
        calls["n"] += 1
        addr = list(STATIC_STATUS["ifconfig"])
        if calls["n"] == 2:
            addr[0] = "192.168.1.99"
        return {**STATIC_STATUS, "ifconfig": addr}

    client = RecordingClient(responses={"ethernet.configure_static": varying})
    with pytest.raises(RuntimeError, match="disagree"):
        run_smoke(port="/dev/cu.test", client=client, evidence_dir=None)


def test_smoke_rejects_non_micropython_info():
    client = RecordingClient(
        responses={
            "system.info": {
                "firmware_version": "0.1.0",
                "device_id": "x",
                "implementation": "cpython",
            }
        }
    )
    with pytest.raises(RuntimeError, match="micropython"):
        run_smoke(port="/dev/cu.test", client=client, evidence_dir=None)


@pytest.mark.parametrize(
    ("command", "result", "message"),
    [
        ("ethernet.link_status", {"link_up": False}, "link_up=true"),
        ("printer.probe", {"reachable": False}, "reachable=true"),
    ],
)
def test_smoke_rejects_soft_link_or_probe_failure(command, result, message):
    client = RecordingClient(responses={command: result})
    with pytest.raises(RuntimeError, match=message):
        run_smoke(
            port="/dev/cu.test",
            client=client,
            clock=FakeClock(),
            evidence_dir=None,
        )


def test_negative_text_confirmation_stops_before_cut(tmp_path):
    client = RecordingClient()
    with pytest.raises(AcceptanceAborted, match="text"):
        run_acceptance(
            port="/dev/cu.test",
            client=client,
            prompt=_answers("no"),
            is_interactive=True,
            clock=FakeClock(start=1_700_000_100.0),
            evidence_dir=tmp_path,
        )
    issued = [command for command, _params in client.calls]
    assert "printer.print_test" in issued
    assert "printer.feed_test" not in issued
    assert "printer.cut_test" not in issued
    evidence = json.loads(next(tmp_path.glob("*.json")).read_text())
    assert evidence["outcome"] == "aborted"
    assert evidence["abort_reason"] == "operator rejected physical text"


def test_negative_feed_confirmation_stops_before_cut(tmp_path):
    client = RecordingClient()
    with pytest.raises(AcceptanceAborted, match="feed"):
        run_acceptance(
            port="/dev/cu.test",
            client=client,
            prompt=_answers("yes", "no"),
            is_interactive=True,
            clock=FakeClock(start=1_700_000_200.0),
            evidence_dir=tmp_path,
        )
    issued = [command for command, _params in client.calls]
    assert "printer.feed_test" in issued
    assert "printer.cut_test" not in issued
    evidence = json.loads(next(tmp_path.glob("*.json")).read_text())
    assert evidence["outcome"] == "aborted"
    assert evidence["abort_reason"] == "operator rejected physical feed"


def test_wrong_cut_token_stops_before_cut(tmp_path):
    client = RecordingClient()
    with pytest.raises(AcceptanceAborted, match="cutter authorization"):
        run_acceptance(
            port="/dev/cu.test",
            client=client,
            prompt=_answers("yes", "yes", "cut"),
            is_interactive=True,
            clock=FakeClock(start=1_700_000_300.0),
            evidence_dir=tmp_path,
        )
    assert all(command != "printer.cut_test" for command, _ in client.calls)
    evidence = json.loads(next(tmp_path.glob("*.json")).read_text())
    assert evidence["outcome"] == "aborted"
    assert evidence["abort_reason"] == "cutter authorization token mismatch"


def test_explicit_token_sends_confirm_true_and_writes_evidence(tmp_path):
    client = RecordingClient()
    clock = FakeClock(start=1_700_000_400.0)
    evidence = run_acceptance(
        port="/dev/cu.usbmodem101",
        client=client,
        prompt=_answers("yes", "yes", CUT_AUTHORIZATION_TOKEN, "yes"),
        is_interactive=True,
        clock=clock,
        evidence_dir=tmp_path,
        test_id="hil-accept-fixed",
    )

    cut_calls = [params for command, params in client.calls if command == "printer.cut_test"]
    assert cut_calls == [{"confirm": True}]
    print_calls = [params for command, params in client.calls if command == "printer.print_test"]
    assert len(print_calls) == 1
    assert "hil-accept-fixed" in print_calls[0]["text"]

    path = tmp_path / "hil-accept-fixed.json"
    assert path.exists()
    on_disk = json.loads(path.read_text())
    assert on_disk["test_id"] == "hil-accept-fixed"
    assert on_disk["port"] == "/dev/cu.usbmodem101"
    assert on_disk["outcome"] == "passed"
    assert on_disk["system_info"]["device_id"] == "paperbridge-dev-001"
    assert on_disk["commands"][-1]["command"] == "printer.cut_test"
    assert on_disk["commands"][-1]["result"]["status"] == "delivered_to_printer"
    assert on_disk["operator"]["text_observed"] is True
    assert on_disk["operator"]["feed_observed"] is True
    assert on_disk["operator"]["cut_observed"] is True
    assert evidence["started_at"] == "2023-11-14T22:20:00+00:00"


def test_bad_print_delivery_stops_before_physical_and_later_output(tmp_path):
    client = RecordingClient(
        responses={
            "printer.print_test": {
                "status": "failed",
                "error": "connection refused",
            }
        }
    )
    with pytest.raises(RuntimeError, match="delivered_to_printer"):
        run_acceptance(
            port="/dev/cu.test",
            client=client,
            prompt=_answers(),  # no prompts should fire
            is_interactive=True,
            evidence_dir=tmp_path,
            test_id="hil-bad-print",
        )
    issued = [command for command, _ in client.calls]
    assert "printer.print_test" in issued
    assert "printer.feed_test" not in issued
    assert "printer.cut_test" not in issued
    evidence = json.loads((tmp_path / "hil-bad-print.json").read_text())
    assert evidence["outcome"] == "failed"
    assert "delivered_to_printer" in evidence["error"]
    assert "text_observed" not in evidence["operator"]


def test_bad_feed_delivery_stops_before_cut(tmp_path):
    client = RecordingClient(
        responses={
            "printer.feed_test": {"status": "unreachable", "error": "timeout"},
        }
    )
    with pytest.raises(RuntimeError, match="delivered_to_printer"):
        run_acceptance(
            port="/dev/cu.test",
            client=client,
            prompt=_answers("yes"),
            is_interactive=True,
            evidence_dir=tmp_path,
            test_id="hil-bad-feed",
        )
    issued = [command for command, _ in client.calls]
    assert "printer.feed_test" in issued
    assert "printer.cut_test" not in issued
    evidence = json.loads((tmp_path / "hil-bad-feed.json").read_text())
    assert evidence["outcome"] == "failed"


def test_bad_cut_delivery_fails_before_physical_cut_prompt(tmp_path):
    client = RecordingClient(responses={"printer.cut_test": {"status": "failed"}})
    with pytest.raises(RuntimeError, match="delivered_to_printer"):
        run_acceptance(
            port="/dev/cu.test",
            client=client,
            prompt=_answers("yes", "yes", CUT_AUTHORIZATION_TOKEN),
            is_interactive=True,
            evidence_dir=tmp_path,
            test_id="hil-bad-cut",
        )
    evidence = json.loads((tmp_path / "hil-bad-cut.json").read_text())
    assert evidence["outcome"] == "failed"
    assert evidence["commands"][-1]["command"] == "printer.cut_test"
    assert "cut_observed" not in evidence["operator"]


def test_acceptance_refuses_noninteractive_stdin_without_prompt_seam():
    client = RecordingClient()
    with pytest.raises(NonInteractiveError):
        run_acceptance(
            port="/dev/cu.test",
            client=client,
            is_interactive=False,
            evidence_dir=None,
        )
    assert client.calls == []


def test_noninteractive_refusal_writes_failed_evidence(tmp_path):
    client = RecordingClient()
    with pytest.raises(NonInteractiveError):
        run_acceptance(
            port="/dev/cu.test",
            client=client,
            is_interactive=False,
            evidence_dir=tmp_path,
            test_id="hil-noninteractive",
        )
    assert client.calls == []
    evidence = json.loads((tmp_path / "hil-noninteractive.json").read_text())
    assert evidence["outcome"] == "failed"
    assert evidence["kind"] == "acceptance"
    assert (
        "interactive" in evidence["error"].lower() or "non-interactive" in evidence["error"].lower()
    )


def test_ordinary_unit_path_never_exposes_cutter_bypass():
    client = RecordingClient()
    harness = HardwareInTheLoop(port="/dev/cu.test", client=client, is_interactive=False)
    with pytest.raises(NonInteractiveError):
        harness.acceptance()
    assert all(command != "printer.cut_test" for command, _ in client.calls)


def test_failed_smoke_writes_failed_evidence(tmp_path):
    client = RecordingClient(errors={"printer.probe": RuntimeError("link ok but probe failed")})
    with pytest.raises(RuntimeError, match="probe failed"):
        run_smoke(
            port="/dev/cu.test",
            client=client,
            clock=FakeClock(start=1_700_000_500.0),
            evidence_dir=tmp_path,
            test_id="hil-smoke-fail",
        )
    evidence = json.loads((tmp_path / "hil-smoke-fail.json").read_text())
    assert evidence["outcome"] == "failed"
    assert "probe failed" in evidence["error"]
    assert "secret" not in json.dumps(evidence).lower()


def test_smoke_validates_expected_results():
    client = RecordingClient(responses={"system.ping": {"status": "nope"}})
    with pytest.raises(RuntimeError, match="system.ping"):
        run_smoke(port="/dev/cu.test", client=client, evidence_dir=None)


def test_require_cli_port_rejects_missing():
    with pytest.raises(ValueError, match="--port is required"):
        require_cli_port("")
    with pytest.raises(ValueError, match="--port is required"):
        require_cli_port(None)


def test_require_cli_port_rejects_numeric_vid_pid():
    with pytest.raises(ValueError, match="VID/PID"):
        require_cli_port("303a")
    with pytest.raises(ValueError, match="VID/PID"):
        require_cli_port("0x303a")
    with pytest.raises(ValueError, match="VID/PID"):
        require_cli_port("9100")


def test_require_cli_port_rejects_nonexistent_path(tmp_path):
    missing = tmp_path / "no-such-serial"
    with pytest.raises(ValueError, match="does not exist"):
        require_cli_port(str(missing))


def test_require_cli_port_accepts_existing_path(tmp_path):
    port = tmp_path / "cu.usbmodem101"
    port.write_text("")
    assert require_cli_port(str(port)) == str(port)


def test_main_rejects_missing_port(monkeypatch, capsys):
    monkeypatch.delenv("PORT", raising=False)
    monkeypatch.delenv("PAPERBRIDGE_PORT", raising=False)
    assert main(["smoke"]) == 1
    err = capsys.readouterr().err
    assert "--port is required" in err


def test_main_requires_explicit_port_even_when_environment_is_set(monkeypatch, capsys, tmp_path):
    port = tmp_path / "cu.usbmodem101"
    port.write_text("")
    monkeypatch.setenv("PORT", str(port))
    monkeypatch.setenv("PAPERBRIDGE_PORT", str(port))
    assert main(["smoke"]) == 1
    assert "--port is required" in capsys.readouterr().err


def test_main_rejects_numeric_port(monkeypatch, capsys):
    monkeypatch.delenv("PORT", raising=False)
    monkeypatch.delenv("PAPERBRIDGE_PORT", raising=False)
    assert main(["smoke", "--port", "303a"]) == 1
    err = capsys.readouterr().err
    assert "VID/PID" in err


def test_main_rejects_nonexistent_port(monkeypatch, capsys, tmp_path):
    monkeypatch.delenv("PORT", raising=False)
    monkeypatch.delenv("PAPERBRIDGE_PORT", raising=False)
    missing = tmp_path / "missing-port"
    assert main(["smoke", "--port", str(missing)]) == 1
    err = capsys.readouterr().err
    assert "does not exist" in err


def test_main_usage_without_mode():
    assert main([]) == 2
