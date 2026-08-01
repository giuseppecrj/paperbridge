def create_watchdog(timeout_ms=10000):
    machine = __import__("machine")
    return machine.WDT(timeout=timeout_ms)
