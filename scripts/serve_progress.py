#!/usr/bin/env python3
"""Serve only the read-only progress dashboard on loopback, without dependencies."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "progress"


class ProgressHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        super().end_headers()

    def do_GET(self):
        requested = Path(self.translate_path(self.path)).resolve()
        if not requested.is_relative_to(ROOT.resolve()) or requested.is_dir() and requested != ROOT.resolve():
            self.send_error(404)
            return
        super().do_GET()

    def do_HEAD(self):
        requested = Path(self.translate_path(self.path)).resolve()
        if not requested.is_relative_to(ROOT.resolve()) or requested.is_dir() and requested != ROOT.resolve():
            self.send_error(404)
            return
        super().do_HEAD()

    def list_directory(self, path):
        self.send_error(404)
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), partial(ProgressHandler, directory=str(ROOT)))
    print(f"Uptime delivery map: http://127.0.0.1:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
