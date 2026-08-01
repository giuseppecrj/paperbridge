import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path("firmware/micropython")


def mpremote(port, *args):
    subprocess.run([sys.executable, "-m", "mpremote", "connect", port, *args], check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", required=True)
    args = parser.parse_args()
    config = ROOT / "config.json"
    if not config.exists():
        raise SystemExit(f"Create {config} from config.example.json before deploying")
    mpremote(args.port, "fs", "cp", str(ROOT / "boot.py"), ":boot.py")
    mpremote(args.port, "fs", "--recursive", "cp", str(ROOT / "src"), ":")
    mpremote(args.port, "fs", "cp", str(config), ":config.json")
    mpremote(args.port, "fs", "cp", str(ROOT / "main.py"), ":main.py")
    mpremote(args.port, "reset")


if __name__ == "__main__":
    main()
