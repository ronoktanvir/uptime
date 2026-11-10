"""Real-browser check of the Uptime side-panel extension against a served workspace.

Run it by hand; it is not part of the test suite. It needs Google Chrome installed.

    uv run --locked python scripts/check_side_panel.py ORIGIN ACCOUNT CREDENTIAL_FILE OUT_DIR

ORIGIN is a workspace served with
    --side-panel-origin chrome-extension://kibophanbmnepbmhpampfagpjfhjfcnl
for example by scripts/setup_northwind.py --serve. ACCOUNT and CREDENTIAL_FILE are the test
reviewer that command printed.

What it does:
- loads a copy of extension/ into a throwaway Chrome profile. The copy differs from the
  packaged extension only in the origin written in config.js, so the check can use any port;
  the manifest key, and therefore the extension's ID and origin, are unchanged;
- opens the extension's panel page, signs in inside the framed app, and moves between tabs.

What it does not do:
- contact Ramp. Every request to demo.ramp.com is answered by a local stub;
- open the browser's side-panel container itself, which only a person can do from the toolbar;
- click any reviewer decision.

Each run is under a hard time limit so a blocked browser cannot hang the caller.
"""
import json
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] if (Path(__file__).resolve().parents[1] / "extension").is_dir() else None
EXTENSION_ID = "kibophanbmnepbmhpampfagpjfhjfcnl"
BILL = "f74ba12c-95d0-582d-9f62-26d8057d1d37"   # the sandbox bill in fixtures/ramp/verified-demo-bill.json
OTHER = "11111111-2222-4333-8444-555555555555"  # a well-formed bill id with no saved record
LIMIT_SECONDS = 150


