import sys

app = __import__("src.app", None, None, ("run",))
logging = __import__("src.logging", None, None, ("log",))

try:
    app.run()
except Exception as exc:
    logging.log(sys.stdout, "error", "application stopped", error=str(exc))
    raise
