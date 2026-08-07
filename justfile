set dotenv-load := true

PORT := env_var_or_default("PORT", env_var_or_default("PAPERBRIDGE_PORT", ""))
FIRMWARE := env_var_or_default("FIRMWARE", "")
CONFIRM := env_var_or_default("CONFIRM", "")
TEXT := env_var_or_default("TEXT", "Hello from my Mac")
NETWORK_RECOVERY_TIMEOUT_SECONDS := env_var_or_default("NETWORK_RECOVERY_TIMEOUT_SECONDS", "60")
NETWORK_RECOVERY_INTERVAL_SECONDS := env_var_or_default("NETWORK_RECOVERY_INTERVAL_SECONDS", "1")
SOAK_DURATION_SECONDS := env_var_or_default("SOAK_DURATION_SECONDS", "259200")
SOAK_INTERVAL_SECONDS := env_var_or_default("SOAK_INTERVAL_SECONDS", "60")

# Verified ESP32_GENERIC_S3-SPIRAM_OCT-20260406-v1.28.0.bin (docs/micropython-bringup.md)
MICROPYTHON_SHA256 := "67c19ae123d84152019b57526ed5291dd0a2b4edd87655c5f76b46c9a62ff5dd"

bootstrap:
    uv sync
    bun install

lint:
    FNOX_CONFIG_DIR=/nonexistent fnox profiles >/dev/null
    uv run ruff check .
    bun run lint

format:
    uv run ruff format .

format-check:
    uv run ruff format --check .

test:
    uv run pytest
    bun run test

# Opt-in HIL: never part of ordinary `just test`. Requires a selected PORT.
test-hardware-smoke:
    test -n "{{PORT}}" || (echo "PORT is required" >&2; exit 2)
    uv run python tools/hardware/hil.py smoke --port "{{PORT}}"

# Opt-in no-output dual-interface recovery HIL; MQTT secret stays Fnox-managed.
test-hardware-network-recovery:
    test -n "{{PORT}}" || (echo "PORT is required" >&2; exit 2)
    FNOX_CONFIG_DIR=/nonexistent fnox --no-daemon exec -- uv run python tools/hardware/hil.py network-recovery \
        --port "{{PORT}}" \
        --timeout-seconds "{{NETWORK_RECOVERY_TIMEOUT_SECONDS}}" \
        --interval-seconds "{{NETWORK_RECOVERY_INTERVAL_SECONDS}}"

# Opt-in HIL acceptance: interactive operator confirmations; cutter needs exact token CUT.
test-hardware-acceptance:
    test -n "{{PORT}}" || (echo "PORT is required" >&2; exit 2)
    uv run python tools/hardware/hil.py acceptance --port "{{PORT}}"

# Opt-in no-output reliability soak; defaults to 72 hours with one sample per minute.
test-hardware-soak:
    test -n "{{PORT}}" || (echo "PORT is required" >&2; exit 2)
    uv run python tools/hardware/hil.py soak \
        --port "{{PORT}}" \
        --duration-seconds "{{SOAK_DURATION_SECONDS}}" \
        --interval-seconds "{{SOAK_INTERVAL_SECONDS}}"

ports:
    uv run paperbridge ports list

erase-device:
    test -n "{{PORT}}" || (echo "PORT is required" >&2; exit 2)
    test "{{CONFIRM}}" = "erase" || (echo "Set CONFIRM=erase to erase {{PORT}}" >&2; exit 2)
    echo "Erasing flash on {{PORT}}"
    uv run esptool --port "{{PORT}}" erase-flash

flash-micropython:
    test -n "{{PORT}}" -a -n "{{FIRMWARE}}" || (echo "PORT and FIRMWARE are required" >&2; exit 2)
    uv run python tools/firmware/flash_micropython.py \
        --port "{{PORT}}" \
        --firmware "{{FIRMWARE}}" \
        --sha256 "{{MICROPYTHON_SHA256}}"

