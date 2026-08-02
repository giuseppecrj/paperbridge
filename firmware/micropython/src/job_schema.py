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


def _printable_ascii(value, field):
    _bounded_string(value, field, 2048)
    for character in value:
        code = ord(character)
        if code < _PRINTABLE_ASCII_MIN or code > _PRINTABLE_ASCII_MAX:
            raise JobValidationError(f"{field} must contain printable ASCII only")


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
            _reject_unknown_keys(block, {"type", "text"}, "text")
            _printable_ascii(block.get("text"), "text")
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
