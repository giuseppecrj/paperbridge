import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).parents[3]
UNIT = ROOT / "deploy/exedev/paperbridge-container.service"
ENVIRONMENT = ROOT / "deploy/exedev/paperbridge-container.env.template"
REMOTE = ROOT / "tools/exedev/container-remote.sh"
JUSTFILE = ROOT / "justfile"


def test_systemd_unit_owns_one_hardened_digest_selected_container():
    unit = UNIT.read_text()

    for directive in (
        "Requires=docker.service",
        "After=network-online.target docker.service",
        "LoadCredentialEncrypted=mqtt-password:/etc/credstore.encrypted/paperbridge-mqtt-password",
        "RuntimeDirectory=paperbridge-container",
        "RuntimeDirectoryMode=0700",
        "EnvironmentFile=/var/lib/paperbridge-container/current-image.env",
        (
            "ExecStartPre=/usr/bin/install -m 0444 %d/mqtt-password "
            "/run/paperbridge-container/mqtt-password"
        ),
        "--read-only",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--network=bridge",
        "--publish=127.0.0.1:3000:3000",
        "source=/run/paperbridge-container/mqtt-password,target=/run/secrets/mqtt-password,readonly",
        "--env-file=/etc/paperbridge-container/api.env",
        "${PAPERBRIDGE_IMAGE}",
        "ExecStop=/usr/bin/docker stop --time=18 paperbridge-api",
        "ExecStopPost=-/usr/bin/rm -f /run/paperbridge-container/mqtt-password",
        "Restart=on-failure",
        "TimeoutStopSec=20",
    ):
        assert directive in unit

    assert "--network=host" not in unit
    assert "docker.sock" not in unit
    assert "--restart=" not in unit
    assert "PAPERBRIDGE_MQTT_PASSWORD=" not in unit


def test_environment_template_contains_only_selected_vm_and_file_secret_config():
    environment = ENVIRONMENT.read_text()

    assert "PAPERBRIDGE_API_HOST=0.0.0.0" in environment
    assert "PAPERBRIDGE_API_ALLOWED_HOST=@EXEDEV_HOST@" in environment
    assert "PAPERBRIDGE_API_ALLOWED_ORIGIN=https://@EXEDEV_HOST@" in environment
    assert "PAPERBRIDGE_MQTT_PASSWORD_FILE=/run/secrets/mqtt-password" in environment
    assert "api.paperbridge.tech" not in environment
    assert "PAPERBRIDGE_MQTT_PASSWORD=" not in environment
    assert "BASE64" not in environment


