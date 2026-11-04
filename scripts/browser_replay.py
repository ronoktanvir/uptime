#!/usr/bin/env python3
"""Record the actual local replay UI without loading a user's database.

Run from the repository with its existing Python environment. This script never
accepts a server URL, database path, provider configuration or login credential.
No traces, HARs, console output, request URLs or cookie state are persisted.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import importlib.util
import ipaddress
import json
from pathlib import Path
import re
import secrets
import socket
import sys
import tempfile
import threading
import time
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class CaptureBlocked(RuntimeError):
    """A sanitized error, safe to show without Playwright's URL-bearing traces."""


def require_loopback(address):
    host = address[0]
    if host == "localhost":
        return
    try:
        allowed = ipaddress.ip_address(host).is_loopback
    except ValueError:
        allowed = False
    if not allowed:
        raise CaptureBlocked("Replay attempted a non-loopback connection")


@contextmanager
def local_connections_only():
    """Guard Python provider transports; browser requests have a separate guard."""
    connect, connect_ex = socket.socket.connect, socket.socket.connect_ex

    def guarded(sock, address):
        if sock.family in {socket.AF_INET, socket.AF_INET6}:
            require_loopback(address)
        return connect(sock, address)

    def guarded_ex(sock, address):
        if sock.family in {socket.AF_INET, socket.AF_INET6}:
            require_loopback(address)
        return connect_ex(sock, address)

    socket.socket.connect, socket.socket.connect_ex = guarded, guarded_ex
    try:
        yield
    finally:
        socket.socket.connect, socket.socket.connect_ex = connect, connect_ex


def allowed_browser_url(value, origin):
    target, expected = urlsplit(value), urlsplit(origin)
    return (target.scheme, target.netloc) == (expected.scheme, expected.netloc)


def new_artifact_directory(path):
    resolved = path.resolve()
    allowed_root = (ROOT / "fixtures" / "qa" / "artifacts").resolve()
    if not resolved.is_relative_to(allowed_root) or resolved == allowed_root:
        raise CaptureBlocked("Output must be a new child of fixtures/qa/artifacts")
    # Never overwrite or mingle a previous capture with this run.
    resolved.mkdir(parents=True, exist_ok=False, mode=0o700)
    return resolved


# Redact rendered URLs/email addresses before screenshots and video frames. The
# browser chrome is never recorded. Only disposable synthetic replay data loads.
REDACT_RENDERED_TEXT = r"""
(() => {
  const redact = () => {
    if (!document.body) return;
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    const changes = [];
    while (walker.nextNode()) {
      const node = walker.currentNode;
      if (['SCRIPT', 'STYLE', 'NOSCRIPT'].includes(node.parentElement?.tagName)) continue;
      const clean = node.textContent
        .replace(/(?:https?:\/\/|www\.)[^\s<>]+/gi, '[source link]')
        .replace(/\/session\/[^\s<>]+/gi, '[session]')
        .replace(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi, '[redacted email]');
      if (clean !== node.textContent) changes.push([node, clean]);
    }
    for (const [node, clean] of changes) node.textContent = clean;
  };
  new MutationObserver(redact).observe(document, {subtree: true, childList: true, characterData: true});
  document.addEventListener('DOMContentLoaded', redact);
})();
"""


def assert_rendered_ui(page):
    page.get_by_text("DETERMINISTIC_REPLAY", exact=False).first.wait_for(timeout=15000)
    if not page.locator("main").count():
        raise CaptureBlocked("UI lacks a main landmark")
    if page.evaluate("document.documentElement.scrollWidth > innerWidth + 2"):
        raise CaptureBlocked("UI overflows the viewport horizontally")
    empty_buttons = page.locator("button").evaluate_all("""buttons => buttons.filter(b =>
        !b.disabled && !b.textContent.trim() && !b.getAttribute('aria-label') &&
        !b.getAttribute('aria-labelledby') && !b.getAttribute('title')).length""")
    if empty_buttons:
        raise CaptureBlocked("UI contains an unnamed actionable button")


def click_named(page, labels):
    """Use real visible controls; never invent URLs or render replacement UI."""
    for label in labels:
        for role in ("link", "button", "tab"):
            locator = page.get_by_role(role, name=re.compile(label, re.I))
            for index in range(locator.count()):
                candidate = locator.nth(index)
                if candidate.is_visible() and candidate.is_enabled():
                    candidate.click()
                    return
    raise CaptureBlocked("A required demo navigation control is unavailable")


def hold_until(page, deadline):
    while time.monotonic() < deadline:
        page.wait_for_timeout(min(500, max(1, (deadline - time.monotonic()) * 1000)))


