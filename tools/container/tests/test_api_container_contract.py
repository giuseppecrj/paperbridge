from pathlib import Path

import tomllib

ROOT = Path(__file__).parents[3]
DOCKERFILE = ROOT / "apps/api/Dockerfile"
ACCEPTANCE = ROOT / "apps/api/tests/container.acceptance.ts"
DOCKERIGNORE = ROOT / ".dockerignore"
JUSTFILE = ROOT / "justfile"
MISE = tomllib.loads((ROOT / "mise.toml").read_text())


def test_image_pins_repository_bun_and_node_versions_by_digest():
    dockerfile = DOCKERFILE.read_text()

    assert MISE["tools"]["bun"] == "1.3.14"
    assert MISE["tools"]["node"] == "26.3.0"
    assert (
        "oven/bun:1.3.14-debian@sha256:"
        "9dba1a1b43ce28c9d7931bfc4eb00feb63b0114720a0277a8f939ae4dfc9db6f" in dockerfile
    )
    assert (
        "node:26.3.0-bookworm-slim@sha256:"
        "3fe807a03a4436e7bc76b7e84e6861899cd75c9028ae99bc00581940141ae150" in dockerfile
    )
    assert dockerfile.count("FROM ") >= 3
    assert not dockerfile.startswith("# syntax=")
    assert "bun install --frozen-lockfile" in dockerfile
    assert "bun run --filter @paperbridge/api build" in dockerfile
    assert 'CMD ["node", "dist/server.js"]' in dockerfile


def test_runtime_image_keeps_native_dependencies_and_runs_non_root():
    dockerfile = DOCKERFILE.read_text()

    assert "COPY --from=production-dependencies" in dockerfile
    assert "apps/api/node_modules" in dockerfile
    assert "USER node" in dockerfile
    assert "PAPERBRIDGE_MQTT_PASSWORD" not in dockerfile


def test_build_context_excludes_secret_and_generated_state():
    ignored = DOCKERIGNORE.read_text().splitlines()

    for pattern in (
        ".env",
        "fnox.local.toml",
        ".fnox.local.toml",
        "firmware/micropython/config.json",
        "**/node_modules",
        "apps/api/dist",
        ".git",
    ):
        assert pattern in ignored


def test_acceptance_runs_one_hardened_loopback_container():
    acceptance = ACCEPTANCE.read_text()

    for flag in (
        '"--read-only"',
        '"--cap-drop=ALL"',
        '"--security-opt=no-new-privileges"',
        "127.0.0.1:${apiPort}:3000",
        "PAPERBRIDGE_MQTT_PASSWORD_FILE=/run/secrets/mqtt-password",
        "target=/run/secrets/mqtt-password,readonly",
    ):
        assert flag in acceptance
    assert '"--network=host"' not in acceptance
    assert '"--memory"' not in acceptance
    assert '"--cpus"' not in acceptance


def test_just_exposes_explicit_container_build_and_acceptance_checks():
    justfile = JUSTFILE.read_text()

    assert "build-api-container:" in justfile
    assert "test-api-container:" in justfile
    assert "docker build" in justfile
    assert "PAPERBRIDGE_TEST_CONTAINER_IMAGE" in justfile
