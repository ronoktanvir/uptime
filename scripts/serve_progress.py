#!/usr/bin/env python3
"""Serve only the read-only progress dashboard on loopback, without dependencies."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1] / "progress"


class ProgressHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        super().end_headers()

    def valid_request(self):
        hosts = self.headers.get_all("Host", [])
        port = self.server.server_address[1]
        allowed = {f"127.0.0.1:{port}", f"localhost:{port}"}
        if len(hosts) != 1 or hosts[0].lower() not in allowed:
            self.send_error(421)
            return False
        if ".." in unquote(urlsplit(self.path).path).split("/"):
            self.send_error(404)
            return False
        requested = Path(self.translate_path(self.path)).resolve()
        if not requested.is_relative_to(ROOT.resolve()) or requested.is_dir() and requested != ROOT.resolve():
            self.send_error(404)
            return False
        return True

    def do_GET(self):
        if self.valid_request():
            super().do_GET()

    def do_HEAD(self):
        if self.valid_request():
            super().do_HEAD()

    def list_directory(self, path):
        self.send_error(404)
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8780)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), partial(ProgressHandler, directory=str(ROOT)))
    print(f"Uptime delivery map: http://127.0.0.1:{server.server_address[1]}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
