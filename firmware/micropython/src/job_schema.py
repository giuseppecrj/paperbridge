class JobValidationError(ValueError):
    pass


def _bounded_string(value, field, maximum):
    if not isinstance(value, str) or not 1 <= len(value) <= maximum:
        raise JobValidationError(f"{field} must be 1..{maximum} characters")


def validate_job(job, allow_cut=False):
    if not isinstance(job, dict) or job.get("schema_version") != "1":
        raise JobValidationError("unsupported schema_version")
    for field in ("job_id", "device_id", "created_at"):
        _bounded_string(job.get(field), field, 128)
    content = job.get("content")
    if not isinstance(content, dict) or content.get("kind") != "receipt":
        raise JobValidationError("content.kind must be receipt")
    blocks = content.get("blocks")
    if not isinstance(blocks, list) or not 1 <= len(blocks) <= 100:
        raise JobValidationError("content.blocks must contain 1..100 blocks")
    for block in blocks:
        if not isinstance(block, dict):
            raise JobValidationError("each block must be an object")
        block_type = block.get("type")
        if block_type == "text":
            _bounded_string(block.get("text"), "text", 2048)
        elif block_type == "feed":
            if not isinstance(block.get("lines"), int) or not 1 <= block["lines"] <= 10:
                raise JobValidationError("feed.lines must be 1..10")
        elif block_type == "rule":
            _bounded_string(block.get("character", "-"), "rule.character", 1)
        elif block_type == "cut" and allow_cut:
            if block.get("mode") != "partial":
                raise JobValidationError("cut.mode must be partial")
        else:
            raise JobValidationError("unsupported block type")
    copies = job.get("options", {}).get("copies", 1)
    if not isinstance(copies, int) or not 1 <= copies <= 3:
        raise JobValidationError("options.copies must be 1..3")
    return job
