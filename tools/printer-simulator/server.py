import argparse
import hashlib
import json
import socket
import struct
import time
from pathlib import Path


class CaptureStore:
    def __init__(self, directory):
        self.directory = Path(directory)

    def record(self, payload, peer):
        self.directory.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256(payload).hexdigest()
        stamp = time.time_ns()
        payload_path = self.directory / f"{stamp}-{digest[:12]}.bin"
        payload_path.write_bytes(payload)
        metadata = {
            "bytes": len(payload),
            "peer": f"{peer[0]}:{peer[1]}",
            "sha256": digest,
            "path": str(payload_path),
        }
        (payload_path.with_suffix(".json")).write_text(json.dumps(metadata, indent=2) + "\n")
        return metadata


def _receive(connection, args):
    payload = bytearray()
    while True:
        if args.read_delay:
            time.sleep(args.read_delay)
        chunk = connection.recv(args.read_size)
        if not chunk:
            break
        payload.extend(chunk)
        if args.reset_after and len(payload) >= args.reset_after:
            connection.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
            connection.close()
            return bytes(payload), "reset"
        if args.close_after and len(payload) >= args.close_after:
            connection.close()
            return bytes(payload), "closed"
    return bytes(payload), "complete"


def serve(args, max_connections=None, ready=None):
    store = CaptureStore(args.capture_dir)
    handled = 0
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((args.host, args.port))
        server.listen(5)
        if ready is not None:
            ready.set()
        print(json.dumps({"listening": f"{args.host}:{server.getsockname()[1]}"}), flush=True)
        while max_connections is None or handled < max_connections:
            if args.accept_delay:
                time.sleep(args.accept_delay)
            connection, peer = server.accept()
            with connection:
                payload, outcome = _receive(connection, args)
            metadata = store.record(payload, peer)
            metadata["outcome"] = outcome
            print(json.dumps(metadata, sort_keys=True), flush=True)
            handled += 1


def _parser():
    parser = argparse.ArgumentParser(description="Capture TCP printer payloads")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9100)
    parser.add_argument("--capture-dir", default="captures")
    parser.add_argument("--accept-delay", type=float, default=0)
    parser.add_argument("--read-delay", type=float, default=0)
    parser.add_argument(
        "--read-size", type=int, default=1024, help="small values simulate partial reads"
    )
    parser.add_argument("--close-after", type=int, default=0)
    parser.add_argument("--reset-after", type=int, default=0)
    return parser


def main():
    args = _parser().parse_args()
    try:
        serve(args)
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