def run(extension, origin, account, credential, out_dir):
    from playwright.sync_api import sync_playwright
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    report = {}

    def uptime_frame(page):
        return next((f for f in page.frames if f.url.startswith(origin)), None)

    def text_of(frame):
        return frame.locator("#content").inner_text() if frame else ""

    with urllib.request.urlopen(origin + "/") as response:
        policy = response.headers.get("Content-Security-Policy", "")
    report["1_frame_ancestors"] = next((part.strip() for part in policy.split(";") if "frame-ancestors" in part), None)

    profile = tempfile.mkdtemp(prefix="uptime-panel-check-")
    try:
        with sync_playwright() as pw:
            context = pw.chromium.launch_persistent_context(
                profile, channel="chrome", headless=True, viewport={"width": 420, "height": 900},
                args=["--enable-unsafe-extension-debugging"], ignore_default_args=["--disable-extensions"])
            context.route("https://demo.ramp.com/**", lambda route: route.fulfill(
                content_type="text/html", body="<!doctype html><title>local stub</title><p>Local stub. Ramp was not contacted.</p>"))
            loaded = context.browser.new_browser_cdp_session().send("Extensions.loadUnpacked", {"path": extension})
            report["extension_loaded_as"] = loaded.get("id")

            panel = context.new_page()
            console = []
            panel.on("console", lambda m: console.append(f"{m.type}: {m.text}"[:300]) if m.type in ("error", "warning") else None)
            panel.goto(f"chrome-extension://{EXTENSION_ID}/panel.html")
            panel.wait_for_timeout(1500)
            frame = uptime_frame(panel)
            report["2_panel_frames_uptime"] = frame.url if frame else None
            if not frame:
                report["frames"] = [f.url for f in panel.frames]
                report["console"] = console
                return report

            frame.wait_for_selector("form", timeout=10000)
            frame.get_by_label("Account name", exact=True).fill(account)
            frame.locator("input[type=file]").set_input_files(credential)
            frame.get_by_role("button", name="Sign in", exact=True).click()
            frame.get_by_text("Verified Ramp record", exact=True).first.wait_for(timeout=20000)
            report["3_signed_in_inside_frame"] = {
                "account_control": frame.locator("#account").inner_text(),
                "label": panel.locator("#bill").inner_text(),
                "verified_record_visible": frame.get_by_text("Verified Ramp record", exact=True).first.is_visible()}
            panel.screenshot(path=str(out / "panel-1-records-signed-in.png"))

            ramp = context.new_page()
            ramp.goto(f"https://demo.ramp.com/bill-pay/bills/list/{BILL}")
            ramp.bring_to_front()
            panel.wait_for_timeout(1800)
            frame = uptime_frame(panel)
            shown = text_of(frame)
            report["4_follows_the_ramp_bill_tab"] = {
                "stub_served": ramp.title(), "label": panel.locator("#bill").inner_text(),
                "frame_url": frame.url if frame else None,
                "still_signed_in": bool(frame) and frame.locator("#account").inner_text(),
                "heading": frame.locator("#content h1").first.inner_text() if frame else None,
                "says": {phrase: phrase in shown for phrase in (
                    "DD-PREAPPROVAL", "USD 840", "Not a live read", "Uptime has made no write to Ramp",
                    "Posted by a person in Ramp")},
                "wider_than_panel": panel.evaluate("document.documentElement.scrollWidth > innerWidth"),
            }
            panel.screenshot(path=str(out / "panel-2-the-verified-bill.png"))

            ramp.goto(f"https://demo.ramp.com/bill-pay/bills/list/{OTHER}")
            panel.wait_for_timeout(1800)
            frame = uptime_frame(panel)
            shown = text_of(frame)
            report["5_a_bill_with_no_saved_record"] = {
                "label": panel.locator("#bill").inner_text(), "frame_url": frame.url if frame else None,
                "heading": frame.locator("#content h1").first.inner_text() if frame else None,
                "shows_the_other_bills_facts": any(word in shown for word in ("DocuSign", "DD-PREAPPROVAL", "USD 840"))}
            panel.screenshot(path=str(out / "panel-3-no-saved-record.png"))

            elsewhere = context.new_page()
            elsewhere.goto(origin + f"/bill-pay/bills/list/{BILL}")
            elsewhere.bring_to_front()
            panel.wait_for_timeout(1800)
            frame = uptime_frame(panel)
            report["6_another_site_with_the_same_path_is_not_followed"] = {
                "label": panel.locator("#bill").inner_text(), "frame_url": frame.url if frame else None,
                "still_signed_in": bool(frame) and frame.locator("#account").inner_text()}

            stranger = context.new_page()
            refused = []
            stranger.on("console", lambda m: refused.append(m.text[:240]) if "frame" in m.text.lower() else None)
            stranger.route("http://localhost:8799/parent.html", lambda route: route.fulfill(
                content_type="text/html", body=f"<!doctype html><title>stranger</title><iframe src='{origin}/'></iframe>"))
            stranger.goto("http://localhost:8799/parent.html")
            stranger.wait_for_timeout(1500)
            report["7_another_page_may_not_frame_the_app"] = {
                "child_frames": [f.url for f in stranger.frames][1:], "browser_said": refused[:2]}

            report["panel_console"] = console[:10]
            context.close()
    finally:
        shutil.rmtree(profile, ignore_errors=True)
    return report


def main():
    if len(sys.argv) == 7 and sys.argv[1] == "--child":
        print(json.dumps(run(*sys.argv[2:7]), indent=2))
        return
    if len(sys.argv) != 5:
        sys.exit(__doc__)
    origin, account, credential, out_dir = sys.argv[1:5]
    if ROOT is None:
        sys.exit("Run this from a checkout that contains extension/.")
    copy = Path(tempfile.mkdtemp(prefix="uptime-panel-extension-")) / "extension"
    shutil.copytree(ROOT / "extension", copy)
    config = copy / "config.js"
    packaged = "origin: 'http://127.0.0.1:8776'"
    text = config.read_text()
    if text.count(packaged) != 1:
        sys.exit("extension/config.js no longer has the packaged origin this check rewrites.")
    config.write_text(text.replace(packaged, "origin: '" + origin + "'"))
    try:
        child = subprocess.run([sys.executable, __file__, "--child", str(copy), origin, account, credential, out_dir],
                               capture_output=True, text=True, timeout=LIMIT_SECONDS)
        print(child.stdout or child.stderr[-2000:])
        sys.exit(child.returncode)
    except subprocess.TimeoutExpired:
        sys.exit(f"The browser did not finish within {LIMIT_SECONDS} seconds; nothing is concluded from this run.")
    finally:
        shutil.rmtree(copy.parent, ignore_errors=True)


if __name__ == "__main__":
    main()