verify-board:
    test -n "{{PORT}}" || (echo "PORT is required" >&2; exit 2)
    uv run python tools/firmware/verify_board.py --port "{{PORT}}"

deploy:
    test -n "{{PORT}}" || (echo "PORT is required" >&2; exit 2)
    uv run python tools/firmware/deploy.py --port "{{PORT}}"

repl:
    test -n "{{PORT}}" || (echo "PORT is required" >&2; exit 2)
    uv run mpremote connect "{{PORT}}" repl

device-ping:
    uv run paperbridge --port "{{PORT}}" device ping

device-info:
    uv run paperbridge --port "{{PORT}}" device info

ethernet-status:
    uv run paperbridge --port "{{PORT}}" ethernet status

printer-probe:
    uv run paperbridge --port "{{PORT}}" printer probe

print-test:
    uv run paperbridge --port "{{PORT}}" printer print-test "{{TEXT}}"

cut-test:
    uv run paperbridge --port "{{PORT}}" printer cut-test --confirm

serial-monitor:
    uv run paperbridge --port "{{PORT}}" serial monitor

printer-simulator:
    uv run python tools/printer-simulator/server.py

# Verify local Device configuration without printing secret values.
secrets-check:
    FNOX_CONFIG_DIR=/nonexistent fnox --no-daemon -P device exec -- python -c 'import os; names=("PAPERBRIDGE_MQTT_PASSWORD", "PAPERBRIDGE_WIFI_SSID", "PAPERBRIDGE_WIFI_PASSWORD"); missing=[name for name in names if not os.environ.get(name)]; assert not missing, missing'

# Generate disposable ignored firmware config without putting passwords in argv or shell history.
configure-device:
    FNOX_CONFIG_DIR=/nonexistent fnox --no-daemon -P device exec -- uv run python tools/provisioning/generate_device_config.py \
        --from-env \
        --output firmware/micropython/config.json

mqtt-probe:
    FNOX_CONFIG_DIR=/nonexistent fnox --no-daemon exec -- bun run mqtt:probe

# Private exe.dev production Host. Set PAPERBRIDGE_SHA to an exact reviewed SHA.
production-bootstrap:
    test -n "${PAPERBRIDGE_SHA:?PAPERBRIDGE_SHA is required}"
    tools/exedev/operator.sh bootstrap

# Verify the production MQTT credential without printing its value.
production-secrets-check:
    FNOX_CONFIG_DIR=/nonexistent fnox --no-daemon -P production exec -- python -c 'import os; assert os.environ.get("PAPERBRIDGE_MQTT_PASSWORD")'

production-configure:
    set -o pipefail; FNOX_CONFIG_DIR=/nonexistent fnox --no-daemon -P production exec -- tools/exedev/write-environment.sh | tools/exedev/operator.sh configure

production-deploy:
    test -n "${PAPERBRIDGE_SHA:?PAPERBRIDGE_SHA is required}"
    tools/exedev/operator.sh deploy

production-status:
    tools/exedev/operator.sh status

production-logs:
    tools/exedev/operator.sh logs

production-verify:
    tools/exedev/operator.sh verify

production-probe:
    tools/exedev/operator.sh probe

production-restart:
    tools/exedev/operator.sh restart

production-rollback:
    tools/exedev/operator.sh rollback

production-reboot:
    tools/exedev/operator.sh reboot

# Private single-device REST/MQTT service; defaults to 127.0.0.1:3000.
[continue]
api:
    status=0; FNOX_CONFIG_DIR=/nonexistent fnox --no-daemon exec -- bun run --filter @paperbridge/api start || status=$?; if [ "$status" -ne 0 ] && [ "$status" -ne 130 ]; then exit "$status"; fi

clean:
    rm -rf .pytest_cache .ruff_cache .venv captures
    find . -type d -name __pycache__ -prune -exec rm -rf {} +
