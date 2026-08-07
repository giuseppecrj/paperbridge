FIRMWARE_VERSION = "0.1.0"
DEFAULT_MAX_LINE_BYTES = 64 * 1024
MAX_PRINT_BYTES = 64 * 1024

JOB_RESULT_ERROR_CODES = {
    "INVALID_PRINT_JOB",
    "WRONG_DEVICE",
    "UNAUTHORIZED_CUT",
    "JOB_TOO_LARGE",
    "ETHERNET_LINK_DOWN",
    "PRINTER_CONNECT_TIMEOUT",
    "PRINTER_CONNECTION_REFUSED",
    "PRINTER_WRITE_TIMEOUT",
    "PRINTER_CONNECTION_RESET",
    "ESC_POS_RENDER_FAILED",
    "DUPLICATE_JOB",
    "INTERNAL_ERROR",
}

JOB_STATUSES = (
    "received",
    "validated",
    "rendering",
    "connecting_to_printer",
    "sending_to_printer",
    "delivered_to_printer",
    "failed",
    "rejected",
    "expired",
)