def record(args):
    if importlib.util.find_spec("uptime.server") is None:
        raise CaptureBlocked("Server has not been merged; no capture was produced")
    from uptime.server import create_app
    import uvicorn
    from playwright.sync_api import sync_playwright

    artifacts = new_artifact_directory(args.output)
    completed = False
    try:
        with tempfile.TemporaryDirectory(prefix="uptime-qa-") as temp, local_connections_only():
            secret = secrets.token_urlsafe(32)
            app = create_app(Path(temp) / "replay.sqlite3", session_secret=secret, mode="replay")
            # Pre-bind an ephemeral loopback socket; never attach to another process.
            listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            listener.bind(("127.0.0.1", 0))
            listener.listen(128)
            origin = "http://127.0.0.1:" + str(listener.getsockname()[1])
            server = uvicorn.Server(uvicorn.Config(app, access_log=False, log_level="critical",
                                                 log_config=None))
            thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
            thread.start()
            try:
                deadline = time.monotonic() + 15
                while not server.started:
                    if not thread.is_alive() or time.monotonic() > deadline:
                        raise CaptureBlocked("Disposable replay server failed to start")
                    time.sleep(0.05)
                with sync_playwright() as playwright:
                    options = {"headless": True}
                    chrome = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
                    if args.chrome:
                        if not chrome.is_file():
                            raise CaptureBlocked("System Chrome is unavailable")
                        options["executable_path"] = str(chrome)
                    browser = playwright.chromium.launch(**options)
                    try:
                        capture_browser(browser, origin, secret, artifacts, args.duration)
                    finally:
                        browser.close()
            finally:
                server.should_exit = True
                thread.join(timeout=10)
                listener.close()
                if thread.is_alive():
                    raise CaptureBlocked("Disposable replay server did not shut down")
        completed = True
    finally:
        if not completed:
            # A partial video must never be mistaken for successful demo evidence.
            for artifact in artifacts.iterdir():
                if artifact.is_file():
                    artifact.unlink()
            artifacts.rmdir()


def capture_browser(browser, origin, secret, artifacts, duration):
    failures = []  # Only counts and generic labels enter the artifact manifest.
    context = browser.new_context(viewport={"width": 1440, "height": 1000},
                                  record_video_dir=str(artifacts),
                                  record_video_size={"width": 1440, "height": 1000},
                                  service_workers="block", reduced_motion="reduce")

    def route_request(route):
        if allowed_browser_url(route.request.url, origin):
            route.continue_()
        else:
            failures.append("nonlocal request")
            route.abort()

    context.route("**/*", route_request)
    context.route_web_socket("**/*", lambda ws: ws.close())
    context.add_init_script(REDACT_RENDERED_TEXT)
    video = None
    try:
        # The real bootstrap endpoint establishes HttpOnly cookies in memory.
        # Authenticate before creating a page so no login URL can enter video.
        login = context.request.get(origin + "/session/" + secret, max_redirects=0)
        if login.status != 303:
            raise CaptureBlocked("Session bootstrap failed")
        cookies = context.cookies()
        if not cookies or not all(cookie["httpOnly"] for cookie in cookies):
            raise CaptureBlocked("Session bootstrap did not establish HttpOnly cookies")
        page = context.new_page()
        video = page.video
        page.on("pageerror", lambda error: failures.append("page error"))
        page.on("response", lambda response: failures.append("HTTP failure")
                if response.status >= 400 else None)
        page.goto(origin + "/", wait_until="networkidle")
        assert_rendered_ui(page)
        # Require the real API and seed, not a static mock or an error shell.
        dashboard = context.request.get(origin + "/api/dashboard")
        if dashboard.status != 200 or not dashboard.json().get("cases"):
            raise CaptureBlocked("Replay dashboard contains no cases")
        case = dashboard.json()["cases"][0]
        page.screenshot(path=str(artifacts / "desktop.png"), full_page=True)
        started = time.monotonic()
        hold_until(page, started + duration * 0.20)
        click_named(page, [re.escape(case["title"]), re.escape(case["vendor"])])
        page.get_by_text(re.compile("evidence|trace|clause", re.I)).first.wait_for()
        page.screenshot(path=str(artifacts / "case.png"), full_page=True)
        hold_until(page, started + duration * 0.45)
        click_named(page, ["onboarding", "adapter lab", "vendor lab"])
        page.get_by_text("Atlassian", exact=False).first.wait_for()
        page.screenshot(path=str(artifacts / "onboarding.png"), full_page=True)
        hold_until(page, started + duration * 0.65)
        click_named(page, ["polic", "approval"])
        page.screenshot(path=str(artifacts / "policy.png"), full_page=True)
        hold_until(page, started + duration * 0.80)
        page.goto(origin + "/", wait_until="networkidle")
        page.set_viewport_size({"width": 390, "height": 844})
        assert_rendered_ui(page)
        page.screenshot(path=str(artifacts / "mobile.png"), full_page=True)
        hold_until(page, started + duration)
        if failures:
            raise CaptureBlocked("Browser encountered an API, JavaScript or network failure")
    finally:
        context.close()
    if video is None:
        raise CaptureBlocked("Video was not initialized")
    raw = Path(video.path())
    raw.rename(artifacts / "backup.webm")
    (artifacts / "manifest.json").write_text(json.dumps({
        "mode": "replay", "sources": ["DETERMINISTIC_REPLAY", "SYNTHETIC_CUSTOMER"],
        "requested_seconds": duration, "minimum_content_seconds": duration,
        "screens": ["desktop", "case", "onboarding", "policy", "mobile"],
        "browser_errors": 0, "external_requests": 0,
        "database": "disposable", "status": "captured",
    }, indent=2) + "\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "fixtures/qa/artifacts/replay")
    parser.add_argument("--chrome", action="store_true", help="Use installed system Chrome")
    parser.add_argument("--duration", type=int, default=120, help="Minimum 120 seconds")
    args = parser.parse_args(argv)
    if args.duration < 120:
        parser.error("Backup recording must contain at least 120 seconds")
    try:
        record(args)
    except (Exception, KeyboardInterrupt):
        # Playwright/HTTP exceptions often embed bootstrap URLs and cookie values.
        print("CAPTURE_BLOCKED: server/UI/browser unavailable or QA assertion failed; no completed evidence retained.",
              file=sys.stderr)
        return 1
    print("Replay desktop/mobile screenshots and backup video captured in the requested QA directory.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
