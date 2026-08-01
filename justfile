set dotenv-load := true

PORT := env_var_or_default("PORT", "")
FIRMWARE := env_var_or_default("FIRMWARE", "")
TEXT := env_var_or_default("TEXT", "Hello from my Mac")

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

ports:
    uv run paperbridge ports list

erase-device:
    test -n "{{PORT}}" || (echo "PORT is required" >&2; exit 2)
    uv run esptool --port "{{PORT}}" erase-flash

flash-micropython:
    test -n "{{PORT}}" -a -n "{{FIRMWARE}}" || (echo "PORT and FIRMWARE are required" >&2; exit 2)
    uv run python tools/firmware/flash_micropython.py --port "{{PORT}}" --firmware "{{FIRMWARE}}"

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
