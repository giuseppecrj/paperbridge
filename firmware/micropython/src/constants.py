FIRMWARE_VERSION = "0.1.0"
PROTOCOL_VERSION = "1"
DEFAULT_MAX_LINE_BYTES = 4096
MAX_PRINT_BYTES = 32 * 1024

ERROR_CODES = {
    "INVALID_RPC_REQUEST",
    "UNSUPPORTED_RPC_COMMAND",
    "INVALID_CONFIGURATION",
    "ETHERNET_INITIALIZATION_FAILED",
    "ETHERNET_LINK_DOWN",
    "PRINTER_CONNECT_TIMEOUT",
    "PRINTER_CONNECTION_REFUSED",
    "PRINTER_WRITE_TIMEOUT",
    "PRINTER_CONNECTION_RESET",
    "ESC_POS_RENDER_FAILED",
    "JOB_TOO_LARGE",
    "QUEUE_FULL",
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
