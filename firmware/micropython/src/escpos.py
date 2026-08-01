from .constants import MAX_PRINT_BYTES

INITIALIZE = b"\x1b@"
DEFAULT_PARTIAL_CUT = b"\x1dV\x01"  # Unverified on the purchased RP326; explicit test only.


class RenderError(ValueError):
    pass


def encode_text(text):
    if not isinstance(text, str) or not text:
        raise RenderError("text must be a non-empty string")
    if any(ord(character) < 32 or ord(character) == 127 for character in text):
        raise RenderError("text contains control characters")
    try:
        return text.encode("ascii")
    except UnicodeError:
        raise RenderError("text must contain printable ASCII only") from None


class EscPosRenderer:
    def __init__(self, max_bytes=MAX_PRINT_BYTES, partial_cut=DEFAULT_PARTIAL_CUT):
        self.max_bytes = max_bytes
        self.partial_cut = partial_cut

    def _bounded(self, payload):
        if len(payload) > self.max_bytes:
            raise RenderError("rendered job exceeds byte limit")
        return payload

    def render_text_test(self, text):
        return self._bounded(INITIALIZE + encode_text(text) + b"\n" * 3)

    def render_feed_test(self, lines=3):
        if not isinstance(lines, int) or not 1 <= lines <= 10:
            raise RenderError("feed lines must be 1..10")
        return INITIALIZE + b"\n" * lines

    def render_cut_test(self):
        return INITIALIZE + self.partial_cut

    def render(self, job):
        blocks = job["content"]["blocks"]
        payload = bytearray(INITIALIZE)
        for block in blocks:
            block_type = block["type"]
            if block_type == "text":
                payload.extend(encode_text(block["text"]))
                payload.extend(b"\n")
            elif block_type == "feed":
                payload.extend(b"\n" * block["lines"])
            elif block_type == "rule":
                payload.extend(encode_text(block.get("character", "-")) * 48)
                payload.extend(b"\n")
            elif block_type == "cut":
                payload.extend(self.partial_cut)
            else:
                raise RenderError("unsupported block type")
        return self._bounded(bytes(payload))