def test_encrypted_credential_check_stops_without_a_plaintext_fallback(tmp_path):
    root = tmp_path / "root"
    env = os.environ.copy()
    env.update(
        {
            "PAPERBRIDGE_EXEDEV_ROOT": str(root),
            "PAPERBRIDGE_SYSTEMD_CREDS_BIN": str(tmp_path / "missing-systemd-creds"),
        }
    )

    checked = subprocess.run(
        ["bash", str(REMOTE), "credential-check"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert checked.returncode != 0
    assert "encrypted systemd credentials are unavailable" in checked.stderr
    assert not (root / "etc/paperbridge-container/paperbridge.env").exists()
    assert not (root / "var/lib/paperbridge-container/bootstrap-complete").exists()


def test_bootstrap_gates_docker_and_records_the_explicit_fresh_vm(tmp_path):
    root = tmp_path / "root"
    (root / "exe.dev").mkdir(parents=True)
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    calls = tmp_path / "calls"

    passthrough = """#!/bin/sh
printf '%s\\n' \"$(basename \"$0\") $*\" >>\"$PAPERBRIDGE_TEST_CALLS\"
exit 0
"""
    for name in ("apt-get", "docker", "systemctl", "systemd-run"):
        path = fake_bin / name
        path.write_text(passthrough)
        path.chmod(0o755)

    systemd_creds = fake_bin / "systemd-creds"
    systemd_creds.write_text(
        """#!/bin/sh
printf '%s\\n' \"systemd-creds $*\" >>\"$PAPERBRIDGE_TEST_CALLS\"
if [ \"$1\" = encrypt ]; then
    for output do :; done
    cat >\"$output\"
fi
"""
    )
    systemd_creds.chmod(0o755)

    git = fake_bin / "git"
    git.write_text(
        """#!/bin/sh
printf '%s\\n' \"git $*\" >>\"$PAPERBRIDGE_TEST_CALLS\"
if [ \"$1\" = clone ]; then
    for target do :; done
    mkdir -p \"$target/.git\"
fi
"""
    )
    git.chmod(0o755)

    sha = "d" * 40
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{fake_bin}:/usr/bin:/bin",
            "PAPERBRIDGE_EXEDEV_ROOT": str(root),
            "PAPERBRIDGE_SYSTEMD_CREDS_BIN": str(systemd_creds),
            "PAPERBRIDGE_SYSTEMD_RUN_BIN": str(fake_bin / "systemd-run"),
            "PAPERBRIDGE_TEST_CALLS": str(calls),
        }
    )
    bootstrapped = subprocess.run(
        ["bash", str(REMOTE), "bootstrap", sha, "paperbridge-container-stage"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert bootstrapped.returncode == 0, bootstrapped.stderr
    assert bootstrapped.stdout == (
        f"bootstrapped_vm=paperbridge-container-stage bootstrap_sha={sha}\n"
    )
    assert (root / "var/lib/paperbridge-container/bootstrap-complete").read_text() == (
        f"vm=paperbridge-container-stage\nbootstrap_sha={sha}\n"
    )
    recorded = calls.read_text()
    assert "apt-get install --yes ca-certificates git docker.io" in recorded
    assert "systemctl enable --now docker.service" in recorded
    assert "docker info" in recorded
    assert "systemd-creds encrypt" in recorded
    assert f"git -C {root}/opt/paperbridge-container/repository fetch" in recorded


def test_build_records_the_exact_commit_image_digest_and_vm_architecture(tmp_path):
    root = tmp_path / "root"
    app_root = root / "opt/paperbridge-container"
    repository = app_root / "repository"
    (repository / ".git").mkdir(parents=True)
    state = root / "var/lib/paperbridge-container"
    (state / "images").mkdir(parents=True)
    (state / "bootstrap-complete").write_text(
        "vm=paperbridge-container-stage\nbootstrap_sha=ignored\n"
    )
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    calls = tmp_path / "calls"
    sha = "e" * 40
    digest = f"sha256:{'f' * 64}"

    git = fake_bin / "git"
    git.write_text(
        """#!/bin/sh
printf '%s\\n' \"git $*\" >>\"$PAPERBRIDGE_TEST_CALLS\"
if [ \"$1\" = -C ]; then shift 2; fi
case \"$1\" in
    worktree)
        target=$4
        mkdir -p \"$target/apps/api\"
        : >\"$target/apps/api/Dockerfile\"
        ;;
    rev-parse)
        printf '%s\\n' \"$PAPERBRIDGE_TEST_SHA\"
        ;;
esac
"""
    )
    git.chmod(0o755)

    docker = fake_bin / "docker"
    docker.write_text(
        """#!/bin/sh
printf '%s\\n' \"docker $*\" >>\"$PAPERBRIDGE_TEST_CALLS\"
if [ \"$1 $2 $3\" = \"image inspect --format\" ]; then
    case \"$4\" in
        '{{.Id}}') printf '%s\\n' \"$PAPERBRIDGE_TEST_DIGEST\" ;;
        '{{ index .Config.Labels "org.opencontainers.image.revision" }}')
            printf '%s\\n' \"$PAPERBRIDGE_TEST_SHA\"
            ;;
        '{{.Architecture}}') printf '%s\\n' amd64 ;;
    esac
fi
"""
    )
    docker.chmod(0o755)

    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{fake_bin}:/usr/bin:/bin",
            "PAPERBRIDGE_EXEDEV_ROOT": str(root),
            "PAPERBRIDGE_TEST_CALLS": str(calls),
            "PAPERBRIDGE_TEST_SHA": sha,
            "PAPERBRIDGE_TEST_DIGEST": digest,
        }
    )
    built = subprocess.run(
        ["bash", str(REMOTE), "build", sha],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert built.returncode == 0, built.stderr
    assert built.stdout == f"built_sha={sha} image_digest={digest} architecture=amd64\n"
    assert (state / "images" / f"{'f' * 64}.sha").read_text() == f"{sha}\n"
    recorded = calls.read_text()
    assert f"git -C {repository} worktree add --detach {app_root}/builds/{sha} {sha}" in recorded
    assert f"--label org.opencontainers.image.revision={sha}" in recorded
    assert f"--file {app_root}/builds/{sha}/apps/api/Dockerfile" in recorded
    assert f"paperbridge-api:sha-{sha}" in recorded


def test_credential_provisioning_and_rotation_are_atomic_and_secret_safe(tmp_path):
    root = tmp_path / "root"
    state = root / "var/lib/paperbridge-container"
    state.mkdir(parents=True)
    (state / "bootstrap-complete").write_text("vm=paperbridge-container-stage\n")
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    calls = tmp_path / "calls"

    systemd_creds = fake_bin / "systemd-creds"
    systemd_creds.write_text(
        """#!/bin/sh
printf '%s\\n' \"systemd-creds $*\" >>\"$PAPERBRIDGE_TEST_CALLS\"
if [ \"$1\" = encrypt ]; then
    for output do :; done
    cat >/dev/null
    printf 'encrypted-credential\\n' >\"$output\"
fi
"""
    )
    systemd_creds.chmod(0o755)
    for name in ("systemd-run", "systemctl"):
        path = fake_bin / name
        path.write_text(
            """#!/bin/sh
printf '%s\\n' \"$(basename \"$0\") $*\" >>\"$PAPERBRIDGE_TEST_CALLS\"
"""
        )
        path.chmod(0o755)

    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{fake_bin}:/usr/bin:/bin",
            "PAPERBRIDGE_EXEDEV_ROOT": str(root),
            "PAPERBRIDGE_SYSTEMD_CREDS_BIN": str(systemd_creds),
            "PAPERBRIDGE_SYSTEMD_RUN_BIN": str(fake_bin / "systemd-run"),
            "PAPERBRIDGE_TEST_CALLS": str(calls),
        }
    )
    secret = "credential-canary-value"
    provisioned = subprocess.run(
        ["bash", str(REMOTE), "credential"],
        cwd=ROOT,
        env=env,
        input=secret,
        capture_output=True,
        text=True,
        check=False,
    )

    assert provisioned.returncode == 0, provisioned.stderr
    assert provisioned.stdout == "credential_provisioned=true\n"
    credential = root / "etc/credstore.encrypted/paperbridge-mqtt-password"
    assert credential.read_text() == "encrypted-credential\n"
    assert secret not in provisioned.stdout + provisioned.stderr + calls.read_text()
    assert "systemctl restart" not in calls.read_text()

    rotated = subprocess.run(
        ["bash", str(REMOTE), "rotate"],
        cwd=ROOT,
        env=env,
        input="replacement-canary-value",
        capture_output=True,
        text=True,
        check=False,
    )
    assert rotated.returncode == 0, rotated.stderr
    assert rotated.stdout == "credential_rotated=true\n"
    assert "systemctl restart paperbridge-container.service" in calls.read_text()
    assert "replacement-canary-value" not in rotated.stdout + rotated.stderr + calls.read_text()


