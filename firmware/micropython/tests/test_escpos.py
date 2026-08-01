from pathlib import Path

import pytest
from src.escpos import EscPosRenderer, RenderError, encode_text


def test_text_fixture_bytes_are_exact():
    expected = Path("packages/protocol/fixtures/expected-hello-world.bin").read_bytes()
    assert EscPosRenderer().render_text_test("Hello from Paperbridge") == expected
    assert b"\x1dV" not in expected


@pytest.mark.parametrize("text", ["café", "hello\x1b@", "line\nbreak", ""])
def test_text_rejects_unicode_and_control_bytes(text):
    with pytest.raises(RenderError):
        encode_text(text)


def test_cut_is_separate_from_text_and_feed():
    renderer = EscPosRenderer()
    assert renderer.render_cut_test() == b"\x1b@\x1dV\x01"
    assert renderer.render_feed_test() == b"\x1b@\n\n\n"
