from .constants import JOB_STATUSES

ALLOWED_TRANSITIONS = {
    "received": ("validated", "rejected", "expired"),
    "validated": ("rendering", "rejected", "expired"),
    "rendering": ("connecting_to_printer", "failed"),
    "connecting_to_printer": ("sending_to_printer", "failed"),
    "sending_to_printer": ("delivered_to_printer", "failed"),
    "delivered_to_printer": (),
    "failed": (),
    "rejected": (),
    "expired": (),
}


class StatusTracker:
    def __init__(self):
        self.current = "received"

    def transition(self, status):
        if status not in JOB_STATUSES or status not in ALLOWED_TRANSITIONS[self.current]:
            raise ValueError(f"invalid status transition: {self.current} -> {status}")
        self.current = status
        return status
