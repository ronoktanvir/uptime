"""Have the held-out contracts written blind, by fresh Claude Code CLI calls.

Each form's brief is briefs/common.md followed by briefs/style-<n>.md; the exact text sent is written to
briefs/form-<n>.md. The author answers with three documents (A, B, C) and its own record of the values it wrote.
Everything returned is saved as returned (response.txt), the three documents are cut from it at the markers, and
manifest.json records the model, the brief, the time and the SHA-256 of every file. A form is never edited
afterwards; an unusable one is moved to discarded/ with the reason and a new author is asked.

    uv run --locked python fixtures/template_builder_heldout/author.py <form-number> <model> [<form-number> <model> ...]

The CLI's own sign-in is used; no credential is read here. Same safe invocation as uptime.template_builder.ClaudeCLI.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from time import perf_counter

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from uptime.correspondence_model_transport import public_environment  # noqa: E402

TIMEOUT = 900
SYSTEM = "You are an experienced commercial lawyer who drafts technology contracts."


def sha(data):
    return hashlib.sha256(data.encode() if isinstance(data, str) else data).hexdigest()


def call(model, prompt):
    env = public_environment()
    env["PATH"] = os.environ.get("PATH", env["PATH"])
    argv = [str(Path(shutil.which("claude")).resolve()), "-p", "--safe-mode", "--model", model, "--tools", "",
            "--strict-mcp-config", "--setting-sources", "", "--no-session-persistence", "--output-format", "json",
            "--system-prompt", SYSTEM]
    with tempfile.TemporaryDirectory(prefix="uptime-heldout-author-") as empty:
        started = perf_counter()
        done = subprocess.run(argv, input=prompt, cwd=empty, env=env, capture_output=True, text=True, timeout=TIMEOUT)
        seconds = perf_counter() - started
    envelope = json.loads(done.stdout)
    if done.returncode or envelope.get("is_error") is not False or model not in (envelope.get("modelUsage") or {}):
        raise RuntimeError("author call failed: exit %s, models %s" % (done.returncode, list(envelope.get("modelUsage") or {})))
    return envelope["result"], seconds, list(envelope["modelUsage"])


def author(number, model):
    brief = (HERE / "briefs" / "common.md").read_text() + "\n" + (HERE / "briefs" / ("style-%s.md" % number)).read_text()
    brief_file = HERE / "briefs" / ("form-%s.md" % number)
    if brief_file.exists() and brief_file.read_text() != brief:
        raise SystemExit("briefs/form-%s.md differs from common.md + style-%s.md" % (number, number))
    brief_file.write_text(brief)
    folder = HERE / "forms" / ("form-%s" % number)
    if folder.exists():
        raise SystemExit("%s exists; move it to discarded/ with a reason first" % folder)
    asked_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    text, seconds, models = call(model, brief)
    folder.mkdir(parents=True)
    (folder / "response.txt").write_text(text)
    files = {"response.txt": sha(text)}
    parts = re.split(r"^===(DOCUMENT [ABC]|VALUES)===[ \t]*$", text, flags=re.M)
    found = {parts[i]: parts[i + 1] for i in range(1, len(parts) - 1, 2)}
    problems = []
    for letter in "ABC":
        body = found.get("DOCUMENT " + letter)
        if body is None:
            problems.append("no DOCUMENT %s marker" % letter)
            continue
        body = body.strip("\n") + "\n"
        (folder / (letter.lower() + ".txt")).write_text(body)
        files[letter.lower() + ".txt"] = sha(body)
    values = found.get("VALUES")
    if values is not None:
        raw = values.strip()
        fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", raw, re.S)
        (folder / "author_values.json").write_text((fenced.group(1) if fenced else raw) + "\n")
        files["author_values.json"] = sha((folder / "author_values.json").read_text())
        try:
            json.loads((folder / "author_values.json").read_text())
        except ValueError:
            problems.append("VALUES is not JSON")
    else:
        problems.append("no VALUES marker")
    manifest = {"form": number, "model_requested": model, "models_answered": models, "asked_at": asked_at,
                "seconds": round(seconds, 1), "brief_file": "briefs/form-%s.md" % number, "brief_sha256": sha(brief),
                "system_prompt": SYSTEM,
                "cutting": "a.txt, b.txt, c.txt are the text between the markers in response.txt, with leading and "
                           "trailing newlines removed and one final newline; author_values.json is the VALUES part "
                           "without a ```json fence. Nothing else is changed.",
                "files": files, "problems": problems}
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    return number, model, round(seconds, 1), problems, {k: len(v) for k, v in found.items()}


if __name__ == "__main__":
    pairs = list(zip(sys.argv[1::2], sys.argv[2::2]))
    with ThreadPoolExecutor(len(pairs)) as pool:
        for result in pool.map(lambda p: author(*p), pairs):
            print(result)
