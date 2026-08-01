import argparse
import socket

PAYLOAD = b"\x1b@Hello from Paperbridge diagnostic\n\n\n"


def main():
    parser = argparse.ArgumentParser(description="Direct network diagnostic; not the normal path")
    parser.add_argument("host")
    parser.add_argument("--port", type=int, default=9100)
    parser.add_argument("--confirm-direct", action="store_true", required=True)
    args = parser.parse_args()
    with socket.create_connection((args.host, args.port), timeout=3) as connection:
        connection.sendall(PAYLOAD)
    print(f"delivered_to_printer: {len(PAYLOAD)} bytes")


if __name__ == "__main__":
    main()
