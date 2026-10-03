import argparse
import json

from .service import MarketScanner, ScannerConfig


def main():
    parser = argparse.ArgumentParser(description="Live Alpaca US-stock activity scanner; no orders")
    parser.add_argument("--top", type=int, default=20)
    parser.add_argument("--feed", choices=("iex", "sip", "delayed_sip"))
    args = parser.parse_args()
    print(json.dumps(MarketScanner(config=ScannerConfig(top_n=args.top, feed=args.feed)).scan(), indent=2))


if __name__ == "__main__":
    main()