def test_deploy_refuses_before_state_change_without_an_encrypted_credential(tmp_path):
    root = tmp_path / "root"
    state = root / "var/lib/paperbridge-container"
    state.mkdir(parents=True)
    current = f"sha256:{'5' * 64}"
    target = f"sha256:{'6' * 64}"
    (state / "bootstrap-complete").write_text("vm=paperbridge-container-stage\n")
    (state / "current-image.env").write_text(f"PAPERBRIDGE_IMAGE={current}\n")

    refused = subprocess.run(
        ["bash", str(REMOTE), "deploy", target],
        cwd=ROOT,
        env={**os.environ, "PAPERBRIDGE_EXEDEV_ROOT": str(root)},
        capture_output=True,
        text=True,
        check=False,
    )

    assert refused.returncode != 0
    assert "credential is not provisioned" in refused.stderr
    assert (state / "current-image.env").read_text() == (f"PAPERBRIDGE_IMAGE={current}\n")
    assert not (state / "previous-image").exists()


def test_deploy_refuses_when_the_current_rollback_image_is_not_retained(tmp_path):
    root = tmp_path / "root"
    state = root / "var/lib/paperbridge-container"
    state.mkdir(parents=True)
    current = f"sha256:{'7' * 64}"
    target = f"sha256:{'8' * 64}"
    (state / "bootstrap-complete").write_text("vm=paperbridge-container-stage\n")
    (state / "current-image.env").write_text(f"PAPERBRIDGE_IMAGE={current}\n")
    credential = root / "etc/credstore.encrypted/paperbridge-mqtt-password"
    credential.parent.mkdir(parents=True)
    credential.write_text("encrypted-credential\n")

    refused = subprocess.run(
        ["bash", str(REMOTE), "deploy", target],
        cwd=ROOT,
        env={**os.environ, "PAPERBRIDGE_EXEDEV_ROOT": str(root)},
        capture_output=True,
        text=True,
        check=False,
    )

    assert refused.returncode != 0
    assert "current image is not retained for rollback" in refused.stderr
    assert (state / "current-image.env").read_text() == (f"PAPERBRIDGE_IMAGE={current}\n")
    assert not (state / "previous-image").exists()


