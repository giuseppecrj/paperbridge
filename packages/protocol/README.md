# Shared protocol

Versioned schemas for serial RPC, semantic print jobs, and device events. Public
clients never supply raw ESC/POS. `cut` exists in the schema contract but device
execution remains disabled unless the purchased printer command is physically
verified and explicitly requested.
