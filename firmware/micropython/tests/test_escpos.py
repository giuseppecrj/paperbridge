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