def test_deploy_and_rollback_keep_only_current_and_previous_digests(tmp_path):
    root = tmp_path / "root"
    state = root / "var/lib/paperbridge-container"
    images = state / "images"
    images.mkdir(parents=True)
    (state / "bootstrap-complete").write_text("vm=paperbridge-container-stage\n")
    credential = root / "etc/credstore.encrypted/paperbridge-mqtt-password"
    credential.parent.mkdir(parents=True)
    credential.write_text("encrypted-credential\n")
    builds = root / "opt/paperbridge-container/builds"
    digests = [f"sha256:{character * 64}" for character in "123"]
    shas = [character * 40 for character in "abc"]
    for digest, sha in zip(digests, shas, strict=True):
        (images / f"{digest.removeprefix('sha256:')}.sha").write_text(f"{sha}\n")
        release = builds / sha
        (release / "deploy/exedev").mkdir(parents=True)
        (release / "deploy/exedev/paperbridge-container.service").write_text(
            f"{UNIT.read_text()}\n# release={sha}\n"
        )
        (release / "deploy/exedev/paperbridge-container.env.template").write_text(
            f"{ENVIRONMENT.read_text()}# RELEASE_SHA={sha}\n"
        )
    (state / "current-image.env").write_text(f"PAPERBRIDGE_IMAGE={digests[0]}\n")

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    calls = tmp_path / "calls"
    git = fake_bin / "git"
    git.write_text(
        """#!/bin/sh
printf '%s\\n' \"git $*\" >>\"$PAPERBRIDGE_TEST_CALLS\"
if [ \"$1\" = -C ]; then
    directory=$2
    shift 2
fi
if [ \"$1 $2\" = \"rev-parse HEAD\" ]; then basename \"$directory\"; fi
"""
    )
    git.chmod(0o755)
    docker = fake_bin / "docker"
    docker.write_text(
        """#!/bin/sh
printf '%s\\n' \"docker $*\" >>\"$PAPERBRIDGE_TEST_CALLS\"
"""
    )
    docker.chmod(0o755)
    systemctl = fake_bin / "systemctl"
    systemctl.write_text(
        """#!/bin/sh
printf '%s\\n' \"systemctl $*\" >>\"$PAPERBRIDGE_TEST_CALLS\"
if [ \"${PAPERBRIDGE_TEST_RESTART_FAIL:-0}\" = 1 ] && [ \"$1\" = restart ]; then exit 1; fi
"""
    )
    systemctl.chmod(0o755)

    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{fake_bin}:/usr/bin:/bin",
            "PAPERBRIDGE_EXEDEV_ROOT": str(root),
            "PAPERBRIDGE_TEST_CALLS": str(calls),
        }
    )
    deployed = subprocess.run(
        ["bash", str(REMOTE), "deploy", digests[1]],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert deployed.returncode == 0, deployed.stderr
    assert deployed.stdout == (f"deployed_digest={digests[1]} rollback_digest={digests[0]}\n")
    assert (state / "current-image.env").read_text() == (f"PAPERBRIDGE_IMAGE={digests[1]}\n")
    assert (state / "previous-image").read_text() == f"{digests[0]}\n"
    assert (images / f"{'1' * 64}.sha").exists()
    assert (images / f"{'2' * 64}.sha").exists()
    assert not (images / f"{'3' * 64}.sha").exists()
    config = (root / "etc/paperbridge-container/api.env").read_text()
    assert "paperbridge-container-stage.exe.xyz" in config
    assert "@EXEDEV_HOST@" not in config
    assert "api.paperbridge.tech" not in config
    assert f"RELEASE_SHA={shas[1]}" in config

    rolled_back = subprocess.run(
        ["bash", str(REMOTE), "rollback"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert rolled_back.returncode == 0, rolled_back.stderr
    assert rolled_back.stdout == (f"rolled_back_digest={digests[0]} rollback_digest={digests[1]}\n")
    assert (state / "current-image.env").read_text() == (f"PAPERBRIDGE_IMAGE={digests[0]}\n")
    assert (state / "previous-image").read_text() == f"{digests[1]}\n"
    recorded = calls.read_text()
    assert f"docker image rm {digests[2]}" in recorded
    assert recorded.count("systemctl restart paperbridge-container.service") == 2

    failed_digest = f"sha256:{'4' * 64}"
    failed_sha = "d" * 40
    (images / f"{'4' * 64}.sha").write_text(f"{failed_sha}\n")
    failed_release = builds / failed_sha / "deploy/exedev"
    failed_release.mkdir(parents=True)
    (failed_release / "paperbridge-container.service").write_text(
        f"{UNIT.read_text()}\n# release={failed_sha}\n"
    )
    (failed_release / "paperbridge-container.env.template").write_text(
        f"{ENVIRONMENT.read_text()}# RELEASE_SHA={failed_sha}\n"
    )
    failed_env = {**env, "PAPERBRIDGE_TEST_RESTART_FAIL": "1"}
    failed = subprocess.run(
        ["bash", str(REMOTE), "deploy", failed_digest],
        cwd=ROOT,
        env=failed_env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert failed.returncode != 0
    assert "previous image restored" in failed.stderr
    assert (state / "current-image.env").read_text() == (f"PAPERBRIDGE_IMAGE={digests[0]}\n")
    assert (state / "previous-image").read_text() == f"{digests[1]}\n"
    assert f"RELEASE_SHA={shas[0]}" in (root / "etc/paperbridge-container/api.env").read_text()
    assert (
        f"release={shas[0]}"
        in (root / "etc/systemd/system/paperbridge-container.service").read_text()
    )
    assert (images / f"{'1' * 64}.sha").exists()
    assert (images / f"{'4' * 64}.sha").exists()

    failed_rollback = subprocess.run(
        ["bash", str(REMOTE), "rollback"],
        cwd=ROOT,
        env=failed_env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert failed_rollback.returncode != 0
    assert "previous image restored" in failed_rollback.stderr
    assert (state / "current-image.env").read_text() == (f"PAPERBRIDGE_IMAGE={digests[0]}\n")
    assert (state / "previous-image").read_text() == f"{digests[1]}\n"
    assert calls.read_text().count("systemctl restart paperbridge-container.service") == 6


def test_remote_observation_and_no_output_actions_are_bounded(tmp_path):
    root = tmp_path / "root"
    state = root / "var/lib/paperbridge-container"
    state.mkdir(parents=True)
    digest = f"sha256:{'4' * 64}"
    (state / "bootstrap-complete").write_text("vm=paperbridge-container-stage\n")
    (state / "current-image.env").write_text(f"PAPERBRIDGE_IMAGE={digest}\n")
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    calls = tmp_path / "calls"
    passthrough = """#!/bin/sh
printf '%s\\n' \"$(basename \"$0\") $*\" >>\"$PAPERBRIDGE_TEST_CALLS\"
"""
    for name in ("curl", "docker", "journalctl", "systemctl"):
        path = fake_bin / name
        path.write_text(passthrough)
        path.chmod(0o755)

    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{fake_bin}:/usr/bin:/bin",
            "PAPERBRIDGE_EXEDEV_ROOT": str(root),
            "PAPERBRIDGE_TEST_CALLS": str(calls),
        }
    )
    outputs: list[str] = []
    for mode in ("status", "logs", "verify", "probe", "restart"):
        completed = subprocess.run(
            ["bash", str(REMOTE), mode],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == 0, f"{mode}: {completed.stderr}"
        outputs.append(completed.stdout)

    recorded = calls.read_text()
    assert "systemctl status --no-pager paperbridge-container.service" in recorded
    assert "journalctl --no-pager --unit=paperbridge-container.service --lines=100" in recorded
    assert "curl --fail --silent --show-error" in recorded
    assert "http://127.0.0.1:3000/health" in recorded
    assert "http://127.0.0.1:3000/ready" in recorded
    assert "docker exec paperbridge-api node dist/main.js" in recorded
    assert "systemctl restart paperbridge-container.service" in recorded
    assert "/api/jobs" not in recorded
    assert "paperbridge_print" not in recorded
    assert "printer" not in recorded.lower()
    assert "device" not in recorded.lower()
    assert "credential" not in "".join(outputs).lower()


def test_justfile_exposes_each_container_operator_action_with_local_fnox_secrets():
    justfile = JUSTFILE.read_text()
    actions = (
        "bootstrap",
        "credential",
        "build",
        "deploy",
        "status",
        "logs",
        "verify",
        "probe",
        "restart",
        "reboot",
        "rotate",
        "rollback",
    )
    for action in actions:
        assert f"exedev-container-{action}:" in justfile

    for action in ("credential", "rotate"):
        block = justfile.split(f"exedev-container-{action}:", 1)[1].split("\n\n", 1)[0]
        assert "fnox --no-daemon -P production exec --" in block
        assert f"tools/exedev/container-operator.sh {action}" in block
        assert "PAPERBRIDGE_MQTT_PASSWORD=" not in block

    assert "PAPERBRIDGE_SHA" in justfile.split("exedev-container-build:", 1)[1].split("\n\n", 1)[0]
    assert (
        "PAPERBRIDGE_IMAGE_DIGEST"
        in justfile.split("exedev-container-deploy:", 1)[1].split("\n\n", 1)[0]
    )
