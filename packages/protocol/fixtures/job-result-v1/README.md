# job-result.v1 fixtures

Closed correlated terminal results shared by the TypeScript API and firmware tests.
Success requires `bytes_sent`; rejection requires a stable `error_code`; delivery
failure requires a stable `error_code` and includes `bytes_sent` only when a
partial write occurred. One-boot QoS redelivery uses `duplicate` with
`DUPLICATE_JOB` and never includes `bytes_sent`.
