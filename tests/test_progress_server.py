"""The project dashboard serves its explicit public snapshot only on loopback."""
from functools import partial
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from threading import Thread

import pytest

from scripts import serve_progress


@pytest.fixture
def progress_server(tmp_path, monkeypatch):
    public = tmp_path / "progress"
    public.mkdir()
    (public / "index.html").write_text("<h1>Progress</h1>")
    (public / "data.json").write_text('{"nodes": []}')
    private = tmp_path / "private.txt"
    private.write_text("private-canary")
    (public / "linked.txt").symlink_to(private)
    (public / "empty").mkdir()
    monkeypatch.setattr(serve_progress, "ROOT", public)
    handler = partial(serve_progress.ProgressHandler, directory=str(public))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)


def response(server, path, host=None, method="GET"):
    client = HTTPConnection(*server.server_address, timeout=5)
    headers = {} if host is None else {"Host": host}
    client.request(method, path, headers=headers)
    result = client.getresponse()
    status, body, cache = result.status, result.read(), result.getheader("Cache-Control")
    client.close()
    return status, body, cache


@pytest.mark.parametrize("method", ["GET", "HEAD"])
def test_local_snapshot_and_headers(progress_server, method):
    assert progress_server.server_address[0] == "127.0.0.1"
    status, body, cache = response(progress_server, "/data.json", method=method)
    assert status == 200 and cache == "no-store"
    assert body == (b'{"nodes": []}' if method == "GET" else b"")


@pytest.mark.parametrize("path", ["/../", "/%2e%2e/private.txt", "/linked.txt", "/empty/", "/private.txt"])
def test_traversal_symlink_and_directory_refused(progress_server, path):
    status, body, _ = response(progress_server, path)
    assert status == 404
    assert b"private-canary" not in body


@pytest.mark.parametrize("host", ["evil.example", "127.0.0.1.evil.example", "localhost:1"])
def test_foreign_host_refused(progress_server, host):
    status, body, _ = response(progress_server, "/data.json", host)
    assert status == 421 and b'"nodes"' not in body


def test_missing_index_cannot_list_directory(progress_server):
    (serve_progress.ROOT / "index.html").unlink()
    status, body, _ = response(progress_server, "/")
    assert status == 404 and b"linked.txt" not in body
