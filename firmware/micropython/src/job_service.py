from .job_schema import JobValidationError, validate_job
from .serial_rpc import RpcError


class JobService:
    """Validate and deliver one semantic job for any trusted ingress."""

    def __init__(self, config, coordinator):
        self.config = config
        self.coordinator = coordinator

    def submit(self, job, allow_cut=False, before_delivery=None):
        try:
            validate_job(job, allow_cut=allow_cut)
        except JobValidationError as exc:
            raise RpcError(exc.code, str(exc)) from exc
        if job["device_id"] != self.config["device_id"]:
            raise RpcError("WRONG_DEVICE", "job device_id does not match this device")
        if before_delivery is not None:
            before_delivery()
        return self.coordinator.print_job(job, allow_cut=allow_cut)
