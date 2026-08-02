import json
from pathlib import Path

import pytest
from src.escpos import (
    RP326_PARTIAL_CUT,
    RP326_TEXT_COLUMNS,
    EscPosRenderer,
    RenderError,
    encode_text,
)

FIXTURES = Path("packages/protocol/fixtures/print-job-v1")


def load(name):
    return json.loads((FIXTURES / name).read_text())


def test_text_fixture_bytes_are_exact():
    expected = Path("packages/protocol/fixtures/expected-hello-world.bin").read_bytes()
    assert EscPosRenderer().render_text_test("Hello from Paperbridge") == expected
    assert b"\x1dV" not in expected


def test_text_encoding_does_not_depend_on_micropython_ascii_codec_lookup():
    class DeviceString(str):
        def encode(self, *_args, **_kwargs):
            raise RuntimeError("maximum recursion depth exceeded")

    assert encode_text(DeviceString("Hello")) == b"Hello"


@pytest.mark.parametrize("text", ["café", "hello\x1b@", "line\nbreak", ""])
def test_text_rejects_unicode_and_control_bytes(text):
    with pytest.raises(RenderError):
        encode_text(text)


def test_cut_is_separate_from_text_and_feed():
    renderer = EscPosRenderer()
    assert renderer.render_cut_test() == b"\x1b@" + RP326_PARTIAL_CUT
    assert renderer.render_feed_test() == b"\x1b@\n\n\n"
    assert RP326_PARTIAL_CUT == b"\x1dV\x01"
    assert RP326_TEXT_COLUMNS == 48


def test_render_shared_text_feed_fixture():
    payload = EscPosRenderer().render(load("valid-text-feed.json"))
    assert payload == b"\x1b@Hello from Paperbridge\n\n\n\n"
    assert b"\x1dV" not in payload


def test_render_shared_rule_fixture_uses_rp326_columns():
    payload = EscPosRenderer().render(load("valid-rule.json"))
    assert payload == b"\x1b@TOTAL\n" + (b"-" * 48) + b"\n\n"


def test_render_styled_text_uses_exact_commands_and_resets():
    payload = EscPosRenderer().render(load("valid-styled-text.json"))
    assert payload == (
        b"\x1b@\x1ba\x01\x1bE\x01\x1b-\x00\x1d!\x10Styled\n\x1ba\x00\x1bE\x00\x1b-\x00\x1d!\x00"
    )


def test_render_styled_text_does_not_leak_to_next_block():
    job = {
        "content": {
            "blocks": [
                {"type": "text", "text": "Bold", "bold": True},
                {"type": "text", "text": "Plain"},
            ]
        }
    }
    assert EscPosRenderer().render(job) == (
        b"\x1b@\x1ba\x00\x1bE\x01\x1b-\x00\x1d!\x00Bold\n"
        b"\x1ba\x00\x1bE\x00\x1b-\x00\x1d!\x00Plain\n"
    )


def test_render_qr_uses_fixed_epson_commands_and_centering():
    payload = EscPosRenderer().render(load("valid-qr.json"))
    assert payload == (
        b"\x1b@\x1ba\x01"
        b"\x1d(k\x04\x00\x31\x41\x32\x00"
        b"\x1d(k\x03\x00\x31\x43\x03"
        b"\x1d(k\x03\x00\x31\x45\x31"
        b"\x1d(k\x22\x00\x31\x50\x30https://example.com/paperbridge"
        b"\x1d(k\x03\x00\x31\x51\x30"
        b"\x1ba\x00\x1bE\x00\x1b-\x00\x1d!\x00"
    )


def test_render_qr_uses_bounded_module_size():
    payload = EscPosRenderer().render(
        {
            "content": {
                "blocks": [
                    {
                        "type": "qr",
                        "data": "https://example.com/paperbridge",
                        "module_size": 5,
                    }
                ]
            }
        }
    )
    assert b"\x1d(k\x03\x00\x31\x43\x05" in payload


@pytest.mark.parametrize("module_size", [0, 9, True])
def test_render_rejects_invalid_qr_module_size(module_size):
    with pytest.raises(RenderError, match="qr.module_size must be 1..8"):
        EscPosRenderer().render(
            {
                "content": {
                    "blocks": [
                        {"type": "qr", "data": "https://example.com", "module_size": module_size}
                    ]
                }
            }
        )


def test_render_rejects_qr_output_before_growing_past_limit():
    with pytest.raises(RenderError, match="rendered job exceeds byte limit"):
        EscPosRenderer(max_bytes=32).render(load("valid-qr.json"))


def test_render_shared_rich_receipt_matches_binary_fixture():
    expected = Path("packages/protocol/fixtures/expected-rich-receipt.bin").read_bytes()
    assert EscPosRenderer().render(load("valid-rich-receipt.json")) == expected


def test_render_shared_cut_fixture_requires_opt_in():
    cut_job = load("valid-cut.json")
    with pytest.raises(RenderError, match="allow_cut"):
        EscPosRenderer().render(cut_job)
    payload = EscPosRenderer().render(cut_job, allow_cut=True)
    assert payload == b"\x1b@Cut me\n" + RP326_PARTIAL_CUT


def test_render_rejects_boolean_feed_lines():
    with pytest.raises(RenderError, match="feed.lines"):
        EscPosRenderer().render(
            {
                "content": {
                    "blocks": [{"type": "feed", "lines": True}],
                }
            }
        )
