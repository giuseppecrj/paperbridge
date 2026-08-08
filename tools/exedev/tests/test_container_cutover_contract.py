import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[3]
OPERATOR = ROOT / "tools/exedev/cutover_operator.py"
RUNBOOK = ROOT / "docs/exedev-container-cutover.md"
JUSTFILE = ROOT / "justfile"
DOMAIN = "api.paperbridge.tech"
PRODUCTION = "paperbridge-prod"
CANDIDATE = "paperbridge-api"


def private_share(vm: str) -> dict[str, object]:
    return {
        "links": [],
        "port": 3000,
        "status": "private",
        "team_access": False,
        "team_shelley": False,
        "team_ssh": False,
        "teams": [],
        "users": [],
        "vm_name": vm,
    }


def write_fakes(tmp_path: Path, route: str | None = PRODUCTION):
    state_path = tmp_path / "state.json"
    log_path = tmp_path / "mutations.log"
    state_path.write_text(
        json.dumps(
            {
                "domains": [] if route is None else [{"domain": DOMAIN, "vm_name": route}],
                "shares": {
                    PRODUCTION: private_share(PRODUCTION),
                    CANDIDATE: private_share(CANDIDATE),
                },
            }
        )
    )

    control = tmp_path / "control"
    control.write_text(
        """#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

state_path = Path(os.environ["PAPERBRIDGE_TEST_ROUTE_STATE"])
log_path = Path(os.environ["PAPERBRIDGE_TEST_ROUTE_LOG"])
state = json.loads(state_path.read_text())
args = sys.argv[1:]

if args == ["domain", "ls", "-a", "--json"]:
    print(json.dumps({"domains": state["domains"]}))
elif len(args) == 4 and args[:2] == ["share", "show"] and args[3] == "--json":
    print(json.dumps(state["shares"][args[2]]))
elif len(args) == 4 and args[:2] == ["domain", "rm"]:
    vm, domain = args[2:]
    expected = {"domain": domain, "vm_name": vm}
    if expected not in state["domains"]:
        raise SystemExit(1)
    state["domains"].remove(expected)
    log_path.open("a").write(" ".join(args) + "\\n")
elif len(args) == 4 and args[:2] == ["domain", "add"]:
    vm, domain = args[2:]
    if any(item["domain"] == domain for item in state["domains"]):
        raise SystemExit(1)
    state["domains"].append({"domain": domain, "vm_name": vm})
    log_path.open("a").write(" ".join(args) + "\\n")
elif len(args) == 3 and args[:2] == ["share", "set-private"]:
    state["shares"][args[2]]["status"] = "private"
    log_path.open("a").write(" ".join(args) + "\\n")
else:
    raise SystemExit(2)

state_path.write_text(json.dumps(state))
"""
    )
    control.chmod(0o755)

    dig = tmp_path / "dig"
    dig.write_text(
        """#!/bin/sh
printf '%s.\\n' "$PAPERBRIDGE_TEST_DNS_CNAME"
"""
    )
    dig.chmod(0o755)

    env = os.environ.copy()
    env.update(
        {
            "PAPERBRIDGE_EXEDEV_CONTROL_BIN": str(control),
            "PAPERBRIDGE_DIG_BIN": str(dig),
            "PAPERBRIDGE_TEST_ROUTE_LOG": str(log_path),
            "PAPERBRIDGE_TEST_ROUTE_STATE": str(state_path),
        }
    )
    return env, state_path, log_path


def run_operator(mode: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(OPERATOR), mode],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_route_activation_requires_exact_confirmation_before_preflight(tmp_path):
    env, _, log = write_fakes(tmp_path)
    env["PAPERBRIDGE_TEST_DNS_CNAME"] = f"{CANDIDATE}.exe.xyz"

    missing = run_operator("activate", env)
    assert missing.returncode == 2
    assert "EXEDEV_CONFIRM_ROUTE must equal" in missing.stderr
    assert not log.exists()

    env["EXEDEV_CONFIRM_ROUTE"] = "wrong-route"
    wrong = run_operator("activate", env)
    assert wrong.returncode == 2
    assert "EXEDEV_CONFIRM_ROUTE must equal" in wrong.stderr
    assert not log.exists()


