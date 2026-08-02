from .constants import MAX_PRINT_BYTES

INITIALIZE = b"\x1b@"
# Verified on the purchased Rongta RP326 (2026-08-01): GS V 1 partial cut.
RP326_TEXT_COLUMNS = 48
RP326_PARTIAL_CUT = b"\x1dV\x01"


class RenderError(ValueError):
    def __init__(self, message, code="ESC_POS_RENDER_FAILED"):
        super().__init__(message)
        self.code = code


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
    def __init__(
        self,
        max_bytes=MAX_PRINT_BYTES,
        text_columns=RP326_TEXT_COLUMNS,
        partial_cut=RP326_PARTIAL_CUT,
    ):
        self.max_bytes = max_bytes
        self.text_columns = text_columns
        self.partial_cut = partial_cut

    def _bounded(self, payload):
        if len(payload) > self.max_bytes:
            raise RenderError("rendered job exceeds byte limit", "JOB_TOO_LARGE")
        return payload

    def render_text_test(self, text):
        return self._bounded(INITIALIZE + encode_text(text) + b"\n" * 3)

    def render_feed_test(self, lines=3):
        if not isinstance(lines, int) or not 1 <= lines <= 10:
            raise RenderError("feed lines must be 1..10")
        return INITIALIZE + b"\n" * lines

    def render_cut_test(self):
        return INITIALIZE + self.partial_cut

    def render(self, job, allow_cut=False):
        blocks = job["content"]["blocks"]
        payload = bytearray(INITIALIZE)
        for block in blocks:
            block_type = block["type"]
            if block_type == "text":
                payload.extend(encode_text(block["text"]))
                payload.extend(b"\n")
            elif block_type == "feed":
                lines = block["lines"]
                # bool is int subclass; reject so True never becomes one feed line
                if isinstance(lines, bool) or not isinstance(lines, int):
                    raise RenderError("feed.lines must be 1..10")
                if not 1 <= lines <= 10:
                    raise RenderError("feed.lines must be 1..10")
                payload.extend(b"\n" * lines)
            elif block_type == "rule":
                payload.extend(encode_text(block["character"]) * self.text_columns)
                payload.extend(b"\n")
            elif block_type == "cut":
                if not allow_cut:
                    raise RenderError("cut requires explicit allow_cut")
                if block.get("mode") != "partial":
                    raise RenderError("cut.mode must be partial")
                payload.extend(self.partial_cut)
            else:
                raise RenderError("unsupported block type")
        return self._bounded(bytes(payload))
