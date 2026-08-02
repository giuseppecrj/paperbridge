set dotenv-load := true

PORT := env_var_or_default("PORT", env_var_or_default("PAPERBRIDGE_PORT", ""))
FIRMWARE := env_var_or_default("FIRMWARE", "")
CONFIRM := env_var_or_default("CONFIRM", "")
TEXT := env_var_or_default("TEXT", "Hello from my Mac")
SOAK_DURATION_SECONDS := env_var_or_default("SOAK_DURATION_SECONDS", "259200")
SOAK_INTERVAL_SECONDS := env_var_or_default("SOAK_INTERVAL_SECONDS", "60")

# Verified ESP32_GENERIC_S3-SPIRAM_OCT-20260406-v1.28.0.bin (docs/micropython-bringup.md)
MICROPYTHON_SHA256 := "67c19ae123d84152019b57526ed5291dd0a2b4edd87655c5f76b46c9a62ff5dd"

bootstrap:
    uv sync

lint:
    uv run ruff check .

format:
    uv run ruff format .

format-check:
    uv run ruff format --check .

test:
    uv run pytest

# Opt-in HIL: never part of ordinary `just test`. Requires a selected PORT.
test-hardware-smoke:
    test -n "{{PORT}}" || (echo "PORT is required" >&2; exit 2)
    uv run python tools/hardware/hil.py smoke --port "{{PORT}}"

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

clean:
    rm -rf .pytest_cache .ruff_cache .venv captures
    find . -type d -name __pycache__ -prune -exec rm -rf {} +
