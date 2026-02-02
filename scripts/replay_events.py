import argparse
import sys

import requests


def main():
    parser = argparse.ArgumentParser(description="Replay demo events into a running server")
    parser.add_argument("--url", default="http://127.0.0.1:5000", help="Base URL")
    parser.add_argument("--limit", type=int, default=60, help="Number of events")
    parser.add_argument("--delay-ms", type=int, default=800, help="Delay between events")
    args = parser.parse_args()

    endpoint = f"{args.url.rstrip('/')}/api/demo/replay"
    try:
        response = requests.post(
            endpoint,
            json={"limit": args.limit, "delay_ms": args.delay_ms},
            timeout=5,
        )
    except requests.RequestException as exc:
        print(f"Request failed: {exc}")
        sys.exit(1)

    if response.status_code != 200:
        print(f"Replay failed: {response.status_code} {response.text}")
        sys.exit(1)

    data = response.json()
    if not data.get("success"):
        print(f"Replay failed: {data}")
        sys.exit(1)

    print(f"Replay started ({data.get('replayed', 0)} events queued).")


if __name__ == "__main__":
    main()
