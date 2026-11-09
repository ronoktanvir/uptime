# Open the Uptime dependency map

Anyone can clone this public repository and run the map on their own computer. It needs Python 3.9 or newer, but no Ramp credentials, application database or Python package installation. For a diagram directly on GitHub, start with the [engineering map](../docs/ENGINEERING-MAP.md).

```sh
git clone https://github.com/ronoktanvir/uptime.git
cd uptime
python3 scripts/serve_progress.py --port 8780
```

Open [http://127.0.0.1:8780/](http://127.0.0.1:8780/). Keep the terminal running while viewing the map; Ctrl-C stops the server. For an existing clone, run the server from that repository instead of cloning again. Cloning the repository does not grant access to Ramp, reviewer credentials or private application state.

## Get the latest recorded progress

In a clean clone on `main`, run:

```sh
git pull --ff-only
```

Then use the dashboard's Refresh button. The server serves the current files, so a restart is unnecessary for snapshot updates. `progress/data.json` contains the dated, manually maintained status, dependency edges and evidence links. Refresh does not query agents or execute engineering work. Always check the displayed update time; source-linked test results and live permissions are distinct measurements.

## View the same running instance remotely

`localhost` belongs to the computer opening the URL. A teammate cannot reach another machine's server by opening their own localhost without a tunnel. The default server accepts only local connections and validates the Host header; simply sharing the host's Wi-Fi address will not work.

If the teammate already has authorized SSH access to the host running the dashboard, they can forward the existing local port:

```sh
ssh -N -L 8780:127.0.0.1:8780 USER@HOST
```

Replace `USER@HOST` with that existing SSH destination. On the teammate's computer, open `http://127.0.0.1:8780/` while the SSH connection and host dashboard remain running. Their port 8780 must be free. This uses existing SSH access; it does not enable remote login, publish a public URL or change repository permissions.

A hosted shared URL is not configured. The map's evidence links point to published repository records. Its companion-application link uses localhost, so it opens an application only when that separate application is running on the viewer's machine or independently forwarded.
