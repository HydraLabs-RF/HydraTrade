"""
Start the HydraTrade local web UI.

Usage:
    python run_webui.py            # default port 8350, opens browser
    python run_webui.py --port 9000 --no-browser
"""

import argparse
import threading
import webbrowser

from core.branding import print_banner, log
from webui.server import serve


def main():
    parser = argparse.ArgumentParser(description="HydraTrade Web UI")
    parser.add_argument("--port", type=int, default=8350)
    parser.add_argument("--no-browser", action="store_true", help="Do not open browser automatically")
    args = parser.parse_args()

    print_banner()
    log(f"Web UI at http://127.0.0.1:{args.port}")

    if not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(f"http://127.0.0.1:{args.port}")).start()

    serve(args.port)


if __name__ == "__main__":
    main()
