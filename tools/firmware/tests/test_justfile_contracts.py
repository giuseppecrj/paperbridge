from pathlib import Path

JUSTFILE = Path("justfile").read_text()


def test_flash_recipe_passes_known_micropython_sha256():
    assert "67c19ae123d84152019b57526ed5291dd0a2b4edd87655c5f76b46c9a62ff5dd" in JUSTFILE
    assert "--sha256" in JUSTFILE
    assert "flash-micropython" in JUSTFILE


def test_erase_requires_confirm_token_and_prints_port():
    assert "CONFIRM" in JUSTFILE
    assert 'CONFIRM" = "erase"' in JUSTFILE or 'CONFIRM}}" = "erase"' in JUSTFILE
    erase_block = JUSTFILE.split("erase-device:")[1].split("\n\n")[0]
    assert "erase" in erase_block
    assert "{{PORT}}" in erase_block
    assert "echo" in erase_block.lower() or "Erasing" in erase_block


def test_port_falls_back_to_paperbridge_port():
    assert "PAPERBRIDGE_PORT" in JUSTFILE
    # explicit PORT still wins via env_var_or_default("PORT", fallback)
    assert 'env_var_or_default("PORT"' in JUSTFILE
    assert "PAPERBRIDGE_PORT" in JUSTFILE.split("PORT :=")[1].split("\n")[0]


def test_soak_recipe_is_explicit_bounded_and_no_output():
    block = JUSTFILE.split("test-hardware-soak:")[1].split("\n\n")[0]
    assert "{{PORT}}" in block
    assert "soak" in block
    assert "--duration-seconds" in block
    assert "--interval-seconds" in block
    assert "print" not in block
    assert "feed" not in block
    assert "cut" not in block
