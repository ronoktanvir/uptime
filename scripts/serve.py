"""Start the replay or saved-sandbox workbench. Never bind beyond loopback."""
import argparse
import os
from pathlib import Path
import secrets
import socket
import sys
from tempfile import TemporaryDirectory
import threading
from urllib.request import urlopen
import webbrowser
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import uvicorn
from uptime.server import create_app, viewer_token

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--mode",choices=["sandbox","replay"],default="sandbox")
    parser.add_argument("--db",type=Path,default=Path("runtime/workbench.sqlite"))
    parser.add_argument("--port",type=int,default=8765)
    parser.add_argument("--open",action="store_true",help="Open the reviewer session in the default browser")
    args=parser.parse_args()
    os.umask(0o077)
    secret=secrets.token_urlsafe(32)
    app=create_app(args.db,session_secret=secret,mode=args.mode)
    # Reserve the exact listener before disclosing a bootstrap URL, even on a busy port.
    listener=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    try:
        listener.bind(("127.0.0.1",args.port))
    except OSError:
        parser.exit(1,"Port unavailable. Select a different --port.\n")
    listener.listen()
    base=f"http://127.0.0.1:{listener.getsockname()[1]}"
    url=base+"/session/"+secret
    if args.open:
        def launch():
            for _ in range(80):
                try:
                    with urlopen(base+"/health",timeout=.5) as r:
                        if r.status==200: break
                except OSError:
                    time.sleep(.1)
            else:
                return
            webbrowser.open(url)
        threading.Thread(target=launch,daemon=True).start()
        print("Opening a local reviewer session. Stop the server with Ctrl-C.",flush=True)
    else:
        # A terminal or service log may be retained; keep bearer links in a private file.
        session_dir=TemporaryDirectory(prefix="uptime-launch-")
        launch_page=Path(session_dir.name)/"open.html"
        launch_page.write_text(f'<meta name="referrer" content="no-referrer"><h1>Uptime local session</h1><p><a href="{url}">Open reviewer workbench</a></p><a href="{base}/session/{viewer_token(secret)}">Open read-only workbench</a>')
        launch_page.chmod(0o600)
        print(f"Open this private file on the server machine: {launch_page}",flush=True)
    config=uvicorn.Config(app,access_log=False,proxy_headers=False,log_level="warning")
    try:
        uvicorn.Server(config).run(sockets=[listener])
    finally:
        listener.close()

if __name__=="__main__":
    main()
