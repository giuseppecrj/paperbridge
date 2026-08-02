"""Opt-in hardware-in-the-loop smoke, acceptance, and soak harness.

Never called by ordinary unit tests. Smoke and soak never print/feed/cut/reboot.
Acceptance requires an interactive operator (or an injected prompt seam).
"""

from __future__ import annotations

import json
import sys
import uuid
from contextlib import nullcontext
from datetime import datetime, timezone
from pathlib import Path

from paperbridge_cli.serial_client import DeviceError, SerialClient

REPO_ROOT = Path(__file__).resolve().parents[2]

SMOKE_COMMANDS = (
    "system.ping",
    "system.info",
    "ethernet.initialize",
    "ethernet.configure_static",
    "ethernet.configure_static",
    "ethernet.link_status",
    "printer.probe",
)
SOAK_COMMANDS = (
    "system.ping",
    "system.info",
    "ethernet.link_status",
    "printer.probe",
)
OUTPUT_COMMANDS = frozenset(
    {
        "printer.print_test",
        "printer.feed_test",
        "printer.cut_test",
        "system.reboot",
    }
)
CUT_AUTHORIZATION_TOKEN = "CUT"  # exact interactive token; no noninteractive bypass
LINK_ATTEMPTS = 20
LINK_RETRY_SECONDS = 0.5
SOAK_DURATION_SECONDS = 72 * 60 * 60
SOAK_INTERVAL_SECONDS = 60
SOAK_CHECKPOINT_SECONDS = 60 * 60


class NonInteractiveError(RuntimeError):
    """Acceptance refused because stdin is not interactive and no prompt seam was injected."""


class AcceptanceAborted(RuntimeError):
    """Operator rejected a physical confirmation or failed cutter authorization."""


class _RealClock:
    def time(self):
        import time

        return time.time()

    def sleep(self, seconds):
        import time

        time.sleep(seconds)


