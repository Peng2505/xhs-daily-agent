"""Robust card screenshotter for the xhs daily run.

Renders out/<date>/{cover,points}.html to 1080x1440 PNG via the dedicated Edge,
retrying Page.captureScreenshot and falling back to JPEG (skill pitfall 18).
"""
import base64
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _cdp import CDP, pick_page  # noqa: E402

DATE = sys.argv[1] if len(sys.argv) > 1 else "2026-10-04"
OUT = os.path.join(r"D:\Hermes Project\xhs-daily\out", DATE)


def shot(c, name):
    url = "file:///D:/Hermes%20Project/xhs-daily/out/{}/{}.html".format(DATE, name)
    c.navigate(url, wait=2.5)
    path = os.path.join(OUT, name + ".png")
    for attempt in range(3):
        try:
            r = c.send("Page.captureScreenshot", timeout=90, format="png")
            with open(path, "wb") as f:
                f.write(base64.b64decode(r["data"]))
            return "png"
        except Exception as e:
            print("  png attempt %d failed: %s" % (attempt + 1, str(e)[:80]))
            time.sleep(2)
    # jpeg fallback, smaller payload
    r = c.send("Page.captureScreenshot", timeout=90, format="jpeg", quality=85)
    with open(path.replace(".png", ".jpg"), "wb") as f:
        f.write(base64.b64decode(r["data"]))
    return "jpg-fallback"


def main():
    t = pick_page()
    c = CDP(ws_url=t["webSocketDebuggerUrl"])
    c.send("Page.enable")
    c.send("Emulation.setDeviceMetricsOverride", width=1080, height=1440,
           deviceScaleFactor=1, mobile=False)
    for name in ("cover", "points"):
        kind = shot(c, name)
        p = os.path.join(OUT, name + ".png")
        print(name, kind, os.path.getsize(p) if os.path.exists(p) else "-",
              "scroll:", c.js("document.documentElement.scrollHeight"),
              "inner:", c.js("window.innerWidth"), c.js("window.innerHeight"))
    c.send("Emulation.clearDeviceMetricsOverride")
    print("cleared; dpr now", c.js("window.devicePixelRatio"))
    print(sorted(os.listdir(OUT)))
    c.close()


if __name__ == "__main__":
    main()