@pytest.mark.parametrize("unsafe_state", ["dns", "domain", "share"])
def test_route_activation_rejects_unexpected_state_without_mutation(tmp_path, unsafe_state):
    route = CANDIDATE if unsafe_state == "domain" else PRODUCTION
    env, state_path, log = write_fakes(tmp_path, route)
    env["EXEDEV_CONFIRM_ROUTE"] = f"{PRODUCTION}:{DOMAIN}->{CANDIDATE}"
    env["PAPERBRIDGE_TEST_DNS_CNAME"] = (
        f"{PRODUCTION}.exe.xyz" if unsafe_state == "dns" else f"{CANDIDATE}.exe.xyz"
    )
    if unsafe_state == "share":
        state = json.loads(state_path.read_text())
        state["shares"][CANDIDATE]["status"] = "public"
        state_path.write_text(json.dumps(state))

    refused = run_operator("activate", env)

    assert refused.returncode == 1
    assert not log.exists()


def test_route_activation_moves_only_the_expected_private_registration(tmp_path):
    env, state_path, log = write_fakes(tmp_path)
    env["EXEDEV_CONFIRM_ROUTE"] = f"{PRODUCTION}:{DOMAIN}->{CANDIDATE}"
    env["PAPERBRIDGE_TEST_DNS_CNAME"] = f"{CANDIDATE}.exe.xyz"

    activated = run_operator("activate", env)

    assert activated.returncode == 0, activated.stderr
    assert activated.stdout == (
        f"route_vm={CANDIDATE}\ndomain={DOMAIN}\ncname={CANDIDATE}.exe.xyz\nprivate=true\n"
    )
    assert log.read_text().splitlines() == [
        f"domain rm {PRODUCTION} {DOMAIN}",
        f"domain add {CANDIDATE} {DOMAIN}",
        f"share set-private {CANDIDATE}",
        f"share set-private {PRODUCTION}",
    ]
    state = json.loads(state_path.read_text())
    assert state["domains"] == [{"domain": DOMAIN, "vm_name": CANDIDATE}]


def test_route_restore_reverses_only_the_expected_private_registration(tmp_path):
    env, state_path, log = write_fakes(tmp_path, CANDIDATE)
    env["EXEDEV_CONFIRM_ROUTE"] = f"{CANDIDATE}:{DOMAIN}->{PRODUCTION}"
    env["PAPERBRIDGE_TEST_DNS_CNAME"] = f"{PRODUCTION}.exe.xyz"

    restored = run_operator("restore", env)

    assert restored.returncode == 0, restored.stderr
    assert restored.stdout == (
        f"route_vm={PRODUCTION}\ndomain={DOMAIN}\ncname={PRODUCTION}.exe.xyz\nprivate=true\n"
    )
    assert log.read_text().splitlines() == [
        f"domain rm {CANDIDATE} {DOMAIN}",
        f"domain add {PRODUCTION} {DOMAIN}",
        f"share set-private {PRODUCTION}",
        f"share set-private {CANDIDATE}",
    ]
    state = json.loads(state_path.read_text())
    assert state["domains"] == [{"domain": DOMAIN, "vm_name": PRODUCTION}]


def test_route_restore_recovers_an_interrupted_missing_registration(tmp_path):
    env, state_path, log = write_fakes(tmp_path, None)
    env["EXEDEV_CONFIRM_ROUTE"] = f"{CANDIDATE}:{DOMAIN}->{PRODUCTION}"
    env["PAPERBRIDGE_TEST_DNS_CNAME"] = f"{PRODUCTION}.exe.xyz"

    restored = run_operator("restore", env)

    assert restored.returncode == 0, restored.stderr
    assert log.read_text().splitlines() == [
        f"domain add {PRODUCTION} {DOMAIN}",
        f"share set-private {PRODUCTION}",
        f"share set-private {CANDIDATE}",
    ]
    state = json.loads(state_path.read_text())
    assert state["domains"] == [{"domain": DOMAIN, "vm_name": PRODUCTION}]


def test_cutover_runbook_uses_guarded_routes_and_exact_authentication_results():
    runbook = RUNBOOK.read_text()
    justfile = JUSTFILE.read_text()

    for command in (
        "PAPERBRIDGE_SHA=<40-character-merged-commit>",
        "PAPERBRIDGE_IMAGE_DIGEST=sha256:<64-hex>",
        "just exedev-container-restart",
        "just exedev-container-reboot",
        "just exedev-container-route-activate",
        "just exedev-container-route-restore",
        "just exedev-container-rollback",
        "set -euo pipefail",
        'test "$anonymous_code" = 307',
        'test "$invalid_code" = 401',
        "X-Exedev-Authorization: Bearer <token>",
    ):
        assert command in runbook

    assert "uv run python tools/exedev/cutover_operator.py activate" in justfile
    assert "uv run python tools/exedev/cutover_operator.py restore" in justfile
    assert runbook.count("just exedev-container-probe") >= 4

    for forbidden in (
        "share set-public",
        "/api/jobs",
        "paperbridge_print",
        "production-restart",
        "printer.cut",
        "printer.feed",
    ):
        assert forbidden not in runbook
