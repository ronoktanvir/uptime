"""Run independent, tool-free Opus reviews on explicitly authored, sanitized decision packets."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from functools import partial
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs/v4/decisions"
MODEL = "claude-opus-5-5"


def consult(packet, max_words=210):
    instruction = ("Critically review this design as an independent adviser. This packet is sanitized and contains no customer information. "
                   "Assess the alternatives, costs, strongest objection, concrete falsification tests, and any required human authorization. "
                   f"Identify unsupported claims. No tools. Return no more than {max_words} words.\n")
    prompt = instruction + packet.read_text()
    receipt = {"model_requested": MODEL, "utc": datetime.now(UTC).isoformat(),
               "packet_sha256": sha256(packet.read_bytes()).hexdigest(), "prompt_sha256": sha256(prompt.encode()).hexdigest()}
    executable = shutil.which("claude") or str(Path.home() / ".local/bin/claude")
    try:
        with tempfile.TemporaryDirectory() as empty:
            run = subprocess.run([executable, "-p", "--model", MODEL, "--tools", "", "--strict-mcp-config",
                                  "--setting-sources", "", "--no-session-persistence", "--output-format", "json"],
                                 input=prompt, capture_output=True, text=True, cwd=empty, timeout=165)
        response = json.loads(run.stdout)
        models = sorted(response.get("modelUsage", {}))
        if run.returncode or response.get("is_error") is not False or MODEL not in models or not response.get("result"):
            raise ValueError("reviewer identity or output unverified")
        receipt.update(status="REVIEWED", session=response["session_id"], models=models, reply=response["result"])
    except (OSError, ValueError, KeyError, subprocess.TimeoutExpired) as exc:
        receipt.update(status="OPUS_BLOCKED", error=type(exc).__name__)
    target = DOCS / "reviews" / (packet.stem + ".json")
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(receipt, indent=2) + "\n")
    tmp.replace(target)
    print(packet.stem, receipt["status"], flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("stem", nargs="*")
    parser.add_argument("--max-words", type=int, choices=range(100,2001), default=210, metavar="100..2000")
    args = parser.parse_args()
    files = sorted((DOCS / "packets").glob("*.md"))
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(partial(consult,max_words=args.max_words), [f for f in files if not args.stem or f.stem in args.stem]))
