"""Restart the dedicated Edge debug instance (xhs profile only) and wait for CDP.

Only processes whose command line contains the xhs-daily edge-profile are killed,
so the user's daily browser is untouched.
"""
import json
import os
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PROFILE = r"D:\Hermes Project\xhs-daily\edge-profile"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
PORT = 9222


def ps(cmd):
    return subprocess.run(["powershell", "-NoProfile", "-Command", cmd],
                          capture_output=True, text=True, timeout=120).stdout


def kill_xhs_edge():
    cmd = ("Get-CimInstance Win32_Process -Filter \"Name='msedge.exe'\" | "
           "Where-Object { $_.CommandLine -like '*xhs-daily*edge-profile*' } | "
           "ForEach-Object { $_.ProcessId }")
    pids = [p.strip() for p in ps(cmd).split() if p.strip().isdigit()]
    print("killing pids:", pids)
    for pid in pids:
        ps(f"Stop-Process -Id {pid} -Force -ErrorAction SilentlyContinue")
    time.sleep(4)
    left = ps("Get-CimInstance Win32_Process -Filter \"Name='msedge.exe'\" | "
              "Where-Object { $_.CommandLine -like '*xhs-daily*edge-profile*' } | "
              "Measure-Object | Select-Object -ExpandProperty Count").strip()
    print("remaining xhs edge procs:", left)


def cdp_ok():
    try:
        op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with op.open(f"http://127.0.0.1:{PORT}/json/version", timeout=3) as r:
            return json.loads(r.read().decode())["Browser"]
    except Exception:
        return None


def launch():
    args = [EDGE, f"--remote-debugging-port={PORT}", f"--user-data-dir={PROFILE}",
            "--no-first-run", "--no-default-browser-check",
            "--disable-features=msEdgeFirstRunExperience",
            "--no-proxy-server",
            "https://creator.xiaohongshu.com/publish/publish?source=official"]
    subprocess.Popen(args, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)


def main():
    print("before:", cdp_ok())
    kill_xhs_edge()
    launch()
    deadline = time.time() + 120
    while time.time() < deadline:
        v = cdp_ok()
        if v:
            print("CDP up after {:.1f}s:".format(time.time() - (deadline - 120)), v)
            return 0
        time.sleep(3)
    print("ERROR: CDP still down after 120s")
    return 1


if __name__ == "__main__":
    sys.exit(main())
