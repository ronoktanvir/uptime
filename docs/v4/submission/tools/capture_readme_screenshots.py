#!/usr/bin/env python3
"""Retake the README's three screenshots from the checked-out build, in one command.

Run from the root of a clean checkout of the build to capture:

    uv run --locked python docs/v4/submission/tools/capture_readme_screenshots.py

What it does, and nothing more:
- builds a fresh authored Northwind workspace in a temporary folder and serves it on loopback;
- serves a *copy* of the preserved recorded onboarding workspace (never the original), so the
  recorded Claude Opus 5.5 job can be shown; no model call can start from it, and none is made;
- drives one headless Chrome through the ordinary sign-in form and the offered controls only:
  the four reviewer decisions, Activity, Agreements and Ramp records;
- writes overview.png, contract-reading.png and ramp-record.png (1440x900 viewport at 2x) and
  a report (by default docs/v4/evidence/submission-presentation-20261109/readme-capture-report.json)
  holding the commit, the decisions and the visible text used to check each alt text;
- stops both servers and deletes the temporary folder.

It never contacts Ramp, never signs in anywhere but the local workspaces it served, and adds
nothing to the page except what a person's clicks would. Every browser step and the whole run
have hard time limits: a stalled Chrome is reported as a stall, not retried.
"""
import argparse
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path.cwd()
RECORDED = Path.home() / ".local/share/uptime-engineering/tasks/submission-onboarding-20261109/recorded-workspace"
BILL = "f74ba12c-95d0-582d-9f62-26d8057d1d37"
SETTLED = ("prev => { const b = document.querySelector('#finance-recovery .actions button:not([disabled])');"
           " const s = document.querySelector('#finance-recovery [role=status]');"
           " return (!b || b.innerText.trim() !== prev) && !(s && /Recording/.test(s.textContent)); }")
SIGNED_IN = ("() => !Array.from(document.querySelectorAll('label')).some(l => /Credential file/.test(l.innerText))"
             " && (document.querySelector('main')?.innerText.length || 0) > 200")


def free(port):
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def wait_listening(port, seconds=120):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if not free(port):
            return
        time.sleep(0.25)
    raise RuntimeError(f"nothing listened on {port} within {seconds} s")


def start(args, log):
    return subprocess.Popen(args, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)


def stop(proc):
    if proc and proc.poll() is None:
        os.killpg(proc.pid, signal.SIGINT)
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)


