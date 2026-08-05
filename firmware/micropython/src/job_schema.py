import binascii

MAX_RASTER_WIDTH = 128
MAX_RASTER_HEIGHT = 24
MAX_RASTER_BYTES = 384
_BASE64_CHARACTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"


class JobValidationError(ValueError):
    def __init__(self, message, code="INVALID_PRINT_JOB"):
        super().__init__(message)
        self.code = code


_PRINTABLE_ASCII_MIN = 32
_PRINTABLE_ASCII_MAX = 126


def _require_object(value, field):
    if not isinstance(value, dict):
        raise JobValidationError(f"{field} must be an object")


def _bounded_string(value, field, maximum, minimum=1):
    if not isinstance(value, str) or not minimum <= len(value) <= maximum:
        raise JobValidationError(f"{field} must be {minimum}..{maximum} characters")


def _printable_ascii(value, field, maximum=2048):
    _bounded_string(value, field, maximum)
    for character in value:
        code = ord(character)
        if code < _PRINTABLE_ASCII_MIN or code > _PRINTABLE_ASCII_MAX:
            raise JobValidationError(f"{field} must contain printable ASCII only")


def decode_raster(block):
    width = block.get("width")
    height = block.get("height")
    data_base64 = block.get("data_base64")
    if (
        isinstance(width, bool)
        or isinstance(height, bool)
        or not isinstance(width, int)
        or not isinstance(height, int)
        or not 1 <= width <= MAX_RASTER_WIDTH
        or not 1 <= height <= MAX_RASTER_HEIGHT
    ):
        raise ValueError("raster dimensions must be 1..128 by 1..24")
    if not isinstance(data_base64, str) or not 4 <= len(data_base64) <= 512 or len(data_base64) % 4:
        raise ValueError("raster.data_base64 must be canonical base64")
    padding = data_base64.find("=")
    content = data_base64 if padding < 0 else data_base64[:padding]
    if not content or any(character not in _BASE64_CHARACTERS for character in content):
        raise ValueError("raster.data_base64 must be canonical base64")
    if padding >= 0 and data_base64[padding:] not in ("=", "=="):
        raise ValueError("raster.data_base64 must be canonical base64")
    try:
        raw = binascii.a2b_base64(data_base64)
    except (ValueError, TypeError) as exc:
        raise ValueError("raster.data_base64 must be canonical base64") from exc
    row_bytes = (width + 7) // 8
    if len(raw) != row_bytes * height or len(raw) > MAX_RASTER_BYTES:
        raise ValueError("raster.data_base64 length does not match dimensions")
    return width, height, raw


def _reject_unknown_keys(value, allowed, field):
    unknown = set(value) - allowed
    if unknown:
        raise JobValidationError(f"{field} has unsupported properties: {sorted(unknown)[0]}")


def validate_job(job, allow_cut=False):
    _require_object(job, "job")
    _reject_unknown_keys(
        job,
        {"schema_version", "job_id", "device_id", "created_at", "content"},
        "job",
    )
    if job.get("schema_version") != "1":
        raise JobValidationError("unsupported schema_version")
    _bounded_string(job.get("job_id"), "job_id", 128)
    _bounded_string(job.get("device_id"), "device_id", 64)
    _bounded_string(job.get("created_at"), "created_at", 64)

    content = job.get("content")
    _require_object(content, "content")
    _reject_unknown_keys(content, {"kind", "blocks"}, "content")
    if content.get("kind") != "receipt":
        raise JobValidationError("content.kind must be receipt")
    blocks = content.get("blocks")
    if not isinstance(blocks, list) or not 1 <= len(blocks) <= 100:
        raise JobValidationError("content.blocks must contain 1..100 blocks")

    for block in blocks:
        _require_object(block, "block")
        block_type = block.get("type")
        if block_type == "text":
            _reject_unknown_keys(
                block,
                {
                    "type",
                    "text",
                    "align",
                    "bold",
                    "underline",
                    "width_multiplier",
                    "height_multiplier",
                },
                "text",
            )
            _printable_ascii(block.get("text"), "text")
            if "align" in block and block["align"] not in ("left", "center", "right"):
                raise JobValidationError("text.align must be left, center, or right")
            for field in ("bold", "underline"):
                if field in block and not isinstance(block[field], bool):
                    raise JobValidationError(f"text.{field} must be a boolean")
            for field in ("width_multiplier", "height_multiplier"):
                value = block.get(field)
                if field in block and (
                    isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 2
                ):
                    raise JobValidationError(f"text.{field} must be 1..2")
        elif block_type == "qr":
            _reject_unknown_keys(block, {"type", "data", "module_size"}, "qr")
            _printable_ascii(block.get("data"), "qr.data", 256)
            module_size = block.get("module_size", 3)
            if (
                isinstance(module_size, bool)
                or not isinstance(module_size, int)
                or not 1 <= module_size <= 8
            ):
                raise JobValidationError("qr.module_size must be 1..8")
        elif block_type == "raster":
            _reject_unknown_keys(block, {"type", "width", "height", "data_base64"}, "raster")
            try:
                decode_raster(block)
            except ValueError as exc:
                raise JobValidationError(str(exc)) from exc
        elif block_type == "feed":
            _reject_unknown_keys(block, {"type", "lines"}, "feed")
            lines = block.get("lines")
            # bool is int subclass in Python; reject so True is not accepted as 1
            if isinstance(lines, bool) or not isinstance(lines, int) or not 1 <= lines <= 10:
                raise JobValidationError("feed.lines must be 1..10")
        elif block_type == "rule":
            _reject_unknown_keys(block, {"type", "character"}, "rule")
            character = block.get("character")
            if not isinstance(character, str) or len(character) != 1:
                raise JobValidationError("rule.character must be 1 printable ASCII character")
            _printable_ascii(character, "rule.character")
        elif block_type == "cut":
            if not allow_cut:
                raise JobValidationError("cut requires explicit allow_cut", "UNAUTHORIZED_CUT")
            _reject_unknown_keys(block, {"type", "mode"}, "cut")
            if block.get("mode") != "partial":
                raise JobValidationError("cut.mode must be partial")
        else:
            raise JobValidationError("unsupported block type")
    return job
