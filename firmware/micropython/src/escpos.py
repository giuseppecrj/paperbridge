from .constants import MAX_PRINT_BYTES

INITIALIZE = b"\x1b@"
# Verified on the purchased Rongta RP326 (2026-08-01): GS V 1 partial cut.
RP326_TEXT_COLUMNS = 48
RP326_PARTIAL_CUT = b"\x1dV\x01"
STYLE_FIELDS = ("align", "bold", "underline", "width_multiplier", "height_multiplier")
STYLE_RESET = b"\x1ba\x00\x1bE\x00\x1b-\x00\x1d!\x00"
QR_MODEL_2 = b"\x1d(k\x04\x00\x31\x41\x32\x00"
QR_MODULE_SIZE_3 = b"\x1d(k\x03\x00\x31\x43\x03"
QR_ERROR_CORRECTION_M = b"\x1d(k\x03\x00\x31\x45\x31"
QR_PRINT = b"\x1d(k\x03\x00\x31\x51\x30"


class RenderError(ValueError):
    def __init__(self, message, code="ESC_POS_RENDER_FAILED"):
        super().__init__(message)
        self.code = code


def encode_text(text):
    if not isinstance(text, str) or not text:
        raise RenderError("text must be a non-empty string")
    encoded = bytearray()
    for character in text:
        code = ord(character)
        if code < 32 or code == 127:
            raise RenderError("text contains control characters")
        if code > 126:
            raise RenderError("text must contain printable ASCII only")
        encoded.append(code)
    return bytes(encoded)


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

    def _append(self, payload, chunk):
        if len(payload) + len(chunk) > self.max_bytes:
            raise RenderError("rendered job exceeds byte limit", "JOB_TOO_LARGE")
        payload.extend(chunk)

    def _style_setup(self, block):
        align = block.get("align", "left")
        if align not in ("left", "center", "right"):
            raise RenderError("text.align must be left, center, or right")
        alignment = {"left": 0, "center": 1, "right": 2}[align]
        bold = block.get("bold", False)
        underline = block.get("underline", False)
        if not isinstance(bold, bool):
            raise RenderError("text.bold must be a boolean")
        if not isinstance(underline, bool):
            raise RenderError("text.underline must be a boolean")
        width = block.get("width_multiplier", 1)
        height = block.get("height_multiplier", 1)
        for field, value in (("width_multiplier", width), ("height_multiplier", height)):
            if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 2:
                raise RenderError(f"text.{field} must be 1..2")
        size = ((width - 1) << 4) | (height - 1)
        return (
            b"\x1ba"
            + bytes((alignment,))
            + b"\x1bE"
            + bytes((1 if bold else 0,))
            + b"\x1b-"
            + bytes((1 if underline else 0,))
            + b"\x1d!"
            + bytes((size,))
        )

    def _append_qr(self, payload, data):
        encoded = encode_text(data)
        if len(encoded) > 256:
            raise RenderError("qr.data must be 1..256 printable ASCII bytes")
        self._append(payload, b"\x1ba\x01")
        self._append(payload, QR_MODEL_2)
        self._append(payload, QR_MODULE_SIZE_3)
        self._append(payload, QR_ERROR_CORRECTION_M)
        length = len(encoded) + 3
        store = b"\x1d(k" + bytes((length & 0xFF, length >> 8, 0x31, 0x50, 0x30))
        self._append(payload, store)
        self._append(payload, encoded)
        self._append(payload, QR_PRINT)
        self._append(payload, STYLE_RESET)

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
        payload = bytearray()
        self._append(payload, INITIALIZE)
        for block in blocks:
            block_type = block["type"]
            if block_type == "text":
                encoded = encode_text(block["text"])
                if any(field in block for field in STYLE_FIELDS):
                    self._append(payload, self._style_setup(block))
                    self._append(payload, encoded)
                    self._append(payload, b"\n")
                    self._append(payload, STYLE_RESET)
                else:
                    self._append(payload, encoded)
                    self._append(payload, b"\n")
            elif block_type == "qr":
                self._append_qr(payload, block["data"])
            elif block_type == "feed":
                lines = block["lines"]
                # bool is int subclass; reject so True never becomes one feed line
                if isinstance(lines, bool) or not isinstance(lines, int):
                    raise RenderError("feed.lines must be 1..10")
                if not 1 <= lines <= 10:
                    raise RenderError("feed.lines must be 1..10")
                self._append(payload, b"\n" * lines)
            elif block_type == "rule":
                self._append(payload, encode_text(block["character"]) * self.text_columns)
                self._append(payload, b"\n")
            elif block_type == "cut":
                if not allow_cut:
                    raise RenderError("cut requires explicit allow_cut")
                if block.get("mode") != "partial":
                    raise RenderError("cut.mode must be partial")
                self._append(payload, self.partial_cut)
            else:
                raise RenderError("unsupported block type")
        return self._bounded(bytes(payload))
