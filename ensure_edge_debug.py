#!/usr/bin/env python
"""Ensure the dedicated Edge debug instance for Xiaohongshu automation is up.

The instance uses its OWN user-data-dir, so it never fights the user's daily
browser for the profile lock and cookies persist across runs (that is what
keeps the Xiaohongshu login alive between daily cron runs).

Idempotent: if the CDP endpoint already answers, it does nothing.
Prints a one-line status for the cron pre-run hook.
"""
import json
import os
import subprocess
import sys
import time
import urllib.request

PORT = int(os.environ.get("XHS_DEBUG_PORT", "9222"))
PROFILE_DIR = os.environ.get(
    "XHS_PROFILE_DIR", r"D:\Hermes Project\xhs-daily\edge-profile"
)
EDGE_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]


def cdp_version(port: int):
    try:
        # Bypass any (possibly dead) system proxy: urllib would otherwise route
        # even 127.0.0.1 through it and report a bogus ConnectionRefused.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(
            f"http://127.0.0.1:{port}/json/version", timeout=2
        ) as resp:
            return json.loads(resp.read().decode("utf-8", "replace"))
    except Exception:
        return None


def find_edge():
    for path in EDGE_CANDIDATES:
        if os.path.isfile(path):
            return path
    return None


def main() -> int:
    if cdp_version(PORT):
        print(f"OK: CDP already listening on 127.0.0.1:{PORT}")
        return 0

    edge = find_edge()
    if not edge:
        print("ERROR: msedge.exe not found in the known install locations")
        return 1

    os.makedirs(PROFILE_DIR, exist_ok=True)
    args = [
        edge,
        f"--remote-debugging-port={PORT}",
        f"--user-data-dir={PROFILE_DIR}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-features=msEdgeFirstRunExperience",
        # The machine's system proxy (127.0.0.1:2023) is often not running; Edge
        # would then fail every page with ERR_PROXY_CONNECTION_FAILED. This
        # instance only talks to domestic sites (xiaohongshu), so go direct.
        "--no-proxy-server",
        "https://creator.xiaohongshu.com/publish/publish",
    ]
    creationflags = 0
    if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(
        args,
        creationflags=creationflags,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
    )

    deadline = time.time() + 40
    while time.time() < deadline:
        if cdp_version(PORT):
            print(f"OK: started Edge debug instance on 127.0.0.1:{PORT}")
            return 0
        time.sleep(1)

    print(f"ERROR: Edge launched but CDP on port {PORT} never answered within 40s")
    return 1


if __name__ == "__main__":
    sys.exit(main())