def copy_recorded(source, target):
    shutil.copytree(source, target, symlinks=False)
    os.chmod(target, 0o700)
    config = json.loads((target / "protected/config.json").read_text())
    config["approvals_path"] = str(target / "protected/approvals.json")
    view = target / "protected/view-config.json"
    if view.exists():
        view.unlink()
    fd = os.open(view, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.write(fd, json.dumps(config).encode())
    os.close(fd)
    return view


def sign_in(page, origin, account, credential):
    page.goto(origin + "/")
    page.wait_for_selector("form")
    page.get_by_label("Account name", exact=True).fill(account)
    page.get_by_label("Credential file", exact=True).set_input_files(str(credential))
    page.get_by_role("button", name="Sign in", exact=True).click()
    page.wait_for_function(SIGNED_IN)


def scroll_to_text(page, pattern):
    return page.evaluate("""p => { const re = new RegExp(p);
        const n = Array.from(document.querySelectorAll('main h1, main h2, main h3, main h4, main dt, main strong'))
          .find(x => re.test(x.textContent));
        if (n) { n.scrollIntoView({block: 'start'}); window.scrollBy(0, -16); }
        return n ? n.textContent.trim() : null; }""", pattern)


def visible_text(page):
    return page.evaluate("""() => { const out = []; const h = window.innerHeight;
        const walker = document.createTreeWalker(document.querySelector('main') || document.body, NodeFilter.SHOW_TEXT);
        let n; while ((n = walker.nextNode())) { const t = n.textContent.trim(); if (!t) continue;
          const el = n.parentElement; if (!el || el.closest('details:not([open]) > :not(summary)')) continue;
          const r = el.getBoundingClientRect(); if (r.bottom > 0 && r.top < h && r.width > 0) out.push(t); }
        return out.join(' | ').slice(0, 4000); }""")


def capture(out, walk_origin, walk_credential, contract_origin, contract_credential, report):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome", headless=True, timeout=30000)
        try:
            context = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=2)
            page = context.new_page()
            page.set_default_timeout(30000)
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)[:200]))

            sign_in(page, walk_origin, "scripted-test-reviewer", walk_credential)
            page.wait_for_selector("#finance-recovery")
            decisions = []
            for _ in range(8):
                buttons = page.locator("#finance-recovery .actions button:not([disabled])")
                if buttons.count() == 0:
                    break
                label = buttons.first.inner_text().strip()
                t = time.monotonic()
                buttons.first.click()
                page.wait_for_function(SETTLED, arg=label)
                decisions.append({"clicked": label, "seconds": round(time.monotonic() - t, 2)})
                page.wait_for_timeout(300)
            report["decisions"] = decisions
            page.evaluate("() => { document.activeElement && document.activeElement.blur(); window.scrollTo(0, 0); }")
            page.wait_for_timeout(500)
            page.screenshot(path=str(out / "overview.png"), full_page=False)
            report["overview_visible"] = visible_text(page)

            page.evaluate("() => { location.hash = '#records'; }")
            page.wait_for_function("() => /DocuSign/.test(document.querySelector('main')?.innerText || '')")
            report["ramp_heading"] = scroll_to_text(page, "^Verified Ramp record")
            page.wait_for_timeout(500)
            page.screenshot(path=str(out / "ramp-record.png"), full_page=False)
            report["ramp_visible"] = visible_text(page)
            report["walkthrough_page_errors"] = errors
            context.close()

            context = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=2)
            page = context.new_page()
            page.set_default_timeout(30000)
            sign_in(page, contract_origin, "role1-operator", contract_credential)
            page.evaluate("() => { location.hash = '#agreements'; }")
            page.wait_for_function("() => /26ee4e3f/.test(document.querySelector('main')?.innerText || '')")
            report["contract_heading"] = scroll_to_text(page, "^Model proposal job")
            page.wait_for_timeout(500)
            page.screenshot(path=str(out / "contract-reading.png"), full_page=False)
            report["contract_visible"] = visible_text(page)
            context.close()
        finally:
            browser.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=ROOT / "docs/assets/submission")
    parser.add_argument("--report", type=Path, default=ROOT / "docs/v4/evidence/submission-presentation-20261109/readme-capture-report.json")
    parser.add_argument("--recorded-workspace", type=Path, default=RECORDED)
    parser.add_argument("--walk-port", type=int, default=8865)
    parser.add_argument("--contract-port", type=int, default=8866)
    parser.add_argument("--limit-seconds", type=int, default=420)
    args = parser.parse_args()
    if not (ROOT / "scripts/setup_northwind.py").is_file():
        parser.error("run this from the root of an Uptime checkout")
    if not (args.recorded_workspace / "workspace.sqlite").is_file():
        parser.error(f"recorded workspace not found: {args.recorded_workspace}")
    for port in (args.walk_port, args.contract_port):
        if not free(port):
            parser.error(f"port {port} is in use; choose another with --walk-port/--contract-port")

    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError("capture exceeded its time limit")))
    signal.alarm(args.limit_seconds)
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    report = {"commit": commit, "tracked_changes": bool(dirty), "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    args.out.mkdir(parents=True, exist_ok=True)
    # Resolved: Uptime refuses credential and config paths that pass through a symlink (macOS /var -> /private/var).
    work = Path(tempfile.mkdtemp(prefix="uptime-readme-shots-")).resolve()
    phases = report["phases"] = {}
    t0 = time.monotonic()
    mark = lambda name: phases.__setitem__(name, round(time.monotonic() - t0, 1))
    walk = contract = None
    try:
        walk_origin = f"http://127.0.0.1:{args.walk_port}"
        contract_origin = f"http://127.0.0.1:{args.contract_port}"
        walk_log = open(work / "walk.log", "w")
        walk = start([sys.executable, "scripts/setup_northwind.py", "--directory", str(work / "take"),
                      "--origin", walk_origin, "--serve"], walk_log)
        recorded = work / "recorded-contract"
        view = copy_recorded(args.recorded_workspace, recorded)
        contract_log = open(work / "contract.log", "w")
        contract = start([sys.executable, "scripts/serve.py", "--db", str(recorded / "workspace.sqlite"), "--mode", "replay",
                          "--tenant", "submission-onboarding", "--port", str(args.contract_port),
                          "--public-proposal-config", str(view)], contract_log)
        mark("servers started")
        wait_listening(args.walk_port)
        mark("walkthrough listening")
        wait_listening(args.contract_port)
        mark("recorded contract listening")
        capture(args.out, walk_origin, work / "take/scripted-reviewer.jwk",
                contract_origin, recorded / "role1-operator.jwk", report)
        mark("captured")
        report["result"] = "captured"
    except Exception as error:  # report, never retry
        report["result"] = f"failed: {type(error).__name__}: {str(error).splitlines()[0][:300]}"
        for name in ("walk.log", "contract.log"):
            log = work / name
            if log.exists():
                report[name + "_tail"] = [l for l in log.read_text(errors="replace").splitlines()
                                          if "eprecat" not in l and "starlette" not in l][-12:]
    finally:
        signal.alarm(0)
        stop(walk)
        stop(contract)
        shutil.rmtree(work, ignore_errors=True)
        report["finished"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps({k: report.get(k) for k in ("commit", "tracked_changes", "result", "decisions")}, indent=1))
    return 0 if report["result"] == "captured" else 1


if __name__ == "__main__":
    sys.exit(main())