def _iso(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _default_prompt(message):
    return input(message)


def _default_is_interactive():
    return sys.stdin.isatty()


def _truthy(answer):
    return answer.strip().lower() in {"y", "yes"}


def _usable_address(result):
    """Return a comparable address tuple from an ethernet status/result object."""
    addr = result.get("ifconfig")
    if not isinstance(addr, (list, tuple)) or len(addr) < 2:
        raise RuntimeError(
            f"ethernet.configure_static expected usable ifconfig address tuple, got {result!r}"
        )
    ip, netmask = addr[0], addr[1]
    if (
        not isinstance(ip, str)
        or not isinstance(netmask, str)
        or ip == "0.0.0.0"
        or netmask == "0.0.0.0"
    ):
        raise RuntimeError(
            f"ethernet.configure_static expected usable address/netmask, got {result!r}"
        )
    return tuple(addr)


def _require_delivered(command, result):
    if not isinstance(result, dict) or result.get("status") != "delivered_to_printer":
        raise RuntimeError(f"{command} expected status=delivered_to_printer, got {result!r}")


class HardwareInTheLoop:
    def __init__(
        self,
        port,
        client=None,
        prompt=None,
        is_interactive=None,
        clock=None,
        evidence_dir=None,
        test_id=None,
    ):
        self.port = port
        self.client = client
        self.prompt = prompt if prompt is not None else _default_prompt
        if is_interactive is None:
            self.is_interactive = _default_is_interactive()
        else:
            self.is_interactive = is_interactive
        self.clock = clock or _RealClock()
        # None means do not write; CLI main passes captures/hardware.
        self.evidence_dir = Path(evidence_dir) if evidence_dir is not None else None
        self.test_id = test_id
        self._owns_client = client is None

    def _client_context(self):
        if self._owns_client:
            return SerialClient(self.port)
        return nullcontext(self.client)

    def _new_evidence(self, kind):
        started = self.clock.time()
        test_id = self.test_id or f"hil-{kind}-{uuid.uuid4().hex[:12]}"
        return {
            "test_id": test_id,
            "kind": kind,
            "port": self.port,
            "started_at": _iso(started),
            "finished_at": None,
            "outcome": "running",
            "system_info": None,
            "link_status": None,
            "probe": None,
            "commands": [],
            "operator": {},
            "error": None,
            "abort_reason": None,
        }

    def _record_command(self, evidence, command, params, result=None, error=None):
        entry = {
            "command": command,
            "params": params,
            "ok": error is None,
        }
        if result is not None:
            entry["result"] = result
        if error is not None:
            entry["error"] = str(error)
        evidence["commands"].append(entry)

    def _save_evidence(self, evidence):
        if self.evidence_dir is None:
            return None
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        path = self.evidence_dir / f"{evidence['test_id']}.json"
        path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
        return path

    def _write_evidence(self, evidence):
        evidence["finished_at"] = _iso(self.clock.time())
        return self._save_evidence(evidence)

    def _request(self, client, evidence, command, params=None):
        params = params or {}
        try:
            result = client.request(command, params)
        except Exception as exc:
            self._record_command(evidence, command, params, error=exc)
            raise
        self._record_command(evidence, command, params, result=result)
        return result

    def _validate_smoke_step(self, command, result, static_addresses):
        if command == "system.ping" and result.get("status") != "ok":
            raise RuntimeError(f"system.ping expected status=ok, got {result!r}")
        if command == "system.info":
            if not isinstance(result, dict):
                raise RuntimeError(f"system.info expected object, got {result!r}")
            if result.get("implementation") != "micropython":
                raise RuntimeError(
                    f"system.info expected implementation=micropython, got {result!r}"
                )
        if command == "ethernet.initialize" and (
            not isinstance(result, dict) or result.get("initialized") not in (True,)
        ):
            raise RuntimeError(f"ethernet.initialize expected initialized=true, got {result!r}")
        if command == "ethernet.configure_static":
            static_addresses.append(_usable_address(result))
        if command == "printer.probe" and not result.get("reachable"):
            raise RuntimeError(f"printer.probe expected reachable=true, got {result!r}")

    def _wait_for_link(self, client, evidence):
        result = None
        for attempt in range(LINK_ATTEMPTS):
            result = self._request(client, evidence, "ethernet.link_status", {})
            if isinstance(result, dict) and result.get("link_up"):
                return result
            if attempt < LINK_ATTEMPTS - 1:
                self.clock.sleep(LINK_RETRY_SECONDS)
        raise RuntimeError(f"ethernet.link_status expected link_up=true, got {result!r}")

    def _run_smoke_commands(self, client, evidence):
        static_addresses = []
        for command in SMOKE_COMMANDS:
            if command == "ethernet.link_status":
                result = self._wait_for_link(client, evidence)
            else:
                result = self._request(client, evidence, command, {})
                self._validate_smoke_step(command, result, static_addresses)
            if command == "system.info":
                evidence["system_info"] = result
            elif command == "ethernet.link_status":
                evidence["link_status"] = result
            elif command == "printer.probe":
                evidence["probe"] = result
        if len(static_addresses) != 2:
            raise RuntimeError(
                f"expected two ethernet.configure_static results, got {len(static_addresses)}"
            )
        if static_addresses[0] != static_addresses[1]:
            raise RuntimeError(
                "ethernet.configure_static results disagree "
                f"(first={static_addresses[0]!r}, second={static_addresses[1]!r})"
            )

    def smoke(self):
        evidence = self._new_evidence("smoke")
        try:
            with self._client_context() as client:
                self._run_smoke_commands(client, evidence)
                evidence["outcome"] = "passed"
                return evidence
        except Exception as exc:
            evidence["outcome"] = "failed"
            evidence["error"] = str(exc)
            raise
        finally:
            self._write_evidence(evidence)

    def soak(
        self,
        duration_seconds: float = SOAK_DURATION_SECONDS,
        interval_seconds: float = SOAK_INTERVAL_SECONDS,
    ):
        if duration_seconds <= 0:
            raise ValueError("soak duration must be greater than zero")
        if interval_seconds <= 0:
            raise ValueError("soak interval must be greater than zero")

        evidence = self._new_evidence("soak")
        evidence["duration_seconds"] = duration_seconds
        evidence["interval_seconds"] = interval_seconds
        evidence["samples"] = []
        evidence["summary"] = None
        checkpoint_every = max(1, round(SOAK_CHECKPOINT_SECONDS / interval_seconds))
        try:
            deadline = self.clock.time() + duration_seconds
            with self._client_context() as client:
                self._run_smoke_commands(client, evidence)
                while True:
                    observed_at = self.clock.time()
                    if observed_at >= deadline:
                        break

                    results = {}
                    for command in SOAK_COMMANDS:
                        result = self._request(client, evidence, command, {})
                        if command == "ethernet.link_status":
                            if not isinstance(result, dict) or not result.get("link_up"):
                                raise RuntimeError(
                                    f"ethernet.link_status expected link_up=true, got {result!r}"
                                )
                        else:
                            self._validate_smoke_step(command, result, [])
                        results[command] = result

                    info = results["system.info"]
                    memory = info.get("memory")
                    heap_free = memory.get("heap_free_bytes") if isinstance(memory, dict) else None
                    if not isinstance(heap_free, int):
                        raise RuntimeError(
                            "system.info expected integer memory.heap_free_bytes during soak, "
                            f"got {info!r}"
                        )
                    if "reset_cause" not in info:
                        raise RuntimeError(
                            f"system.info expected reset_cause during soak, got {info!r}"
                        )

                    link = results["ethernet.link_status"]
                    probe = results["printer.probe"]
                    evidence["samples"].append(
                        {
                            "sequence": len(evidence["samples"]) + 1,
                            "observed_at": _iso(observed_at),
                            "heap_allocated_bytes": memory.get("heap_allocated_bytes"),
                            "heap_free_bytes": heap_free,
                            "reset_cause": info["reset_cause"],
                            "link_up": link["link_up"],
                            "raw_status": link.get("raw_status"),
                            "printer_reachable": probe["reachable"],
                            "printer_endpoint": probe.get("printer_endpoint"),
                        }
                    )
                    if len(evidence["samples"]) % checkpoint_every == 0:
                        self._save_evidence(evidence)

                    remaining = deadline - self.clock.time()
                    if remaining > 0:
                        self.clock.sleep(min(interval_seconds, remaining))

                evidence["outcome"] = "passed"
                return evidence
        except KeyboardInterrupt:
            evidence["outcome"] = "aborted"
            evidence["error"] = "operator interrupted soak"
            raise
        except Exception as exc:
            evidence["outcome"] = "failed"
            evidence["error"] = str(exc)
            raise
        finally:
            heaps = [sample["heap_free_bytes"] for sample in evidence["samples"]]
            evidence["summary"] = {
                "sample_count": len(heaps),
                "first_heap_free_bytes": heaps[0] if heaps else None,
                "last_heap_free_bytes": heaps[-1] if heaps else None,
                "minimum_heap_free_bytes": min(heaps) if heaps else None,
                "maximum_heap_free_bytes": max(heaps) if heaps else None,
                "heap_change_bytes": heaps[-1] - heaps[0] if heaps else None,
            }
            self._write_evidence(evidence)

    def _require_interactive(self):
        # Injected prompt still needs an explicit interactive flag so ordinary
        # unit tests cannot accidentally drive the cutter path.
        if not self.is_interactive and self.prompt is _default_prompt:
            raise NonInteractiveError(
                "hardware acceptance requires an interactive terminal "
                "(or an injected prompt seam with is_interactive=True)"
            )
        if not self.is_interactive:
            raise NonInteractiveError(
                "hardware acceptance refuses non-interactive stdin; "
                "inject is_interactive=True only from dedicated HIL tests"
            )

    def _confirm_yes(self, evidence, key, message, abort_reason):
        answer = self.prompt(message)
        evidence["operator"][key] = _truthy(answer)
        evidence["operator"][f"{key}_raw"] = answer.strip()
        if not evidence["operator"][key]:
            raise AcceptanceAborted(abort_reason)

    def acceptance(self):
        # Evidence first so noninteractive refusal is still recorded on disk.
        evidence = self._new_evidence("acceptance")
        try:
            self._require_interactive()
            with self._client_context() as client:
                self._run_smoke_commands(client, evidence)

                text = (
                    f"Paperbridge HIL acceptance {evidence['test_id']} at {evidence['started_at']}"
                )
                print_result = self._request(client, evidence, "printer.print_test", {"text": text})
                _require_delivered("printer.print_test", print_result)
                evidence["operator"]["print_text"] = text
                evidence["operator"]["print_delivery"] = print_result
                self._confirm_yes(
                    evidence,
                    "text_observed",
                    "Did the printer produce the expected text receipt? [yes/no]: ",
                    "operator rejected physical text",
                )

                feed_result = self._request(client, evidence, "printer.feed_test", {})
                _require_delivered("printer.feed_test", feed_result)
                evidence["operator"]["feed_delivery"] = feed_result
                self._confirm_yes(
                    evidence,
                    "feed_observed",
                    "Did the printer feed paper as expected? [yes/no]: ",
                    "operator rejected physical feed",
                )

                token = self.prompt(
                    f'Type exactly "{CUT_AUTHORIZATION_TOKEN}" to authorize printer.cut_test '
                    "(anything else aborts): "
                )
                accepted = token.strip() == CUT_AUTHORIZATION_TOKEN
                evidence["operator"]["cut_token_accepted"] = accepted
                if not accepted:
                    raise AcceptanceAborted("cutter authorization token mismatch")

                cut_result = self._request(client, evidence, "printer.cut_test", {"confirm": True})
                _require_delivered("printer.cut_test", cut_result)
                evidence["operator"]["cut_delivery"] = cut_result
                self._confirm_yes(
                    evidence,
                    "cut_observed",
                    "Did the printer perform a partial cut as expected? [yes/no]: ",
                    "operator rejected physical cut",
                )

                evidence["outcome"] = "passed"
                return evidence
        except AcceptanceAborted as exc:
            evidence["outcome"] = "aborted"
            evidence["abort_reason"] = str(exc)
            raise
        except Exception as exc:
            evidence["outcome"] = "failed"
            evidence["error"] = str(exc)
            raise
        finally:
            self._write_evidence(evidence)


def run_smoke(
    port,
    client=None,
    clock=None,
    evidence_dir=None,
    test_id=None,
):
    return HardwareInTheLoop(
        port=port,
        client=client,
        clock=clock,
        evidence_dir=evidence_dir,
        test_id=test_id,
    ).smoke()


def run_soak(
    port,
    duration_seconds: float = SOAK_DURATION_SECONDS,
    interval_seconds: float = SOAK_INTERVAL_SECONDS,
    client=None,
    clock=None,
    evidence_dir=None,
    test_id=None,
):
    return HardwareInTheLoop(
        port=port,
        client=client,
        clock=clock,
        evidence_dir=evidence_dir,
        test_id=test_id,
    ).soak(duration_seconds=duration_seconds, interval_seconds=interval_seconds)


def run_acceptance(
    port,
    client=None,
    prompt=None,
    is_interactive=None,
    clock=None,
    evidence_dir=None,
    test_id=None,
):
    return HardwareInTheLoop(
        port=port,
        client=client,
        prompt=prompt,
        is_interactive=is_interactive,
        clock=clock,
        evidence_dir=evidence_dir,
        test_id=test_id,
    ).acceptance()


def require_cli_port(port):
    """Validate a CLI-supplied serial device path.

    Injected unit APIs may still use fake ports; this guard is for main() only.
    """
    if not port:
        raise ValueError("--port is required (or run the just recipe with PORT set)")
    text = str(port).strip()
    if not text:
        raise ValueError("--port is required (or run the just recipe with PORT set)")
    # Reject bare numbers / hex that look like USB VID/PID selections.
    hex_body = text[2:] if text[:2].lower() == "0x" else text
    if hex_body and all(c in "0123456789abcdefABCDEF" for c in hex_body):
        raise ValueError(
            f"PORT must be a serial device path, not a numeric VID/PID value: {text!r}"
        )
    path = Path(text)
    if not path.exists():
        raise ValueError(f"PORT does not exist: {text}")
    return text


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] not in {"smoke", "acceptance", "soak"}:
        print(
            "usage: uv run python tools/hardware/hil.py smoke|acceptance|soak --port PORT "
            "[--duration-seconds N --interval-seconds N]",
            file=sys.stderr,
        )
        return 2
    mode = argv[0]
    port = None
    duration_seconds = SOAK_DURATION_SECONDS
    interval_seconds = SOAK_INTERVAL_SECONDS
    args = argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--port" and i + 1 < len(args):
            port = args[i + 1]
            i += 2
            continue
        if mode == "soak" and args[i] == "--duration-seconds" and i + 1 < len(args):
            try:
                duration_seconds = float(args[i + 1])
            except ValueError:
                print(f"invalid duration: {args[i + 1]!r}", file=sys.stderr)
                return 2
            i += 2
            continue
        if mode == "soak" and args[i] == "--interval-seconds" and i + 1 < len(args):
            try:
                interval_seconds = float(args[i + 1])
            except ValueError:
                print(f"invalid interval: {args[i + 1]!r}", file=sys.stderr)
                return 2
            i += 2
            continue
        print(f"unknown argument: {args[i]}", file=sys.stderr)
        return 2
    evidence_dir = REPO_ROOT / "captures" / "hardware"
    try:
        port = require_cli_port(port)
        if mode == "smoke":
            evidence = run_smoke(port=port, evidence_dir=evidence_dir)
        elif mode == "soak":
            evidence = run_soak(
                port=port,
                duration_seconds=duration_seconds,
                interval_seconds=interval_seconds,
                evidence_dir=evidence_dir,
            )
        else:
            evidence = run_acceptance(port=port, evidence_dir=evidence_dir)
        print(json.dumps({"ok": True, "test_id": evidence["test_id"]}, indent=2))
        return 0
    except (AcceptanceAborted, NonInteractiveError, DeviceError, RuntimeError, ValueError) as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
