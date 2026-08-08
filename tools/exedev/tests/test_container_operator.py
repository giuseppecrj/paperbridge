import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).parents[3]
OPERATOR = ROOT / "tools/exedev/container-operator.sh"


def run_operator(mode: str, **environment: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(environment)
    env["PAPERBRIDGE_EXEDEV_DRY_RUN"] = "1"
    return subprocess.run(
        ["bash", str(OPERATOR), mode],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_operator_requires_an_explicit_new_vm_and_refuses_production():
    missing = run_operator("status")
    assert missing.returncode == 2
    assert "EXEDEV_VM is required" in missing.stderr

    production = run_operator(
        "status",
        EXEDEV_VM="paperbridge-prod",
    )
    assert production.returncode == 2
    assert "existing production VM is forbidden" in production.stderr


def test_bootstrap_requires_confirmation_and_an_exact_reviewed_sha():
    environment = {
        "EXEDEV_VM": "paperbridge-container-stage",
        "PAPERBRIDGE_SHA": "a" * 40,
    }
    unconfirmed = run_operator("bootstrap", **environment)
    assert unconfirmed.returncode == 2
    assert "EXEDEV_CONFIRM_VM must match EXEDEV_VM" in unconfirmed.stderr

    invalid_sha = run_operator(
        "bootstrap",
        **{
            **environment,
            "EXEDEV_CONFIRM_VM": "paperbridge-container-stage",
            "PAPERBRIDGE_SHA": "main",
        },
    )
    assert invalid_sha.returncode == 2
    assert "PAPERBRIDGE_SHA must be a 40-character lowercase commit SHA" in invalid_sha.stderr

    rendered = run_operator(
        "bootstrap",
        **environment,
        EXEDEV_CONFIRM_VM="paperbridge-container-stage",
    )
    assert rendered.returncode == 0, rendered.stderr
    assert "paperbridge-container-stage.exe.xyz" in rendered.stdout
    assert "BatchMode=yes" in rendered.stdout
    assert "ForwardAgent=no" in rendered.stdout
    assert "a" * 40 in rendered.stdout
    assert "paperbridge-prod" not in rendered.stdout
    assert "api.paperbridge.tech" not in rendered.stdout


def test_credential_bytes_are_sent_only_through_ssh_stdin():
    environment = {
        "EXEDEV_VM": "paperbridge-container-stage",
        "EXEDEV_CONFIRM_VM": "paperbridge-container-stage",
    }
    missing = run_operator("credential", **environment)
    assert missing.returncode == 2
    assert "PAPERBRIDGE_MQTT_PASSWORD is required" in missing.stderr

    secret = "credential-canary-value"
    rendered = run_operator(
        "credential",
        **environment,
        PAPERBRIDGE_MQTT_PASSWORD=secret,
    )
    assert rendered.returncode == 0, rendered.stderr
    assert "paperbridge-container-remote credential" in rendered.stdout
    assert "credential bytes via SSH stdin" in rendered.stdout
    assert secret not in rendered.stdout
    assert secret not in rendered.stderr
    assert "PAPERBRIDGE_MQTT_PASSWORD=" not in rendered.stdout


def test_build_and_deploy_accept_only_immutable_inputs():
    environment = {
        "EXEDEV_VM": "paperbridge-container-stage",
        "EXEDEV_CONFIRM_VM": "paperbridge-container-stage",
    }
    built = run_operator(
        "build",
        **environment,
        PAPERBRIDGE_SHA="b" * 40,
    )
    assert built.returncode == 0, built.stderr
    assert "paperbridge-container-remote build" in built.stdout
    assert "b" * 40 in built.stdout

    tag = run_operator(
        "deploy",
        **environment,
        PAPERBRIDGE_IMAGE_DIGEST="paperbridge-api:latest",
    )
    assert tag.returncode == 2
    assert "PAPERBRIDGE_IMAGE_DIGEST must be a sha256 image digest" in tag.stderr

    digest = f"sha256:{'c' * 64}"
    deployed = run_operator(
        "deploy",
        **environment,
        PAPERBRIDGE_IMAGE_DIGEST=digest,
    )
    assert deployed.returncode == 0, deployed.stderr
    assert "paperbridge-container-remote deploy" in deployed.stdout
    assert digest in deployed.stdout
    assert ":latest" not in deployed.stdout


def test_operator_exposes_bounded_read_only_and_confirmed_actions():
    vm = "paperbridge-container-stage"
    for mode in ("status", "logs", "verify"):
        rendered = run_operator(mode, EXEDEV_VM=vm)
        assert rendered.returncode == 0, rendered.stderr
        assert f"paperbridge-container-remote {mode}" in rendered.stdout

    for mode in ("probe", "restart", "rollback"):
        unconfirmed = run_operator(mode, EXEDEV_VM=vm)
        assert unconfirmed.returncode == 2
        assert "EXEDEV_CONFIRM_VM must match EXEDEV_VM" in unconfirmed.stderr

        rendered = run_operator(mode, EXEDEV_VM=vm, EXEDEV_CONFIRM_VM=vm)
        assert rendered.returncode == 0, rendered.stderr
        assert f"paperbridge-container-remote {mode}" in rendered.stdout

    reboot = run_operator("reboot", EXEDEV_VM=vm, EXEDEV_CONFIRM_VM=vm)
    assert reboot.returncode == 0, reboot.stderr
    assert "exe.dev restart paperbridge-container-stage" in reboot.stdout

    combined = "\n".join(
        run_operator(mode, EXEDEV_VM=vm, EXEDEV_CONFIRM_VM=vm).stdout
        for mode in ("status", "logs", "verify", "probe", "restart", "rollback", "reboot")
    )
    assert "api.paperbridge.tech" not in combined
    assert "share " not in combined
    assert "domain " not in combined
    assert "printer" not in combined.lower()
    assert "device" not in combined.lower()
