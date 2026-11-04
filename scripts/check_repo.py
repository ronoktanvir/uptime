"""Report only filenames on a failed secret check. Never print matched bytes."""
import argparse
import json
from pathlib import Path
import re
import subprocess

def run_git(*args):
    return subprocess.check_output(["git", *args])

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--compare-local-ramp", action="store_true",
                        help="check committed objects against locally stored credential bytes, without printing them")
    args=parser.parse_args()
    files=run_git("ls-files","-z").decode().split("\0")
    forbidden = {".env", "ramp-sandbox.json", "session.key", "session.secret"}
    for file in filter(None,files):
        if "__pycache__" in Path(file).parts or Path(file).name in forbidden or file.startswith(("runtime/",".venv/")):
            raise SystemExit("forbidden tracked file: "+file)
    secrets=[]
    if args.compare_local_ramp:
        path=Path.home()/".config/uptime/ramp-sandbox.json"
        if path.exists():
            values=json.loads(path.read_text())
            secrets=[values[k].encode() for k in ("client_id","client_secret") if values.get(k)]
    objects=run_git("rev-list","--objects","--all").decode().splitlines()
    patterns=[re.compile(rb"sk-(?:ant-|proj-)[A-Za-z0-9_-]{20,}"),re.compile(rb"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----")]
    count=0
    for line in objects:
        oid,sep,name=line.partition(" ")
        if not sep or not Path(name).suffix or name.endswith((".webm",".mp4",".png",".docx",".svg")):
            continue
        blob=run_git("cat-file","-p",oid)
        if any(value in blob for value in secrets) or any(p.search(blob) for p in patterns):
            raise SystemExit("secret check failed for "+name)
        count+=1
    print(f"Secret check passed for {count} versioned text objects.")
if __name__=="__main__":
    main()
