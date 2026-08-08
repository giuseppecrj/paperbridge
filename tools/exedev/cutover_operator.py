#!/usr/bin/env python3
import json
import os
import subprocess
import sys
from collections.abc import Sequence

DOMAIN = "api.paperbridge.tech"
PRODUCTION_VM = "paperbridge-prod"
CANDIDATE_VM = "paperbridge-api"
PRODUCTION_CNAME = f"{PRODUCTION_VM}.exe.xyz"
CANDIDATE_CNAME = f"{CANDIDATE_VM}.exe.xyz"
DNS_SERVER = "nsa1.squarespacedns.com"


class CutoverError(Exception):
    pass


class ConfirmationError(CutoverError):
    pass


def run(command: Sequence[str], description: str) -> str:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
    except subprocess.TimeoutExpired as error:
        raise CutoverError(f"{description} timed out") from error
    except OSError as error:
        raise CutoverError(f"{description} could not run") from error
    if completed.returncode != 0:
        raise CutoverError(f"{description} failed")
    return completed.stdout


def control_command(*arguments: str) -> list[str]:
    override = os.environ.get("PAPERBRIDGE_EXEDEV_CONTROL_BIN")
    if override:
        return [override, *arguments]
    return [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "ForwardAgent=no",
        "-o",
        "StrictHostKeyChecking=yes",
        "-o",
        "ConnectTimeout=10",
        "exe.dev",
        *arguments,
    ]


def control(*arguments: str) -> str:
    return run(control_command(*arguments), f"exe.dev {' '.join(arguments)}")


def control_json(*arguments: str) -> dict[str, object]:
    output = control(*arguments)
    try:
        value = json.loads(output)
    except json.JSONDecodeError as error:
        raise CutoverError("exe.dev returned invalid JSON") from error
    if not isinstance(value, dict):
        raise CutoverError("exe.dev returned invalid JSON")
    return value


def authoritative_cname() -> str:
    dig = os.environ.get("PAPERBRIDGE_DIG_BIN", "dig")
    output = run(
        [
            dig,
            f"@{DNS_SERVER}",
            DOMAIN,
            "CNAME",
            "+short",
            "+time=5",
            "+tries=1",
        ],
        "authoritative DNS lookup",
    )
    answers = [line.strip().lower().removesuffix(".") for line in output.splitlines()]
    answers = [answer for answer in answers if answer]
    if len(answers) != 1:
        raise CutoverError("authoritative DNS must return exactly one CNAME")
    return answers[0]


def domain_routes() -> list[str]:
    value = control_json("domain", "ls", "-a", "--json")
    domains = value.get("domains")
    if not isinstance(domains, list):
        raise CutoverError("exe.dev domain state is invalid")
    routes = []
    for item in domains:
        if not isinstance(item, dict):
            raise CutoverError("exe.dev domain state is invalid")
        if item.get("domain") == DOMAIN:
            vm_name = item.get("vm_name")
            if not isinstance(vm_name, str):
                raise CutoverError("exe.dev domain state is invalid")
            routes.append(vm_name)
    return routes


def require_private_share(vm: str) -> None:
    value = control_json("share", "show", vm, "--json")
    required_values = {
        "vm_name": vm,
        "port": 3000,
        "status": "private",
        "team_access": False,
        "team_shelley": False,
        "team_ssh": False,
    }
    if any(value.get(key) != expected for key, expected in required_values.items()):
        raise CutoverError(f"{vm} share is not the expected private port")
    if any(value.get(key) != [] for key in ("links", "teams", "users")):
        raise CutoverError(f"{vm} share has unexpected grants")


def require_private_shares() -> None:
    require_private_share(PRODUCTION_VM)
    require_private_share(CANDIDATE_VM)


def require_confirmation(expected: str) -> None:
    if os.environ.get("EXEDEV_CONFIRM_ROUTE") != expected:
        raise ConfirmationError(f"EXEDEV_CONFIRM_ROUTE must equal {expected}")


def require_route(expected: str) -> None:
    routes = domain_routes()
    if routes != [expected]:
        raise CutoverError(f"{DOMAIN} must be registered only to {expected}")


def require_cname(expected: str) -> None:
    if authoritative_cname() != expected:
        raise CutoverError(f"{DOMAIN} CNAME must equal {expected}")


def print_state(vm: str, cname: str) -> None:
    print(f"route_vm={vm}")
    print(f"domain={DOMAIN}")
    print(f"cname={cname}")
    print("private=true")


def activate() -> None:
    confirmation = f"{PRODUCTION_VM}:{DOMAIN}->{CANDIDATE_VM}"
    require_confirmation(confirmation)
    require_cname(CANDIDATE_CNAME)
    require_route(PRODUCTION_VM)
    require_private_shares()

    control("domain", "rm", PRODUCTION_VM, DOMAIN)
    control("domain", "add", CANDIDATE_VM, DOMAIN)
    control("share", "set-private", CANDIDATE_VM)
    control("share", "set-private", PRODUCTION_VM)

    require_cname(CANDIDATE_CNAME)
    require_route(CANDIDATE_VM)
    require_private_shares()
    print_state(CANDIDATE_VM, CANDIDATE_CNAME)


def restore() -> None:
    confirmation = f"{CANDIDATE_VM}:{DOMAIN}->{PRODUCTION_VM}"
    require_confirmation(confirmation)
    require_cname(PRODUCTION_CNAME)
    routes = domain_routes()
    if routes not in ([CANDIDATE_VM], [], [PRODUCTION_VM]):
        raise CutoverError(f"{DOMAIN} has an unexpected registration")
    require_private_shares()

    if routes == [CANDIDATE_VM]:
        control("domain", "rm", CANDIDATE_VM, DOMAIN)
    if routes != [PRODUCTION_VM]:
        control("domain", "add", PRODUCTION_VM, DOMAIN)
    control("share", "set-private", PRODUCTION_VM)
    control("share", "set-private", CANDIDATE_VM)

    require_cname(PRODUCTION_CNAME)
    require_route(PRODUCTION_VM)
    require_private_shares()
    print_state(PRODUCTION_VM, PRODUCTION_CNAME)


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in {"activate", "restore"}:
        print("usage: cutover_operator.py <activate|restore>", file=sys.stderr)
        return 2
    try:
        if sys.argv[1] == "activate":
            activate()
        else:
            restore()
    except ConfirmationError as error:
        print(error, file=sys.stderr)
        return 2
    except CutoverError as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
